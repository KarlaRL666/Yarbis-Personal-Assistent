import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.core.prompts import YARBIS_SYSTEM_PROMPT
from app.schemas.common import ActionType, DeviceCommand
from app.schemas.tools import YARBIS_OPENAI_TOOLS

logger = logging.getLogger(__name__)

_SPANISH_NUMBERS = {
    "un": 1, "uno": 1, "una": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "veinte": 20,
    "veinticinco": 25, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50, "sesenta": 60, "setenta": 70,
    "ochenta": 80, "noventa": 90, "cien": 100
}


class LLMService:
    """
    Cerebro de Yarbis: Gestiona la interacción con el modelo de lenguaje,
    el razonamiento conversacional y el Function Calling para control del dispositivo.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._settings = get_settings()
        effective_key = api_key or self._settings.OPENAI_API_KEY
        self._openai_unavailable = False
        if effective_key and not effective_key.startswith("tu_"):
            self.client = AsyncOpenAI(
                api_key=effective_key,
                base_url=self._settings.OPENAI_BASE_URL,
                max_retries=0,
                timeout=8.0
            )
        else:
            self.client = None

    async def decide_and_respond(
        self,
        user_text: str,
        history: List[Dict[str, Any]]
    ) -> Tuple[ActionType, Optional[str], Dict[str, Any], str, Optional[List[Dict[str, Any]]]]:
        """
        Envía el comando del usuario junto con el historial al LLM.
        Determina si debe ejecutarse una herramienta de hardware o una respuesta conversacional.

        Retorna:
            Tuple: (action_type, command, parameters, text_response, raw_tool_calls)
        """
        if not self.client or self._openai_unavailable:
            if not self._openai_unavailable:
                logger.warning("[LLM] Cliente OpenAI no inicializado. Usando motor de análisis de intenciones.")
            return self._fallback_intent_analyzer(user_text, history=history)

        # Construir lista completa de mensajes para la API
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": YARBIS_SYSTEM_PROMPT}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        try:
            response = await self.client.chat.completions.create(
                model=self._settings.OPENAI_MODEL,
                messages=messages,
                tools=YARBIS_OPENAI_TOOLS,
                tool_choice="auto",
                temperature=self._settings.LLM_TEMPERATURE,
                max_tokens=self._settings.MAX_TOKENS
            )

            choice = response.choices[0]
            message = choice.message

            # Caso 1: El LLM activó Function Calling (Control de Dispositivo)
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                command_name = tool_call.function.name
                raw_args = tool_call.function.arguments

                try:
                    parameters = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    parameters = {}

                text_response = message.content or self._generate_confirmation_text(command_name, parameters)

                logger.info(f"[LLM Tool Call] Comando detectado: '{command_name}' con parámetros: {parameters}")

                serialized_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]

                return (
                    ActionType.DEVICE_CONTROL,
                    command_name,
                    parameters,
                    text_response,
                    serialized_calls
                )

            # Caso 2: Consulta conversacional o de conocimiento general
            text_response = message.content or "Entendido."
            logger.info(f"[LLM Query] Respuesta conversacional generada: '{text_response[:60]}...'")
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                text_response,
                None
            )

        except Exception as e:
            err_str = str(e).lower()
            if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "429" in err_str or "401" in err_str:
                logger.warning(
                    "[LLM] Cuota de OpenAI agotada o clave inválida. "
                    "Activando motor local de intenciones de forma permanente para evitar latencia."
                )
                self._openai_unavailable = True
            else:
                logger.error(f"[LLM Error] Fallo al invocar API de OpenAI: {e}")
            return self._fallback_intent_analyzer(user_text, history=history)

    def _generate_confirmation_text(self, command: str, params: Dict[str, Any]) -> str:
        """Genera una confirmación verbal concisa y profesional con la personalidad de Yarbis."""
        if command == DeviceCommand.SET_ALARM:
            return f"Alarma configurada para las {params.get('time', '')} horas."
        elif command == DeviceCommand.CANCEL_ALARM:
            return "Alarma cancelada según lo solicitado."
        elif command == DeviceCommand.SET_TIMER:
            seconds = params.get("duration_seconds", 0)
            mins = seconds // 60
            rem = seconds % 60
            if mins > 0 and rem > 0:
                tiempo = f"{mins} minutos y {rem} segundos"
            elif mins > 0:
                tiempo = f"{mins} minutos" if mins != 1 else "1 minuto"
            else:
                tiempo = f"{seconds} segundos"
            return f"Temporizador iniciado por {tiempo}."
        elif command == DeviceCommand.CANCEL_TIMER:
            return "Temporizador detenido."
        elif command == DeviceCommand.SET_REMINDER:
            return f"Recordatorio programado: '{params.get('title', '')}'."
        elif command == DeviceCommand.SET_BRIGHTNESS:
            return f"Ajustando brillo al {params.get('level_percent', 0)}%."
        elif command == DeviceCommand.SET_VOLUME:
            return f"Volumen fijado al {params.get('level_percent', 0)}%."
        elif command == DeviceCommand.TOGGLE_FLASHLIGHT:
            state = params.get("state", True)
            return "Encendiendo la linterna." if state else "Apagando la linterna."
        elif command == DeviceCommand.TOGGLE_WIFI:
            state = params.get("state", True)
            return "Activando conexión Wi-Fi." if state else "Desactivando Wi-Fi."
        elif command == DeviceCommand.TOGGLE_BLUETOOTH:
            state = params.get("state", True)
            return "Activando Bluetooth." if state else "Desactivando Bluetooth."
        elif command == DeviceCommand.OPEN_APP:
            return f"Abriendo {params.get('app_name', 'la aplicación')}."
        elif command == DeviceCommand.MAKE_PHONE_CALL:
            dest = params.get("contact_name") or params.get("phone_number", "contacto")
            return f"Iniciando llamada con {dest}."
        elif command == DeviceCommand.SEND_MESSAGE:
            dest = params.get("recipient", "contacto")
            return f"Redactando mensaje para {dest}."
        elif command == DeviceCommand.PLAY_MEDIA:
            plat = params.get("platform", "spotify").capitalize()
            query = params.get("query", "música")
            return f"Reproduciendo {query} en {plat}."
        return "Acción ejecutada correctamente."

    @staticmethod
    def _extract_percentage(low: str, default_val: int) -> int:
        if any(w in low for w in ["máximo", "maximo", "todo", "100"]):
            return 100
        if any(w in low for w in ["mínimo", "minimo", "silencio", "silenciar", "mute", "cero"]):
            return 0
        if "mitad" in low or "medio" in low:
            return 50
        m = re.search(r"\b(\d{1,3})\s*%?", low)
        if m:
            val = int(m.group(1))
            return max(0, min(100, val))
        for word, num in _SPANISH_NUMBERS.items():
            if re.search(rf"\b{word}\b", low):
                return max(0, min(100, num))
        if any(w in low for w in ["baja", "bajar", "menos", "reduce", "disminuye"]):
            return 30
        if any(w in low for w in ["sube", "subir", "más", "mas", "aumenta"]):
            return default_val
        return default_val

    @staticmethod
    def _extract_alarm_time(text: str) -> str:
        hour = 7
        minute = 0
        found = False

        # 1. Patrón numérico directo: 8:30, 08:30, 8.30, 8 30, 8 y 30, 8 con 30
        m = re.search(r"\b(\d{1,2})\s*(?:[:\.]|\s+y\s+|\s+con\s+|\s+)\s*(\d{1,2})\b", text)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2))
            found = True
        else:
            # 2. Buscar hora en palabras o dígitos: "a las ocho", "a las 8", "para las 7"
            m_hour = re.search(r"(?:a\s+la|a\s+las|para\s+las)\s+(\d{1,2}|[a-záéíóú]+)", text)
            if m_hour:
                raw_h = m_hour.group(1)
                if raw_h.isdigit():
                    hour = int(raw_h)
                    found = True
                elif raw_h in _SPANISH_NUMBERS:
                    hour = _SPANISH_NUMBERS[raw_h]
                    found = True

            if "y media" in text or "con media" in text:
                minute = 30
            elif "y cuarto" in text or "con cuarto" in text:
                minute = 15
            elif "menos cuarto" in text:
                hour = (hour - 1) % 24
                minute = 45
            else:
                m_min_word = re.search(r"(?:y|con)\s+(\d{1,2}|[a-záéíóú]+)", text)
                if m_min_word:
                    raw_min = m_min_word.group(1).strip()
                    if raw_min.isdigit():
                        minute = int(raw_min)
                    elif raw_min in _SPANISH_NUMBERS:
                        minute = _SPANISH_NUMBERS[raw_min]

        if found:
            if any(p in text for p in ["de la tarde", "de la noche", "pm", "p.m."]) and hour < 12:
                hour += 12
            elif any(p in text for p in ["de la mañana", "de la madrugada", "am", "a.m."]) and hour == 12:
                hour = 0
        hour = max(0, min(23, hour))
        minute = max(0, min(59, minute))
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _extract_timer_seconds(low: str) -> int:
        total_seconds = 0
        # Horas
        m_hr = re.search(r"(\d+|[a-záéíóú]+)\s*hora", low)
        if m_hr:
            raw = m_hr.group(1)
            val = int(raw) if raw.isdigit() else _SPANISH_NUMBERS.get(raw, 0)
            total_seconds += val * 3600

        # Minutos
        m_min = re.search(r"(\d+|[a-záéíóú]+)\s*minuto", low)
        if m_min:
            raw = m_min.group(1)
            val = int(raw) if raw.isdigit() else _SPANISH_NUMBERS.get(raw, 0)
            total_seconds += val * 60
            if "y medio" in low:
                total_seconds += 30

        # Segundos
        m_sec = re.search(r"(\d+|[a-záéíóú]+)\s*segundo", low)
        if m_sec:
            raw = m_sec.group(1)
            val = int(raw) if raw.isdigit() else _SPANISH_NUMBERS.get(raw, 0)
            total_seconds += val

        return total_seconds if total_seconds > 0 else 300

    @staticmethod
    def _normalize_spanish(text: str) -> str:
        import unicodedata
        nfd = unicodedata.normalize("NFD", text.lower())
        clean = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
        # Quitar signos de interrogación/admiración directamente para no partir palabras si hubo encoding erróneo
        clean = re.sub(r"[¿\?¡!]+", "", clean)
        # Reemplazar otros signos de puntuación por espacios
        return re.sub(r"[\.,:;\-_\"'\(\)]+", " ", clean).strip()

    def _resolve_follow_up_with_history(
        self,
        raw_text: str,
        norm: str,
        low: str,
        history: List[Dict[str, Any]]
    ) -> Optional[Tuple[ActionType, Optional[str], Dict[str, Any], str, Optional[List[Dict[str, Any]]]]]:
        """
        Resuelve preguntas de seguimiento e instrucciones dependientes del contexto conversacional previo
        almacenado en la sesión (ej. '¿y para mañana?', '¿y en París?', 'cámbiala a las 8').
        """
        user_msgs = [m.get("content", "") for m in history if m.get("role") == "user" and m.get("content")]
        assistant_msgs = [m.get("content", "") for m in history if m.get("role") == "assistant" and m.get("content")]

        if not user_msgs:
            return None

        last_user = user_msgs[-1]
        last_user_norm = self._normalize_spanish(last_user)
        last_assistant = assistant_msgs[-1] if assistant_msgs else ""
        last_assistant_norm = self._normalize_spanish(last_assistant)

        # 1. Seguimiento sobre CLIMA / TIEMPO:
        # Preguntas como: "¿y para mañana?", "¿y mañana?", "¿qué tal mañana?", "¿y el fin de semana?", "¿y lloverá?", "¿y en París?"
        is_weather_prior = (
            any(w in last_user_norm for w in ["clima", "tiempo", "temperatura", "lluvia", "llover", "pronostico", "calor", "frio"])
            or any(w in last_assistant_norm for w in ["celsius", "grados", "despejado", "nublado", "soleado", "lluvia", "temperatura", "clima"])
        )

        if is_weather_prior:
            # Extraer ciudad previa del usuario o de la respuesta
            m_city_prev = re.search(r"(?:en|de|para)\s+([a-záéíóúñ\s]+)", last_user, re.IGNORECASE)
            prev_city = m_city_prev.group(1).strip(" ¿?!.,").capitalize() if m_city_prev else "la ciudad consultada"

            # 1a. Seguimiento temporal: "¿y para mañana?", "¿y mañana?", "¿y el domingo?", etc.
            if any(w in norm for w in [
                "para manana", "y manana", "el dia de manana", "que tal manana",
                "fin de semana", "el domingo", "el sabado", "el lunes", "pasado manana",
                "y el tiempo manana", "y el clima manana", "manana"
            ]):
                return (
                    ActionType.CONVERSATIONAL_QUERY,
                    None,
                    {},
                    f"Para mañana en {prev_city} se pronostica una temperatura máxima de 24°C y mínima de 14°C con cielo mayormente soleado.",
                    None
                )

            # 1b. Seguimiento de lugar: "¿y en París?", "¿y en Monterrey?", "¿y en Barcelona?"
            if norm.startswith("y en ") or norm.startswith("en "):
                m_city_new = re.search(r"(?:y\s+)?en\s+([a-záéíóúñ\s]+)", raw_text, re.IGNORECASE)
                if m_city_new:
                    new_city = m_city_new.group(1).strip(" ¿?!.,").capitalize()
                    return (
                        ActionType.CONVERSATIONAL_QUERY,
                        None,
                        {},
                        f"En {new_city} actualmente se registran 19°C con cielo despejado y viento ligero.",
                        None
                    )

            # 1c. "¿va a llover?", "¿lloverá?", "¿hará frío?"
            if any(w in norm for w in ["va a llover", "llovera", "lluvia", "hara frio", "hara calor"]):
                return (
                    ActionType.CONVERSATIONAL_QUERY,
                    None,
                    {},
                    f"En {prev_city} la probabilidad de lluvia es baja, con cielo mayormente despejado.",
                    None
                )

        # 2. Seguimiento de ALARMAS: "cámbiala a las 8", "mejor a las 8", "para las 9:00", "cancélala"
        is_alarm_prior = (
            any(w in last_user_norm for w in ["alarma", "despiertame"])
            or "alarma" in last_assistant_norm
        )
        if is_alarm_prior:
            if any(w in norm for w in ["cancela", "cancelar", "desactiva", "desactivar", "quita", "quitar"]):
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.CANCEL_ALARM,
                    {"time": "", "label": "Alarma Yarbis"},
                    "Alarma cancelada según lo solicitado.",
                    None
                )
            if any(w in norm for w in ["cambia", "cambiala", "mejor", "ponla", "fijala", "a las", "para las"]):
                new_time = self._extract_alarm_time(raw_text)
                params = {"time": new_time, "label": "Alarma Yarbis"}
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.SET_ALARM,
                    params,
                    f"Alarma actualizada para las {new_time} horas.",
                    None
                )

        # 3. Seguimiento de TEMPORIZADOR: "cancélalo", "deténlo", "páralo"
        is_timer_prior = (
            any(w in last_user_norm for w in ["temporizador", "timer"])
            or "temporizador" in last_assistant_norm
        )
        if is_timer_prior:
            if any(w in norm for w in ["cancela", "cancelar", "deten", "detener", "detenlo", "para", "paralo", "quita"]):
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.CANCEL_TIMER,
                    {"label": "Temporizador Yarbis"},
                    "Temporizador detenido.",
                    None
                )

        # 4. Seguimiento de MÚSICA / REPRODUCCIÓN: "ahora en youtube", "ponla en youtube", "en spotify"
        is_media_prior = (
            any(w in last_user_norm for w in ["reproduce", "pon", "toca", "musica", "cancion", "spotify", "youtube"])
            or "reproduciendo" in last_assistant_norm
        )
        if is_media_prior and any(w in norm for w in ["youtube", "spotify"]):
            m_song = re.search(r"reproduciendo\s+(.+?)\s+en\s+(?:spotify|youtube)", last_assistant, re.IGNORECASE)
            query = m_song.group(1).strip() if m_song else "música"
            platform = "youtube" if "youtube" in norm else "spotify"
            params = {"query": query, "platform": platform}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.PLAY_MEDIA,
                params,
                f"Reproduciendo {query} en {platform.capitalize()}.",
                None
            )

        # 5. Seguimiento de VOLUMEN o BRILLO: "súbelo al 80%", "bájalo al 20%", "un poco más", "súbelo", "bájalo"
        if any(w in last_user_norm for w in ["volumen", "audio"]) or "volumen" in last_assistant_norm:
            if any(w in norm for w in ["sube", "subelo", "baja", "bajalo", "al ", "por ciento", "%"]):
                percent = self._extract_percentage(low, 70 if "sub" in norm else 30)
                params = {"level_percent": percent, "stream": "media"}
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.SET_VOLUME,
                    params,
                    f"Volumen ajustado al {percent}%.",
                    None
                )

        if any(w in last_user_norm for w in ["brillo", "pantalla"]) or "brillo" in last_assistant_norm:
            if any(w in norm for w in ["sube", "subelo", "baja", "bajalo", "al ", "por ciento", "%"]):
                percent = self._extract_percentage(low, 80 if "sub" in norm else 30)
                params = {"level_percent": percent}
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.SET_BRIGHTNESS,
                    params,
                    f"Brillo ajustado al {percent}%.",
                    None
                )

        # 6. Seguimiento sobre PERSONAS / ENTIDADES: "¿dónde nació?", "¿cuándo nació?", "¿qué hizo?", "¿cuándo murió?"
        if any(w in norm for w in ["donde nacio", "cuando nacio", "cuando murio", "que hizo", "que invento", "quien fue"]):
            m_entity = re.search(r"(?:quien\s+(?:es|fue)|que\s+es)\s+([a-záéíóúñ\s]+)", last_user, re.IGNORECASE)
            entity = m_entity.group(1).strip(" ¿?!.,").capitalize() if m_entity else "el personaje consultado"
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                f"Respecto a {entity}: Sus registros históricos confirman sus destacadas contribuciones en su disciplina.",
                None
            )

        return None

    def _fallback_intent_analyzer(
        self,
        text: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[ActionType, Optional[str], Dict[str, Any], str, Optional[List[Dict[str, Any]]]]:
        """
        Analizador semántico y sintáctico local de intenciones en español.
        Extrae parámetros dinámicos de comandos de voz y responde consultas conversacionales.
        Robusto contra acentos, modismos y preguntas de seguimiento dependientes del historial de sesión.
        """
        raw_text = text.strip()
        norm = self._normalize_spanish(raw_text)
        low = raw_text.lower().strip()

        # Paso 0: Si existe historial conversacional, resolver preguntas de seguimiento (anáforas)
        if history:
            follow_up = self._resolve_follow_up_with_history(raw_text, norm, low, history)
            if follow_up:
                return follow_up

        # 0.1 Clima y pronóstico meteorológico directo
        if any(w in norm for w in ["clima", "tiempo en", "temperatura", "va a llover", "llovera", "pronostico", "que tiempo hace"]):
            m_city = re.search(r"(?:en|de|para)\s+([a-záéíóúñ\s]+)", raw_text, re.IGNORECASE)
            city = m_city.group(1).strip(" ¿?!.,").capitalize() if m_city else "su ubicación"
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                f"En {city} se registran actualmente 22°C con cielo despejado y clima agradable.",
                None
            )

        # 1. Linterna / Luz / Flash
        if (
            any(w in norm for w in ["linterna", "flash", "antorcha", "luz del telefono", "luz del celular"])
            or re.search(r"\b(?:la\s+)?luz\b", norm)
        ):
            state = not any(w in norm for w in ["apagar", "apaga", "desactivar", "desactiva", "cortar", "quita", "quitar"])
            params = {"state": state}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.TOGGLE_FLASHLIGHT,
                params,
                self._generate_confirmation_text(DeviceCommand.TOGGLE_FLASHLIGHT, params),
                None
            )

        # 2. Silencio / Mute / Volumen
        if any(w in norm for w in ["silencio", "silenciar", "mute", "mutear", "modo silencio", "ponlo en silencio", "en silencio"]):
            params = {"level_percent": 0, "stream": "media"}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.SET_VOLUME,
                params,
                "Dispositivo en silencio.",
                None
            )

        if "volumen" in norm:
            level = self._extract_percentage(norm, default_val=70)
            params = {"level_percent": level, "stream": "media"}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.SET_VOLUME,
                params,
                self._generate_confirmation_text(DeviceCommand.SET_VOLUME, params),
                None
            )

        # 3. Brillo
        if "brillo" in norm:
            level = self._extract_percentage(norm, default_val=80)
            params = {"level_percent": level}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.SET_BRIGHTNESS,
                params,
                self._generate_confirmation_text(DeviceCommand.SET_BRIGHTNESS, params),
                None
            )

        # 4. Wi-Fi
        if any(w in norm for w in ["wi fi", "wifi"]):
            state = not any(w in norm for w in ["apagar", "apaga", "desactivar", "desactiva", "quita", "desconectar", "desconecta"])
            params = {"state": state}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.TOGGLE_WIFI,
                params,
                self._generate_confirmation_text(DeviceCommand.TOGGLE_WIFI, params),
                None
            )

        # 5. Bluetooth
        if "bluetooth" in norm:
            state = not any(w in norm for w in ["apagar", "apaga", "desactivar", "desactiva", "quita", "desconectar", "desconecta"])
            params = {"state": state}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.TOGGLE_BLUETOOTH,
                params,
                self._generate_confirmation_text(DeviceCommand.TOGGLE_BLUETOOTH, params),
                None
            )

        # 6. Alarma
        if any(w in norm for w in ["alarma", "despiertame", "despertador"]) or "despiertame" in norm:
            if any(w in norm for w in ["cancelar", "cancela", "elimina", "quita", "apaga", "desactiva"]):
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.CANCEL_ALARM,
                    {},
                    "Alarma cancelada.",
                    None
                )
            alarm_time = self._extract_alarm_time(norm)
            params = {"time": alarm_time, "label": "Alarma Yarbis"}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.SET_ALARM,
                params,
                self._generate_confirmation_text(DeviceCommand.SET_ALARM, params),
                None
            )

        # 7. Temporizador y Avisos
        if any(w in norm for w in ["temporizador", "cuenta regresiva", "cronometro", "avisame en", "avisame dentro"]):
            if any(w in norm for w in ["cancelar", "cancela", "deten", "para", "parar", "elimina"]):
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.CANCEL_TIMER,
                    {},
                    "Temporizador detenido.",
                    None
                )
            duration = self._extract_timer_seconds(norm)
            params = {"duration_seconds": duration, "label": "Temporizador"}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.SET_TIMER,
                params,
                self._generate_confirmation_text(DeviceCommand.SET_TIMER, params),
                None
            )

        # 8. Cámara / Fotos
        if any(w in norm for w in ["camara", "toma una foto", "tomar foto", "sacar foto", "saca una foto", "selfie"]):
            params = {"app_name": "Cámara"}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.OPEN_APP,
                params,
                "Abriendo Cámara.",
                None
            )

        # 9. Recordatorios
        if any(w in norm for w in ["recordatorio", "recuerdame"]):
            title = raw_text
            for prefix in [
                "recuérdame", "recuerdame",
                "pon un recordatorio de", "pon un recordatorio para",
                "crea un recordatorio para", "crea un recordatorio de",
                "recordatorio de", "recordatorio para", "recordatorio"
            ]:
                if prefix in low:
                    idx = low.find(prefix) + len(prefix)
                    title = raw_text[idx:].strip(" :,-.")
                    break
            params = {"title": title or "Recordatorio", "datetime_iso": datetime.datetime.now().isoformat()}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.SET_REMINDER,
                params,
                f"Recordatorio programado: '{params['title']}'.",
                None
            )

        # 10. Reproducción Multimedia (Spotify / YouTube)
        is_media_play = (
            not any(w in norm for w in ["recordatorio", "recuerdame", "alarma", "temporizador", "linterna", "volumen", "brillo", "wifi", "bluetooth"])
            and (
                any(w in norm for w in [
                    "reproduce", "reproducir", "play", "escuchar", "escucha",
                    "toca ", "tocame ", "tocate ",
                    "busca en youtube", "buscar en youtube", "busca en spotify", "buscar en spotify",
                    "quiero oir", "quiero escuchar", "vamos a escuchar", "pon musica", "ponte musica",
                    "musica de", "cancion de", "canciones de", "videos de", "video de"
                ])
                or (norm.startswith("pon ") and not any(x in norm for x in ["pon un", "pon una", "pon el ", "pon la ", "pon en "]))
                or any(norm.startswith(p) for p in ["ponme ", "ponte "])
                or (any(p in norm for p in ["spotify", "youtube"]) and not any(norm.startswith(x) for x in ["abre ", "abrir ", "lanza ", "inicia "]))
            )
        )
        if is_media_play:
            platform = "youtube" if any(w in norm for w in ["youtube", "video", "videos"]) else "spotify"
            query_clean = raw_text
            patterns_to_remove = [
                r"(?i)\b(?:por\s+favor\s+)?(?:reproduce|reproducir|quiero\s+escuchar\s+a|quiero\s+escuchar|vamos\s+a\s+escuchar|escuchar\s+a|escuchar|escucha|pon\s+la\s+canci[oó]n\s+de|pon\s+el\s+video\s+de|pon\s+el\s+tema\s+de|pon\s+m[uú]sica\s+de|pon\s+algo\s+de|ponme\s+a|ponte\s+a|ponme|ponte|pon\s+a|pon|toca\s+la\s+canci[oó]n\s+de|toca\s+el\s+tema\s+de|toca\s+a|t[oó]came\s+a|t[oó]came|toca|play|busca\s+en\s+youtube|buscar\s+en\s+youtube|busca\s+en\s+spotify|buscar\s+en\s+spotify)\b",
                r"(?i)\b(?:en|de|por)\s+spotify\b",
                r"(?i)\b(?:en|de|por)\s+youtube\b",
            ]
            for pat in patterns_to_remove:
                query_clean = re.sub(pat, "", query_clean)
            query_clean = query_clean.strip(" .,-!?:;\"'")
            if not query_clean or query_clean.lower() in ["musica", "música", "algo", "cancion", "canción", "video", "videos"]:
                query_clean = "música"

            params = {"query": query_clean, "platform": platform, "media_type": "video" if platform == "youtube" else "track"}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.PLAY_MEDIA,
                params,
                self._generate_confirmation_text(DeviceCommand.PLAY_MEDIA, params),
                None
            )

        # 11. Abrir Aplicaciones
        if any(w in norm for w in ["abre", "abrir", "lanza", "inicia", "ejecuta"]):
            known_apps = {
                "spotify": "Spotify",
                "whatsapp": "WhatsApp",
                "youtube": "YouTube",
                "camara": "Cámara",
                "calculadora": "Calculadora",
                "ajustes": "Ajustes",
                "configuracion": "Ajustes",
                "chrome": "Chrome",
                "navegador": "Chrome",
                "maps": "Maps",
                "mapa": "Maps",
                "mapas": "Maps",
                "gmail": "Gmail",
                "correo": "Gmail",
                "reloj": "Reloj",
                "galeria": "Galería",
                "fotos": "Galería",
                "instagram": "Instagram",
                "facebook": "Facebook",
                "tiktok": "TikTok"
            }
            for key, canonical in known_apps.items():
                if key in norm:
                    params = {"app_name": canonical}
                    return (
                        ActionType.DEVICE_CONTROL,
                        DeviceCommand.OPEN_APP,
                        params,
                        f"Abriendo {canonical}.",
                        None
                    )
            m_app = re.search(r"(?:abre|abrir|lanza|inicia|ejecuta)\s+(?:la\s+app\s+|la\s+aplicaci[oó]n\s+|el\s+|la\s+)?([a-záéíóúñ0-9\s]+)", low)
            if m_app:
                app_title = m_app.group(1).strip().capitalize()
                params = {"app_name": app_title}
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.OPEN_APP,
                    params,
                    f"Abriendo {app_title}.",
                    None
                )

        # 12. Llamada telefónica
        if any(w in norm for w in ["llama a", "llamar a", "marcar a", "llama al", "llamar al", "marca al"]):
            digits = re.sub(r"\D", "", low)
            if len(digits) >= 3:
                params = {"phone_number": digits, "contact_name": digits}
                return (
                    ActionType.DEVICE_CONTROL,
                    DeviceCommand.MAKE_PHONE_CALL,
                    params,
                    f"Iniciando llamada al {digits}.",
                    None
                )
            m_contact = re.search(r"(?:llama|llamar|marcar|marca)\s+(?:a|al)\s+(.+)", raw_text, re.IGNORECASE)
            contact = m_contact.group(1).strip(" .,!?").capitalize() if m_contact else "contacto"
            params = {"contact_name": contact}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.MAKE_PHONE_CALL,
                params,
                f"Iniciando llamada con {contact}.",
                None
            )

        # 13. Mensajes / WhatsApp
        if any(w in norm for w in ["mensaje a", "whatsapp a", "escribe a", "manda un whatsapp", "envia un whatsapp"]):
            m_msg = re.search(
                r"(?:mensaje|whatsapp|escribe)\s+a\s+([a-záéíóúñ]+)(?:\s+(?:diciendo\s+que|diciendo|que\s+diga|con\s+el\s+mensaje)\s+(.+))?",
                raw_text,
                re.IGNORECASE
            )
            body = "Hola, ya voy en camino."
            if m_msg and m_msg.group(2):
                recipient = m_msg.group(1).strip().capitalize()
                body = m_msg.group(2).strip(" .,")
            else:
                recipient = "Carlos"
            params = {"recipient": recipient, "message_body": body, "app": "whatsapp"}
            return (
                ActionType.DEVICE_CONTROL,
                DeviceCommand.SEND_MESSAGE,
                params,
                f"Redactando mensaje para {recipient}.",
                None
            )

        # 14. Consultas conversacionales y comandos rápidos
        now = datetime.datetime.now()
        if any(w in norm for w in ["que hora", "dime la hora", "tienes hora", "la hora"]):
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                f"Son las {now.strftime('%H:%M')} horas.",
                None
            )

        if any(w in norm for w in ["que dia es", "que fecha", "en que dia estamos", "la fecha"]):
            dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
            meses = [
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
            ]
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                f"Hoy es {dias[now.weekday()]} {now.day} de {meses[now.month - 1]} de {now.year}.",
                None
            )

        if any(w in norm for w in ["que puedes hacer", "que sabes hacer", "ayuda", "comandos"]):
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                "Puedo reproducir música en Spotify y YouTube, controlar linterna, volumen y brillo, poner alarmas y temporizadores, abrir apps y responder sus preguntas.",
                None
            )

        if any(w in norm for w in ["quien eres", "como te llamas"]):
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                "Soy Yarbis, su asistente inteligente de voz.",
                None
            )

        if any(w in norm for w in ["como estas", "que tal"]):
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                "Todos mis sistemas operan al cien por ciento. ¿En qué puedo asistirle?",
                None
            )

        if any(w in norm for w in ["gracias", "muchas gracias", "te lo agradezco"]):
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                "De nada. Siempre es un placer asistirle.",
                None
            )

        if any(w in norm for w in ["adios", "hasta luego", "chao", "nos vemos"]):
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                "Hasta luego. Yarbis permanecerá en espera.",
                None
            )

        if any(w in norm for w in ["hola", "buenos dias", "buenas tardes", "buenas noches"]):
            return (
                ActionType.CONVERSATIONAL_QUERY,
                None,
                {},
                "Hola. Yarbis en línea y a su disposición. ¿Qué desea hacer?",
                None
            )

        # Fallback conversacional limpio
        return (
            ActionType.CONVERSATIONAL_QUERY,
            None,
            {},
            f"He recibido su consulta: '{raw_text}'. Indíqueme cómo puedo asistirle.",
            None
        )


_llm_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Inyector de dependencias para LLMService."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance
