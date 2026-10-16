from enum import Enum


class ActionType(str, Enum):
    """Tipo principal de acción devuelta al frontend."""
    DEVICE_CONTROL = "device_control"
    CONVERSATIONAL_QUERY = "conversational_query"


class DeviceCommand(str, Enum):
    """Comandos estructurados de hardware y sistema operativo para clientes Kotlin / Android."""
    # Alarmas, temporizadores y recordatorios
    SET_ALARM = "set_alarm"
    CANCEL_ALARM = "cancel_alarm"
    SET_TIMER = "set_timer"
    CANCEL_TIMER = "cancel_timer"
    SET_REMINDER = "set_reminder"

    # Acciones de hardware
    SET_BRIGHTNESS = "set_brightness"
    SET_VOLUME = "set_volume"
    TOGGLE_FLASHLIGHT = "toggle_flashlight"
    TOGGLE_WIFI = "toggle_wifi"
    TOGGLE_BLUETOOTH = "toggle_bluetooth"

    # Aplicaciones y comunicación
    OPEN_APP = "open_app"
    MAKE_PHONE_CALL = "make_phone_call"
    SEND_MESSAGE = "send_message"

    # Multimedia y reproducción
    PLAY_MEDIA = "play_media"
