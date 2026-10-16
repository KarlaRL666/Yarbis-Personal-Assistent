from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# Modelos Pydantic para validación interna de parámetros de herramientas
# -------------------------------------------------------------------------

class SetAlarmParams(BaseModel):
    time: str = Field(..., description="Hora de la alarma en formato 24 horas 'HH:MM', ej. '07:30'")
    label: Optional[str] = Field(default=None, description="Etiqueta descriptiva de la alarma, ej. 'Despertador'")
    days: Optional[List[str]] = Field(default=None, description="Días de repetición, ej. ['lunes', 'viernes']")


class CancelAlarmParams(BaseModel):
    time: Optional[str] = Field(default=None, description="Hora de la alarma a cancelar en formato 'HH:MM'")
    label: Optional[str] = Field(default=None, description="Etiqueta de la alarma a cancelar")


class SetTimerParams(BaseModel):
    duration_seconds: int = Field(..., description="Duración del temporizador en segundos totales, ej. 300 para 5 minutos")
    label: Optional[str] = Field(default=None, description="Etiqueta del temporizador, ej. 'Pasta'")


class CancelTimerParams(BaseModel):
    label: Optional[str] = Field(default=None, description="Etiqueta del temporizador a cancelar")


class SetReminderParams(BaseModel):
    title: str = Field(..., description="Título o contenido del recordatorio")
    datetime_iso: str = Field(..., description="Fecha y hora objetivo en formato ISO 8601 o legible, ej. '2026-10-15T09:00:00'")
    notes: Optional[str] = Field(default=None, description="Notas adicionales")


class SetBrightnessParams(BaseModel):
    level_percent: int = Field(..., ge=0, le=100, description="Nivel de brillo en porcentaje de 0 a 100")


class SetVolumeParams(BaseModel):
    level_percent: int = Field(..., ge=0, le=100, description="Nivel de volumen en porcentaje de 0 a 100")
    stream: Optional[str] = Field(default="media", description="Canal de audio: 'media', 'ring', 'alarm', 'notification'")


class ToggleFlashlightParams(BaseModel):
    state: bool = Field(..., description="True para encender linterna, False para apagar")


class ToggleWifiParams(BaseModel):
    state: bool = Field(..., description="True para encender Wi-Fi, False para apagar")


class ToggleBluetoothParams(BaseModel):
    state: bool = Field(..., description="True para encender Bluetooth, False para apagar")


class OpenAppParams(BaseModel):
    app_name: str = Field(..., description="Nombre comercial de la aplicación, ej. 'Spotify', 'WhatsApp', 'YouTube', 'Cámara'")
    package_name: Optional[str] = Field(default=None, description="ID de paquete Android si se conoce, ej. 'com.spotify.music'")


class MakePhoneCallParams(BaseModel):
    contact_name: Optional[str] = Field(default=None, description="Nombre del contacto a llamar según agenda")
    phone_number: Optional[str] = Field(default=None, description="Número telefónico a marcar")


class SendMessageParams(BaseModel):
    recipient: str = Field(..., description="Nombre de contacto o número telefónico de destino")
    message_body: str = Field(..., description="Cuerpo del mensaje a redactar y enviar")
    app: Optional[str] = Field(default="whatsapp", description="Aplicación de mensajería: 'whatsapp', 'sms', 'telegram'")


class PlayMediaParams(BaseModel):
    query: str = Field(..., description="Canción, artista, álbum, playlist o video a reproducir, ej. 'Bohemian Rhapsody', 'Queen'")
    platform: str = Field(default="spotify", description="Plataforma de reproducción: 'spotify' o 'youtube'")
    media_type: Optional[str] = Field(default="track", description="Tipo de contenido opcional: 'track', 'artist', 'album', 'playlist', 'video'")


# -------------------------------------------------------------------------
# Definición OpenAI Function / Tool Calling Schema
# -------------------------------------------------------------------------

YARBIS_OPENAI_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "set_alarm",
            "description": "Configura una alarma en el reloj del dispositivo móvil del usuario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "string",
                        "description": "Hora de la alarma en formato 24 horas 'HH:MM' (ej. '06:45', '14:30')."
                    },
                    "label": {
                        "type": "string",
                        "description": "Etiqueta opcional de la alarma (ej. 'Entrenamiento', 'Reunión')."
                    },
                    "days": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Días de la semana si es recurrente (ej. ['lunes', 'martes'])."
                    }
                },
                "required": ["time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_alarm",
            "description": "Cancela o desactiva una alarma programada en el dispositivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "string",
                        "description": "Hora de la alarma que se desea cancelar."
                    },
                    "label": {
                        "type": "string",
                        "description": "Nombre de la alarma a cancelar."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": "Inicia una cuenta regresiva o temporizador en el dispositivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration_seconds": {
                        "type": "integer",
                        "description": "Duración total en segundos (ej. 300 para 5 minutos, 60 para 1 minuto, 3600 para 1 hora)."
                    },
                    "label": {
                        "type": "string",
                        "description": "Etiqueta descriptiva del temporizador."
                    }
                },
                "required": ["duration_seconds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_timer",
            "description": "Detiene o cancela el temporizador activo en el dispositivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Etiqueta del temporizador que se desea cancelar."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Crea un recordatorio o notificación programada en el calendario/recordatorios del dispositivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Título o asunto del recordatorio (ej. 'Comprar leche', 'Llamar al médico')."
                    },
                    "datetime_iso": {
                        "type": "string",
                        "description": "Fecha y hora objetivo (formato ISO 8601 o texto claro como '2026-10-15T15:00:00')."
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notas o detalles adicionales."
                    }
                },
                "required": ["title", "datetime_iso"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Ajusta el nivel de brillo de la pantalla del dispositivo móvil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level_percent": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Porcentaje de brillo deseado de 0 a 100."
                    }
                },
                "required": ["level_percent"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Ajusta el nivel de volumen de audio del dispositivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level_percent": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Nivel de volumen en porcentaje de 0 a 100."
                    },
                    "stream": {
                        "type": "string",
                        "enum": ["media", "ring", "alarm", "notification"],
                        "description": "Canal de audio a modificar (por defecto 'media')."
                    }
                },
                "required": ["level_percent"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_flashlight",
            "description": "Enciende o apaga la linterna/flash de la cámara del dispositivo móvil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "boolean",
                        "description": "true para encender la linterna, false para apagarla."
                    }
                },
                "required": ["state"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_wifi",
            "description": "Activa o desactiva la conexión Wi-Fi del dispositivo móvil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "boolean",
                        "description": "true para activar Wi-Fi, false para desactivarlo."
                    }
                },
                "required": ["state"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_bluetooth",
            "description": "Activa o desactiva la antena Bluetooth del dispositivo móvil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "boolean",
                        "description": "true para activar Bluetooth, false para desactivarlo."
                    }
                },
                "required": ["state"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Abre o lanza una aplicación instalada en el dispositivo móvil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Nombre de la aplicación (ej. 'Spotify', 'WhatsApp', 'YouTube', 'Instagram', 'Cámara', 'Calculadora')."
                    },
                    "package_name": {
                        "type": "string",
                        "description": "Nombre de paquete Android opcional (ej. 'com.google.android.youtube')."
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_phone_call",
            "description": "Inicia una llamada telefónica a un contacto o número específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {
                        "type": "string",
                        "description": "Nombre del contacto según la agenda telefónica (ej. 'Mamá', 'Carlos')."
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "Número de teléfono a marcar si fue provisto directamente."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Redacta y prepara el envío de un mensaje de texto o mensajería instantánea a un contacto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Destinatario del mensaje (nombre o número telefónico)."
                    },
                    "message_body": {
                        "type": "string",
                        "description": "Contenido textual del mensaje a enviar."
                    },
                    "app": {
                        "type": "string",
                        "enum": ["whatsapp", "sms", "telegram"],
                        "description": "Canal o app de mensajería (por defecto 'whatsapp')."
                    }
                },
                "required": ["recipient", "message_body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_media",
            "description": "Reproduce música, canciones, artistas, playlists o videos en Spotify o YouTube en el dispositivo móvil.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nombre de la canción, artista, álbum o video a reproducir (ej. 'Bohemian Rhapsody', 'Queen', 'Coldplay Yellow', 'música relajante')."
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["spotify", "youtube"],
                        "description": "Plataforma elegida para reproducir el contenido: 'spotify' o 'youtube'."
                    },
                    "media_type": {
                        "type": "string",
                        "enum": ["track", "artist", "album", "playlist", "video"],
                        "description": "Tipo de contenido multimedia opcional."
                    }
                },
                "required": ["query", "platform"]
            }
        }
    }
]
