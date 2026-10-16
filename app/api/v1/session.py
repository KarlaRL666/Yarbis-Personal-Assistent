import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.session_service import SessionService, get_session_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["Gestión de Memoria y Contexto"])


@router.get(
    "/{session_id}/history",
    status_code=status.HTTP_200_OK,
    summary="Obtener historial conversacional de una sesión",
    description="Retorna la lista de mensajes (turnos del usuario y de Yarbis) asociados al session_id."
)
async def get_session_history(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> Dict[str, Any]:
    """Obtiene el historial de conversación completo de la sesión."""
    info = session_service.get_session_info(session_id)
    if not info:
        return {
            "session_id": session_id,
            "turns_count": 0,
            "messages_count": 0,
            "messages": [],
            "context": {}
        }
    return info


@router.get(
    "/{session_id}/context",
    status_code=status.HTTP_200_OK,
    summary="Obtener contexto semántico activo",
    description="Retorna el contexto semántico (último tema, entidad, comando y parámetros) para seguimiento."
)
async def get_session_context(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> Dict[str, Any]:
    """Obtiene el contexto semántico activo atado al session_id."""
    context = session_service.get_context(session_id)
    return {
        "session_id": session_id,
        "context": context
    }


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Reiniciar memoria de la sesión",
    description="Borra todo el historial y contexto almacenado para el session_id especificado."
)
async def clear_session_memory(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> Dict[str, Any]:
    """Limpia la memoria conversacional de la sesión."""
    cleared = session_service.clear_session(session_id)
    return {
        "session_id": session_id,
        "cleared": cleared,
        "message": f"Memoria de sesión '{session_id}' reiniciada correctamente."
    }


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Listar sesiones activas",
    description="Retorna los IDs de las sesiones conversacionales almacenadas actualmente en memoria."
)
async def list_sessions(
    session_service: SessionService = Depends(get_session_service)
) -> Dict[str, Any]:
    """Lista las sesiones activas en el backend."""
    sessions = session_service.list_active_sessions()
    return {
        "active_sessions_count": len(sessions),
        "sessions": sessions
    }
