import base64
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Set
import aiofiles
from fastapi import UploadFile
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Extensiones de audio típicas emitidas por clientes móviles Kotlin / Android (M4A/AAC, WAV, 3GP, AMR, MP4, Opus, OGG, MP3)
SUPPORTED_AUDIO_EXTENSIONS: Set[str] = {
    ".m4a", ".wav", ".aac", ".mp3", ".ogg", ".webm", ".flac", ".caf", ".3gp", ".amr", ".mp4", ".opus"
}


def is_supported_audio_extension(filename: str) -> bool:
    """Verifica si el archivo posee una extensión de audio soportada."""
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_AUDIO_EXTENSIONS


async def save_upload_to_temp(upload_file: UploadFile) -> Path:
    """
    Guarda un archivo subido vía multipart en un archivo temporal en disco.
    Conserva la extensión original (.m4a, .wav, .3gp, etc.) para que la API de Whisper
    identifique el códec de forma precisa.
    """
    settings = get_settings()
    raw_ext = Path(upload_file.filename or "audio.m4a").suffix.lower()
    extension = raw_ext if raw_ext in SUPPORTED_AUDIO_EXTENSIONS else ".m4a"

    temp_filename = f"upload_{uuid.uuid4().hex}{extension}"
    target_path = settings.AUDIO_DIR / temp_filename

    async with aiofiles.open(target_path, "wb") as out_file:
        while content := await upload_file.read(1024 * 64):  # 64 KB chunks
            await out_file.write(content)

    return target_path


def generate_audio_filename(extension: str = ".mp3") -> str:
    """Genera un nombre único para archivos sintetizados por TTS."""
    if not extension.startswith("."):
        extension = f".{extension}"
    return f"yarbis_{uuid.uuid4().hex[:12]}{extension}"


def get_audio_url(filename: str, relative: Optional[bool] = None) -> str:
    """
    Construye la URL del audio generado.
    Por defecto retorna una URL relativa (/api/v1/voice/audio/...) para que
    el cliente Kotlin le anteponga su propio baseUrl configurado (evita fallos de localhost
    en dispositivos físicos o emuladores de Android).
    """
    settings = get_settings()
    use_relative = relative if relative is not None else settings.USE_RELATIVE_AUDIO_URL

    if use_relative:
        return f"/api/v1/voice/audio/{filename}"

    base = settings.SERVER_BASE_URL.rstrip("/")
    return f"{base}/api/v1/voice/audio/{filename}"


async def file_to_base64(file_path: Path) -> Optional[str]:
    """
    Lee un archivo de audio del disco y lo codifica en Base64.
    Permite reproducción inmediata en Kotlin sin realizar una segunda petición HTTP.
    """
    if not file_path.exists():
        return None
    try:
        async with aiofiles.open(file_path, "rb") as audio_file:
            data = await audio_file.read()
            return base64.b64encode(data).decode("utf-8")
    except Exception as e:
        logger.error(f"[Audio Base64 Error] No se pudo convertir {file_path.name} a Base64: {e}")
        return None


def remove_file_silent(file_path: Path) -> None:
    """Elimina de forma segura y no bloqueante un archivo temporal de disco."""
    try:
        if file_path.exists() and file_path.is_file():
            file_path.unlink(missing_ok=True)
            logger.debug(f"[Cleanup] Archivo temporal eliminado: {file_path.name}")
    except Exception as e:
        logger.warning(f"[Cleanup Warning] No se pudo eliminar {file_path}: {e}")


def cleanup_old_audio_files(max_age_seconds: int = 3600) -> None:
    """Elimina archivos de audio huérfanos que excedan el tiempo máximo de vida."""
    settings = get_settings()
    now = time.time()
    try:
        if not settings.AUDIO_DIR.exists():
            return
        for file_path in settings.AUDIO_DIR.iterdir():
            if file_path.is_file() and not file_path.name.startswith("."):
                stat = file_path.stat()
                if (now - stat.st_mtime) > max_age_seconds:
                    remove_file_silent(file_path)
    except Exception as e:
        logger.warning(f"[Cleanup Old Audios Error] {e}")
