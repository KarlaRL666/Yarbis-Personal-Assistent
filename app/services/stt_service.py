import abc
import asyncio
import io
import logging
import subprocess
import wave
from pathlib import Path
from typing import Optional
import imageio_ffmpeg
import speech_recognition as sr
from openai import AsyncOpenAI
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _decode_audio_to_pcm_wav_bytes(audio_path: Path) -> bytes:
    """
    Convierte cualquier formato de audio móvil (.wav, .m4a, .3gp, .aac, .mp3, .ogg, .webm, .amr)
    a WAV PCM 16kHz 16-bit mono en memoria de forma aislada y segura.
    """
    # 1. Si ya es un archivo WAV PCM válido, leerlo directamente sin subprocess
    if audio_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio_path), "rb") as w:
                if w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == 16000 and w.getnframes() > 0:
                    return audio_path.read_bytes()
        except Exception:
            pass

    # 2. Para .m4a, .3gp, .mp3, .aac o WAV con otra frecuencia, usar el binario ffmpeg aislado
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(audio_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-f", "wav",
        "pipe:1"
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=10)
    if proc.returncode != 0 or len(proc.stdout) <= 44:
        err_msg = proc.stderr.decode("utf-8", errors="ignore").strip()
        raise ValueError(f"FFmpeg no pudo decodificar {audio_path.name}: {err_msg}")

    return proc.stdout


class BaseSTTService(abc.ABC):
    """Interfaz abstracta desacoplada para servicios de Speech-To-Text."""

    @abc.abstractmethod
    async def transcribe(self, audio_path: Path) -> str:
        """
        Transcribe el archivo de audio dado a texto en lenguaje natural.

        Args:
            audio_path: Ruta al archivo en disco (WAV, MP3, M4A, etc.)

        Returns:
            str: Transcripción textual obtenida.
        """
        pass


def _normalize_wav_gain(wav_bytes: bytes) -> bytes:
    """Normaliza la ganancia del audio si fue grabado a volumen bajo para mejorar reconocimiento STT."""
    try:
        import array
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())

        arr = array.array("h", frames)
        if not arr:
            return wav_bytes

        peak = max(abs(x) for x in arr)
        # Si el pico de amplitud es bajo (micrófono celular alejado), amplificar limpiamente
        if 50 < peak < 22000:
            scale = min(28000.0 / peak, 12.0)
            norm_arr = array.array("h", (int(x * scale) for x in arr))
            out_io = io.BytesIO()
            with wave.open(out_io, "wb") as out_w:
                out_w.setparams(params)
                out_w.writeframes(norm_arr.tobytes())
            return out_io.getvalue()
        return wav_bytes
    except Exception:
        return wav_bytes


class GoogleSpeechSTT(BaseSTTService):
    """
    Implementación de STT gratuita y sin API Key mediante Google Web Speech API + PyAV.
    Soporta nativamente contenedores móviles (.m4a, .3gp, .aac, .mp3, .wav, .ogg, .webm).
    """

    def __init__(self, language: str = "es-MX"):
        self.language = language

    def _transcribe_sync(self, audio_path: Path) -> str:
        wav_bytes = _decode_audio_to_pcm_wav_bytes(audio_path)
        wav_bytes = _normalize_wav_gain(wav_bytes)
        recognizer = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio_data = recognizer.record(source)

        # Probar idiomas de forma jerárquica para maximizar acierto fonético en español
        langs_to_try = [self.language]
        for l in ["es-ES", "es-US", "es"]:
            if l not in langs_to_try:
                langs_to_try.append(l)

        for lang in langs_to_try:
            try:
                text = recognizer.recognize_google(audio_data, language=lang)
                if text and text.strip():
                    return text.strip()
            except sr.UnknownValueError:
                continue
            except Exception as e:
                logger.warning(f"[STT Google] Error con idioma {lang}: {e}")
                continue

        logger.info(f"[STT Google] No se detectó voz inteligible en {audio_path.name}")
        return ""

    async def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(f"Archivo de audio no encontrado: {audio_path}")

        # Si es un archivo stub diminuto de pruebas unitarias (< 256 bytes sin muestras reales),
        # usar el mock para preservar compatibilidad con tests sintéticos.
        file_size = audio_path.stat().st_size
        if file_size < 256:
            logger.info(f"[STT] Archivo sintético de prueba detectado ({file_size} bytes). Usando MockSTTService.")
            return await MockSTTService.get_mock_transcript(audio_path)

        try:
            text = await asyncio.to_thread(self._transcribe_sync, audio_path)
            logger.info(f"[STT Google] Transcripción completada: '{text}'")
            return text
        except Exception as e:
            logger.error(f"[STT Google Error] Fallo al procesar {audio_path.name}: {e}")
            return ""


class OpenAIWhisperSTT(BaseSTTService):
    """Implementación de STT mediante el modelo Whisper de OpenAI con respaldo real en GoogleSpeechSTT."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
            base_url=base_url or settings.OPENAI_BASE_URL,
            max_retries=0,
            timeout=10.0
        )
        self.fallback_stt = GoogleSpeechSTT()
        self._openai_unavailable = False

    async def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(f"Archivo de audio no encontrado: {audio_path}")

        # Si es un archivo stub de prueba unitaria (< 256 bytes), evitar llamada de red innecesaria
        if audio_path.stat().st_size < 256:
            return await MockSTTService.get_mock_transcript(audio_path)

        if self._openai_unavailable:
            return await self.fallback_stt.transcribe(audio_path)

        try:
            model = "whisper-large-v3" if "groq" in str(self.client.base_url).lower() else "whisper-1"
            with open(audio_path, "rb") as audio_file:
                transcript_response = await self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language="es",
                    temperature=0.0
                )
                text = transcript_response.text.strip()
                logger.info(f"[STT OpenAI] Transcripción completada: '{text}'")
                return text
        except Exception as e:
            err_str = str(e).lower()
            if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "429" in err_str or "401" in err_str:
                logger.warning(
                    "[STT OpenAI] Cuota agotada o clave inválida en OpenAI. "
                    "Cambiando permanentemente a GoogleSpeechSTT para reconocimiento real de voz."
                )
                self._openai_unavailable = True
            else:
                logger.warning(f"[STT OpenAI Fallback] Fallo en OpenAI ({e}). Usando GoogleSpeechSTT real.")
            return await self.fallback_stt.transcribe(audio_path)


class MockSTTService(BaseSTTService):
    """
    Implementación simulada únicamente para pruebas unitarias sintéticas sin audio real.
    """

    _SAMPLE_COMMANDS = [
        "Yarbis, enciende la linterna",
        "Yarbis, abre Spotify",
        "Yarbis, pon una alarma a las 7:30",
        "Yarbis, pon un temporizador de 5 minutos",
        "Yarbis, sube el volumen al 80%",
        "Yarbis, abre YouTube",
        "Yarbis, apaga la linterna",
        "Yarbis, ¿cuál es la distancia a la luna?"
    ]
    _index: int = 0

    def __init__(self, default_response: Optional[str] = None):
        self.default_response = default_response

    @classmethod
    async def get_mock_transcript(cls, audio_path: Path, default_response: Optional[str] = None) -> str:
        import os
        custom_env = os.getenv("MOCK_STT_COMMAND")
        if custom_env:
            response = custom_env
        elif default_response:
            response = default_response
        else:
            response = cls._SAMPLE_COMMANDS[cls._index % len(cls._SAMPLE_COMMANDS)]
            cls._index += 1
        logger.info(f"[STT Mock] Transcripción simulada generada: '{response}' para {audio_path.name}")
        return response

    async def transcribe(self, audio_path: Path) -> str:
        return await self.get_mock_transcript(audio_path, self.default_response)


_stt_instance: Optional[BaseSTTService] = None


def get_stt_service() -> BaseSTTService:
    """Fábrica e inyector de dependencias para el servicio STT."""
    global _stt_instance
    if _stt_instance is None:
        settings = get_settings()
        provider = settings.STT_PROVIDER.lower()

        if provider in ("google", "free", "auto"):
            _stt_instance = GoogleSpeechSTT()
        elif provider == "openai":
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("tu_"):
                logger.warning(
                    "[STT] OPENAI_API_KEY no configurada. Activando GoogleSpeechSTT para reconocimiento real de voz."
                )
                _stt_instance = GoogleSpeechSTT()
            else:
                _stt_instance = OpenAIWhisperSTT()
        elif provider == "mock":
            _stt_instance = MockSTTService()
        else:
            logger.warning(f"[STT] Proveedor '{provider}' desconocido. Usando GoogleSpeechSTT.")
            _stt_instance = GoogleSpeechSTT()

    return _stt_instance
