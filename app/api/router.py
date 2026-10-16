from fastapi import APIRouter
from app.api.v1 import command, session, voice

api_router = APIRouter(prefix="/api/v1")

# Rutas versión 1
api_router.include_router(voice.router)
api_router.include_router(command.router)
api_router.include_router(session.router)


@api_router.get("/health", tags=["Salud del Sistema"], summary="Verificar estado de Yarbis")
async def health_check():
    """Endpoint de comprobación de salud para conectividad de clientes Kotlin / Android."""
    return {
        "status": "online",
        "assistant": "Yarbis",
        "version": "1.0.0",
        "ready": True
    }
