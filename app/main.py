import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.router import api_router
from app.core.config import get_settings
from app.utils.audio import cleanup_old_audio_files

# Configurar logging profesional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("yarbis.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación Yarbis."""
    settings = get_settings()
    logger.info(f"=== Iniciando {settings.APP_NAME} en entorno [{settings.APP_ENV}] ===")
    logger.info(f"Configuración de asistente: Wake Word = '{settings.ASSISTANT_NAME}'")
    logger.info(f"Requerir Wake Word: {settings.REQUIRE_WAKE_WORD}")
    logger.info(f"Proveedor STT: {settings.STT_PROVIDER} | Proveedor TTS: {settings.TTS_PROVIDER}")
    logger.info(f"Directorio de audio estático: {settings.AUDIO_DIR}")

    # Delegación de la creación de las carpetas de almacenamiento al lifespan
    settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Limpieza inicial de archivos temporales antiguos
    cleanup_old_audio_files(max_age_seconds=1800)

    yield

    logger.info("=== Apagando Yarbis Backend. Liberando recursos... ===")


def create_application() -> FastAPI:
    """Fábrica de la aplicación FastAPI."""
    settings = get_settings()
    settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="Yarbis Voice Assistant API",
        description=(
            "Backend asíncrono y modular para el asistente de voz móvil Yarbis (Kotlin / Android). "
            "Incluye transcripción de audio (STT), validación de Wake Word, "
            "razonamiento inteligente con Function Calling / Tool Use para control de hardware/SO, "
            "y síntesis de voz (TTS)."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # Configuración de CORS para permitir solicitudes desde emuladores y dispositivos móviles
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Montar directorio estático para servir audios directamente si es requerido
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

    # Incluir enrutadores de la API
    app.include_router(api_router)

    @app.get("/", tags=["Información"])
    async def root():
        return {
            "name": "Yarbis Backend",
            "version": "1.0.0",
            "status": "active",
            "docs": "/docs",
            "endpoints": {
                "voice_process": "/api/v1/voice/process",
                "command_process": "/api/v1/command/process",
                "health": "/api/v1/health"
            }
        }

    return app


app = create_application()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
