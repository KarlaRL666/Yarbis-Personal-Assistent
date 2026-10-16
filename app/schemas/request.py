from typing import Optional
from pydantic import BaseModel, Field


class CommandProcessRequest(BaseModel):
    """Esquema para recepción directa de texto (POST /api/v1/command/process)."""
    text: str = Field(
        ...,
        description="Texto o comando dictado por el usuario",
        examples=["Yarbis, enciende la linterna", "¿Cuál es la distancia a la luna?"]
    )
    session_id: str = Field(
        default="default_session",
        description="Identificador de sesión para conservar historial y contexto"
    )
    user_id: Optional[str] = Field(
        default="user_mobile_01",
        description="Identificador del usuario móvil"
    )
    require_wake_word: Optional[bool] = Field(
        default=None,
        description="Sobrescribe la configuración global de requerir 'Yarbis' al inicio"
    )
    generate_audio: bool = Field(
        default=True,
        description="Indica si el backend debe sintetizar la respuesta con TTS"
    )
    include_audio_base64: bool = Field(
        default=False,
        description="Si es True, incluye el buffer del audio codificado en Base64 en la respuesta"
    )
