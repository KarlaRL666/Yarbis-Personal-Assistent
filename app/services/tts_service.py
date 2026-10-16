import abc
import logging
from pathlib import Path
from typing import Optional
import edge_tts
from openai import AsyncOpenAI
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BaseTTSService(abc.ABC):
    """Interfaz abstracta desacoplada para síntesis de voz (Text-To-Speech)."""

    @abc.abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path:
        """
        Sintetiza el texto a un archivo de audio y lo almacena en output_path.

        Args:
            text: Frase o respuesta verbal a sintetizar.
            output_path: Destino en disco donde guardar el archivo generado (MP3).

        Returns:
            Path: Ruta del archivo generado.
        """
        pass


class EdgeTTSService(BaseTTSService):
    """
    Síntesis de voz neural de alta calidad utilizando Edge TTS (gratuito, sin API key).
    Ideal para un asistente operativo con voces en español de tono profesional.
    """

    def __init__(self, voice: Optional[str] = None):
        settings = get_settings()
        self.voice = voice or settings.EDGE_TTS_VOICE

    async def synthesize(self, text: str, output_path: Path) -> Path:
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(output_path))
            logger.info(f"[TTS Edge] Audio generado exitosamente con voz {self.voice}: {output_path.name}")
            return output_path
        except Exception as e:
            logger.error(f"[TTS Edge Error] Falló la síntesis para '{text[:30]}...': {e}")
            raise


class OpenAITTSService(BaseTTSService):
    """Síntesis de voz utilizando OpenAI TTS (tts-1)."""

    def __init__(self, api_key: Optional[str] = None, voice: Optional[str] = None):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self.voice = voice or settings.OPENAI_TTS_VOICE

    async def synthesize(self, text: str, output_path: Path) -> Path:
        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=text
            )
            # Guardar el stream de audio en disco
            await response.astream_to_file(output_path)
            logger.info(f"[TTS OpenAI] Audio generado con voz {self.voice}: {output_path.name}")
            return output_path
        except Exception as e:
            logger.error(f"[TTS OpenAI Error] Falló la síntesis de OpenAI: {e}")
            raise


class MockTTSService(BaseTTSService):
    """Servicio simulado para pruebas rápidas y entornos de CI/CD sin conectividad."""

    async def synthesize(self, text: str, output_path: Path) -> Path:
        logger.info(f"[TTS Mock] Creando archivo simulado en {output_path.name}")
        output_path.touch(exist_ok=True)
        return output_path


_tts_instance: Optional[BaseTTSService] = None


def get_tts_service() -> BaseTTSService:
    """Fábrica e inyector de dependencias para el servicio TTS."""
    global _tts_instance
    if _tts_instance is None:
        settings = get_settings()
        provider = settings.TTS_PROVIDER.lower()

        if provider == "edge_tts":
            _tts_instance = EdgeTTSService()
        elif provider == "openai":
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("tu_"):
                logger.warning(
                    "[TTS] OPENAI_API_KEY no configurada o es plantilla. Activando EdgeTTSService como alternativa de alta calidad."
                )
                _tts_instance = EdgeTTSService()
            else:
                _tts_instance = OpenAITTSService()
        elif provider == "mock":
            _tts_instance = MockTTSService()
        else:
            logger.warning(f"[TTS] Proveedor '{provider}' desconocido. Usando EdgeTTSService por defecto.")
            _tts_instance = EdgeTTSService()

    return _tts_instance
