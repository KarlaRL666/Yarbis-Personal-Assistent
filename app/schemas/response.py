from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.schemas.common import ActionType


class YarbisResponse(BaseModel):
    """
    Contrato estándar de respuesta frontend-backend para clientes Kotlin / Android.
    """
    action_type: ActionType = Field(
        ...,
        description="Tipo de acción: 'device_control' o 'conversational_query'"
    )
    command: Optional[str] = Field(
        default=None,
        description="Nombre de la acción de hardware/sistema, o null en consultas generales"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parámetros estructurados para que el cliente Kotlin / Android ejecute el comando en el dispositivo"
    )
    text_response: str = Field(
        ...,
        description="Respuesta verbal concisa de Yarbis para el usuario"
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="URL relativa (/api/v1/voice/audio/...) o absoluta para streaming de audio"
    )
    audio_base64: Optional[str] = Field(
        default=None,
        description="Buffer de audio codificado en Base64 para reproducción inmediata sin segunda petición HTTP"
    )
    # Metadatos auxiliares útiles para depuración en la app móvil
    transcription: Optional[str] = Field(
        default=None,
        description="Transcripción del audio recibido si provino de STT"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="ID de la sesión activa"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "action_type": "device_control",
                "command": "toggle_flashlight",
                "parameters": {
                    "state": True
                },
                "text_response": "Encendiendo la linterna.",
                "audio_url": "http://10.0.2.2:8000/api/v1/voice/audio/response_123.mp3",
                "transcription": "Yarbis enciende la linterna",
                "session_id": "session_kotlin_01"
            }
        }
    }
