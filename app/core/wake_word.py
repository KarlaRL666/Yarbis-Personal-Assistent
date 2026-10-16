import re
from typing import Tuple

# Variantes fonéticas comunes de "Yarbis" en modelos STT (Whisper, Google Speech, Vosk, etc.)
# Incluye prefijos conversacionales como "oye", "hey", "hola", "ok"
WAKE_WORD_VARIANTS = (
    "yarbis", "yarbiss", "jarvis", "jarviss", "yarvis", "yarviss",
    "iarbis", "llarbis", "llarvis", "llárvis", "yárvis", "yárbis",
    "harvis", "harvey", "arbis", "arvis", "garbis", "garvis",
    "darbis", "darvis", "charvis", "yerbis", "jarbi", "yarbi", "jarvi", "yarvi",
    "jervis", "llervis", "yervis", "barbis", "barbi", "marvis", "elvis", "hierbas", "avis", "alvis"
)

WAKE_WORD_REGEX_TOKEN = r"(?:" + "|".join(WAKE_WORD_VARIANTS) + r"|[yjdhgc]a?r[bv][yií]s+)"

WAKE_WORD_PATTERN = re.compile(
    r"^(?:(?:hola|hey|oye|ok|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches)[,\s]+)*"
    + WAKE_WORD_REGEX_TOKEN + r"\b[,\s:\.\!\?]*",
    re.IGNORECASE | re.UNICODE
)


class WakeWordValidator:
    """Validador y normalizador de Wake Word para Yarbis."""

    @classmethod
    def detect_and_clean(cls, transcript: str) -> Tuple[bool, str]:
        """
        Detecta si la transcripción contiene el wake word "Yarbis" (o variantes fonéticas)
        y remueve el prefijo para entregar la orden limpia al LLM.

        Retorna:
            Tuple[bool, str]: (wake_word_detectado, texto_limpio)
        """
        if not transcript:
            return False, ""

        stripped = transcript.strip()
        match = WAKE_WORD_PATTERN.match(stripped)

        if match:
            cleaned_command = stripped[match.end():].strip()
            cleaned_command = re.sub(r"^[,\-\.:;\!\?\s]+", "", cleaned_command)
            return True, cleaned_command

        # Verificación en cualquier posición de la frase (ej. "Oye por favor Yarbis reproduce..." o "... Yarbis")
        m_any = re.search(r"\b" + WAKE_WORD_REGEX_TOKEN + r"\b", stripped, re.IGNORECASE)
        if m_any:
            after = stripped[m_any.end():].strip(" ,.:;-!?")
            before = stripped[:m_any.start()].strip(" ,.:;-!?")
            # Eliminar saludos iniciales si estaban antes del wake word
            before_clean = re.sub(
                r"^(?:hola|hey|oye|ok|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches)\b[,\s]*",
                "",
                before,
                flags=re.IGNORECASE
            ).strip()
            cleaned = after if after else before_clean
            return True, cleaned

        return False, stripped

    @classmethod
    def process_transcript(cls, transcript: str, require_wake_word: bool) -> Tuple[bool, str]:
        """
        Evalúa la transcripción según la política de requerimiento de wake word.

        Si require_wake_word es True:
            Solo se considera válido si se detecta "Yarbis".
        Si require_wake_word es False:
            Se limpia el wake word si está presente, pero no es obligatorio.

        Retorna:
            Tuple[bool, str]: (es_valido_para_procesar, comando_limpio)
        """
        detected, cleaned = cls.detect_and_clean(transcript)

        if require_wake_word:
            if not detected:
                return False, transcript
            return True, cleaned
        else:
            # Si no es obligatorio, procesamos siempre, usando el texto limpio si existía wake word
            return True, cleaned if detected else transcript
