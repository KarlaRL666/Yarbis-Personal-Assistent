import logging
from pathlib import Path
from typing import Optional
from app.core.config import get_settings
from app.core.wake_word import WakeWordValidator
from app.schemas.common import ActionType
from app.schemas.response import YarbisResponse
from app.services.llm_service import LLMService, get_llm_service
from app.services.session_service import SessionService, get_session_service
from app.services.stt_service import BaseSTTService, get_stt_service
from app.services.tts_service import BaseTTSService, get_tts_service
from app.utils.audio import generate_audio_filename, get_audio_url, file_to_base64

logger = logging.getLogger(__name__)


class YarbisOrchestrator:
    """
    Orquestador Central de Yarbis.
    Coordina el ciclo de vida completo de cada interacción:
    Audio -> STT -> Validación de Wake Word -> Memoria de Sesión -> Razonamiento LLM/Tools -> TTS -> Respuesta Kotlin / Android.
    """

    def __init__(
        self,
        stt_service: Optional[BaseSTTService] = None,
        tts_service: Optional[BaseTTSService] = None,
        llm_service: Optional[LLMService] = None,
        session_service: Optional[SessionService] = None,
    ):
        self.settings = get_settings()
        self.stt = stt_service or get_stt_service()
        self.tts = tts_service or get_tts_service()
        self.llm = llm_service or get_llm_service()
        self.session = session_service or get_session_service()

    async def process_text_command(
        self,
        text: str,
        session_id: str = "default",
        user_id: Optional[str] = None,
        require_wake_word: Optional[bool] = None,
        generate_audio: bool = True,
        include_audio_base64: bool = False
    ) -> YarbisResponse:
        """Procesa una orden proveniente de texto directo."""
        return await self._orchestrate_pipeline(
            raw_input_text=text,
            session_id=session_id,
            user_id=user_id,
            require_wake_word=require_wake_word,
            generate_audio=generate_audio,
            include_audio_base64=include_audio_base64,
            is_voice_input=False
        )

    async def process_voice_audio(
        self,
        audio_path: Path,
        session_id: str = "default",
        user_id: Optional[str] = None,
        require_wake_word: Optional[bool] = None,
        generate_audio: bool = True,
        include_audio_base64: bool = False
    ) -> YarbisResponse:
        """Procesa un archivo de audio proveniente del micrófono de Kotlin / Android."""
        # Paso 1: Transcripción con STT desacoplado
        try:
            transcription = await self.stt.transcribe(audio_path)
        finally:
            # Limpiar archivo temporal de subida
            if audio_path.exists():
                try:
                    audio_path.unlink()
                except Exception:
                    pass

        return await self._orchestrate_pipeline(
            raw_input_text=transcription,
            session_id=session_id,
            user_id=user_id,
            require_wake_word=require_wake_word,
            generate_audio=generate_audio,
            include_audio_base64=include_audio_base64,
            is_voice_input=True
        )

    async def _orchestrate_pipeline(
        self,
        raw_input_text: str,
        session_id: str,
        user_id: Optional[str],
        require_wake_word: Optional[bool],
        generate_audio: bool,
        include_audio_base64: bool,
        is_voice_input: bool
    ) -> YarbisResponse:
        transcription = raw_input_text.strip()
        should_require_wake = (
            require_wake_word if require_wake_word is not None
            else self.settings.REQUIRE_WAKE_WORD
        )

        # Si el audio no produjo ninguna transcripción inteligible (silencio / ruido)
        if not transcription:
            no_speech_text = "No logré escuchar con claridad. Por favor, inténtelo de nuevo."
            audio_url, audio_b64 = await self._synthesize_if_requested(
                no_speech_text, generate_audio and not should_require_wake, include_audio_base64
            )
            return YarbisResponse(
                action_type=ActionType.CONVERSATIONAL_QUERY,
                command=None,
                parameters={},
                text_response=no_speech_text,
                audio_url=audio_url,
                audio_base64=audio_b64,
                transcription="",
                session_id=session_id
            )

        # Paso 2: Validación y Normalización de Wake Word ("Yarbis")
        is_valid, cleaned_command = WakeWordValidator.process_transcript(
            transcript=transcription,
            require_wake_word=should_require_wake
        )

        # Si el wake word era obligatorio y no fue detectado:
        if not is_valid:
            rejected_text = "No detecté la orden de activación 'Yarbis'. Por favor mencione mi nombre al inicio."
            return YarbisResponse(
                action_type=ActionType.CONVERSATIONAL_QUERY,
                command=None,
                parameters={},
                text_response=rejected_text,
                audio_url=None,
                audio_base64=None,
                transcription=transcription,
                session_id=session_id
            )

        # Si el usuario solo dijo el wake word (ej. "Yarbis"), responder en modo escucha
        if not cleaned_command:
            acknowledgment = "¿A su orden? Indíqueme cómo puedo asistirle."
            audio_url, audio_b64 = await self._synthesize_if_requested(
                acknowledgment, generate_audio, include_audio_base64
            )
            return YarbisResponse(
                action_type=ActionType.CONVERSATIONAL_QUERY,
                command=None,
                parameters={},
                text_response=acknowledgment,
                audio_url=audio_url,
                audio_base64=audio_b64,
                transcription=transcription,
                session_id=session_id
            )

        # Paso 3: Recuperación de Historial Conversacional
        history = self.session.get_history(session_id)

        # Paso 4: Razonamiento LLM y Tool Calling
        (
            action_type,
            command,
            parameters,
            text_response,
            raw_tool_calls
        ) = await self.llm.decide_and_respond(
            user_text=cleaned_command,
            history=history
        )

        # Paso 5: Actualizar memoria de sesión
        self.session.add_user_message(session_id, cleaned_command)
        self.session.add_assistant_message(
            session_id=session_id,
            content=text_response,
            tool_calls=raw_tool_calls,
            command=command,
            parameters=parameters,
            action_type=action_type.value if hasattr(action_type, "value") else str(action_type)
        )

        # Paso 6: Síntesis Text-To-Speech (TTS)
        audio_url, audio_b64 = await self._synthesize_if_requested(
            text_response, generate_audio, include_audio_base64
        )

        # Paso 7: Conformar respuesta estructurada para Kotlin / Android
        return YarbisResponse(
            action_type=action_type,
            command=command,
            parameters=parameters,
            text_response=text_response,
            audio_url=audio_url,
            audio_base64=audio_b64,
            transcription=transcription if is_voice_input else None,
            session_id=session_id
        )

    async def _synthesize_if_requested(
        self,
        text: str,
        generate_audio: bool,
        include_audio_base64: bool = False
    ) -> tuple[Optional[str], Optional[str]]:
        """Sintetiza audio si fue solicitado y devuelve su URL (relativa por defecto) y Base64 opcional."""
        if not generate_audio or not text:
            return None, None

        try:
            filename = generate_audio_filename(".mp3")
            out_path = self.settings.AUDIO_DIR / filename
            await self.tts.synthesize(text, out_path)
            audio_url = get_audio_url(filename)
            audio_b64 = await file_to_base64(out_path) if include_audio_base64 else None
            return audio_url, audio_b64
        except Exception as e:
            logger.error(f"[Orchestrator TTS Error] No se pudo generar audio para '{text[:30]}': {e}")
            return None, None


_orchestrator_instance: Optional[YarbisOrchestrator] = None


def get_orchestrator() -> YarbisOrchestrator:
    """Inyector de dependencias singleton para YarbisOrchestrator."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = YarbisOrchestrator()
    return _orchestrator_instance
