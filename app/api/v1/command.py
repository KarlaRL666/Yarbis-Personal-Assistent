import logging
from fastapi import APIRouter, Depends, status
from app.schemas.request import CommandProcessRequest
from app.schemas.response import YarbisResponse
from app.services.orchestrator import YarbisOrchestrator, get_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/command", tags=["Comandos de Texto"])


@router.post(
    "/process",
    response_model=YarbisResponse,
    status_code=status.HTTP_200_OK,
    summary="Procesar comando de texto directo",
    description=(
        "Endpoint para pruebas rápidas y modo texto en clientes Kotlin / Android. "
        "Recibe el texto, evalúa el Wake Word (si está configurado), "
        "consulta el LLM con Tool Calling y retorna la orden de control de dispositivo "
        "o la respuesta conversacional, junto con el audio sintetizado."
    )
)
async def process_text_command(
    request: CommandProcessRequest,
    orchestrator: YarbisOrchestrator = Depends(get_orchestrator)
) -> YarbisResponse:
    """Procesa una orden en formato de texto."""
    logger.info(f"[POST /command/process] Recibido texto: '{request.text}' (session: {request.session_id})")
    response = await orchestrator.process_text_command(
        text=request.text,
        session_id=request.session_id,
        user_id=request.user_id,
        require_wake_word=request.require_wake_word,
        generate_audio=request.generate_audio,
        include_audio_base64=request.include_audio_base64
    )
    return response
