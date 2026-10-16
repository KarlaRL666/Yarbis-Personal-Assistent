import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from app.core.config import get_settings
from app.schemas.response import YarbisResponse
from app.services.orchestrator import YarbisOrchestrator, get_orchestrator
from app.utils.audio import (
    save_upload_to_temp,
    remove_file_silent,
    is_supported_audio_extension,
    SUPPORTED_AUDIO_EXTENSIONS
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Procesamiento de Voz y Audio"])


@router.post(
    "/process",
    response_model=YarbisResponse,
    status_code=status.HTTP_200_OK,
    summary="Procesar audio de voz desde la app móvil",
    description=(
        "Endpoint principal para clientes Kotlin / Android. Recibe el archivo de audio grabado por el micrófono "
        "(WAV, M4A, AAC, 3GP, AMR, MP3, WebM, etc.), ejecuta la transcripción STT (Whisper), "
        "valida el Wake Word 'Yarbis', consulta al LLM con Function Calling, "
        "sintetiza la respuesta por TTS y devuelve el JSON estandarizado con la acción a ejecutar. "
        "Limpia automáticamente el archivo temporal en segundo plano tras procesarlo."
    )
)
async def process_voice_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(
        ...,
        description="Archivo de audio grabado en Kotlin / Android (WAV, M4A, AAC, 3GP, AMR, MP3, etc.)"
    ),
    session_id: str = Form(
        default="default_session",
        description="ID de sesión para mantener el contexto conversacional"
    ),
    user_id: Optional[str] = Form(
        default=None,
        description="ID del usuario móvil"
    ),
    require_wake_word: Optional[bool] = Form(
        default=None,
        description="Sobrescribe el requerimiento de detectar 'Yarbis' al inicio del audio"
    ),
    generate_audio: bool = Form(
        default=True,
        description="Indica si se debe generar y retornar el stream o buffer de audio TTS"
    ),
    include_audio_base64: bool = Form(
        default=True,
        description="Si es True, devuelve el buffer en Base64 para reproducción instantánea en Kotlin sin segunda petición"
    ),
    orchestrator: YarbisOrchestrator = Depends(get_orchestrator)
) -> YarbisResponse:
    """Procesa un archivo de audio grabado y enviado desde el cliente Kotlin / Android."""
    logger.info(
        f"[POST /voice/process] Recibido archivo de audio: '{file.filename}' "
        f"({file.content_type}) para sesión: '{session_id}'"
    )

    # Validar extensión para Whisper y evitar subir archivos no multimedia
    if file.filename and not is_supported_audio_extension(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato de archivo '{file.filename}' no soportado. "
                f"Extensiones válidas: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            )
        )

    # Guardar en archivo temporal para Whisper preservando el códec original
    temp_path = await save_upload_to_temp(file)

    try:
        response = await orchestrator.process_voice_audio(
            audio_path=temp_path,
            session_id=session_id,
            user_id=user_id,
            require_wake_word=require_wake_word,
            generate_audio=generate_audio,
            include_audio_base64=include_audio_base64
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[POST /voice/process Error] Fallo durante el flujo de audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno procesando el audio: {str(e)}"
        )
    finally:
        # Garantizar que el archivo temporal subido siempre se elimine del disco
        background_tasks.add_task(remove_file_silent, temp_path)


@router.get(
    "/audio/{filename}",
    summary="Obtener archivo de audio generado por TTS",
    description="Permite al cliente móvil en Kotlin / Android reproducir o transmitir el audio sintetizado.",
    response_class=FileResponse
)
async def get_audio_file(filename: str):
    """Descarga o streaming del archivo de audio generado."""
    settings = get_settings()
    # Prevenir ataques de Directory Traversal
    safe_filename = Path(filename).name
    file_path = settings.AUDIO_DIR / safe_filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo de audio '{safe_filename}' no encontrado."
        )

    # Determinar Content-Type
    media_type = "audio/mpeg" if safe_filename.endswith(".mp3") else "audio/wav"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=safe_filename
    )
