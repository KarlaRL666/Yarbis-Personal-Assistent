import time
from typing import Any, Dict, List, Optional
from app.core.config import get_settings


class SessionHistory:
    """Estructura interna que almacena los mensajes, el contexto activo y la última actividad de una sesión."""

    def __init__(self, session_id: str, max_turns: int):
        self.session_id = session_id
        self.max_turns = max_turns
        self.messages: List[Dict[str, Any]] = []
        self.created_at: float = time.time()
        self.last_activity: float = time.time()
        self.context: Dict[str, Any] = {
            "last_topic": None,
            "last_entity": None,
            "last_action_type": None,
            "last_command": None,
            "last_parameters": {},
            "last_user_query": None,
            "last_assistant_response": None
        }

    def touch(self) -> None:
        """Actualiza la marca de tiempo de última interacción."""
        self.last_activity = time.time()

    def add_message(self, message: Dict[str, Any]) -> None:
        """Agrega un mensaje y aplica ventana deslizante si excede el límite."""
        self.touch()
        self.messages.append(message)
        # Cada turno son usualmente 2 mensajes: user + assistant (más tool calls si hubo)
        max_messages = self.max_turns * 3
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

    def update_context(self, updates: Dict[str, Any]) -> None:
        """Actualiza variables contextuales de la sesión para preguntas de seguimiento."""
        self.touch()
        for k, v in updates.items():
            if v is not None or k not in self.context:
                self.context[k] = v

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la sesión para inspección y depuración."""
        return {
            "session_id": self.session_id,
            "turns_count": len([m for m in self.messages if m.get("role") == "user"]),
            "messages_count": len(self.messages),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "context": dict(self.context),
            "messages": list(self.messages)
        }


class SessionService:
    """
    Gestor de memoria conversacional en memoria con política TTL y ventana deslizante.
    Almacena el historial y contexto atado al session_id para permitir
    preguntas de seguimiento ("¿y para mañana?") sin repetir el sujeto anterior.
    """

    def __init__(self):
        self._settings = get_settings()
        self._sessions: Dict[str, SessionHistory] = {}

    def _get_or_create(self, session_id: str) -> SessionHistory:
        """Obtiene o crea una sesión limpiando las que hayan expirado."""
        self._cleanup_expired()
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionHistory(
                session_id=session_id,
                max_turns=self._settings.SESSION_MAX_HISTORY_TURNS
            )
        return self._sessions[session_id]

    def _cleanup_expired(self) -> None:
        """Remueve sesiones inactivas mayores al TTL configurado."""
        now = time.time()
        ttl_seconds = self._settings.SESSION_TTL_MINUTES * 60
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if (now - session.last_activity) > ttl_seconds
        ]
        for sid in expired_ids:
            del self._sessions[sid]

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Devuelve una copia del historial de mensajes para el LLM."""
        session = self._get_or_create(session_id)
        return list(session.messages)

    def get_context(self, session_id: str) -> Dict[str, Any]:
        """Obtiene el contexto semántico actual atado al session_id."""
        session = self._get_or_create(session_id)
        return dict(session.context)

    def update_context(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Actualiza variables contextuales de la sesión."""
        session = self._get_or_create(session_id)
        session.update_context(updates)

    def add_user_message(self, session_id: str, content: str) -> None:
        """Registra el mensaje del usuario y actualiza la última consulta."""
        session = self._get_or_create(session_id)
        session.add_message({"role": "user", "content": content})
        session.update_context({"last_user_query": content})

    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        command: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        action_type: Optional[str] = None
    ) -> None:
        """
        Registra la respuesta de Yarbis (incluyendo llamadas a herramientas y
        sus respuestas requeridas por el schema de OpenAI) y preserva el contexto semántico.
        """
        session = self._get_or_create(session_id)
        msg: Dict[str, Any] = {"role": "assistant", "content": content}

        if tool_calls:
            msg["tool_calls"] = tool_calls
            session.add_message(msg)
            for tc in tool_calls:
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if tc_id:
                    session.add_message({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": '{"status": "success"}'
                    })
        else:
            session.add_message(msg)

        # Actualizar contexto atado a la sesión
        updates: Dict[str, Any] = {
            "last_assistant_response": content
        }
        if command:
            updates["last_command"] = command
        if parameters:
            updates["last_parameters"] = parameters
        if action_type:
            updates["last_action_type"] = action_type

        session.update_context(updates)

    def clear_session(self, session_id: str) -> bool:
        """Reinicia la memoria de una sesión específica."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Devuelve los detalles completos de la sesión si existe."""
        self._cleanup_expired()
        session = self._sessions.get(session_id)
        return session.to_dict() if session else None

    def list_active_sessions(self) -> List[str]:
        """Lista los identificadores de sesiones activas."""
        self._cleanup_expired()
        return list(self._sessions.keys())


_session_service_instance: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """Inyección de dependencias para SessionService."""
    global _session_service_instance
    if _session_service_instance is None:
        _session_service_instance = SessionService()
    return _session_service_instance
