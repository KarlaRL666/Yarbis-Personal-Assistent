import pytest
from app.core.wake_word import WakeWordValidator


def test_wake_word_exact_detection():
    # Detecta "Yarbis" exacto y limpia el comando
    detected, cleaned = WakeWordValidator.detect_and_clean("Yarbis, enciende la linterna")
    assert detected is True
    assert cleaned.lower() == "enciende la linterna"


def test_wake_word_variants():
    # Detecta variantes fonéticas usuales en Whisper ("Jarvis", "Yarvis", etc.)
    cases = [
        ("Jarvis, pon una alarma a las 7", "pon una alarma a las 7"),
        ("Hola Yarbis, cuál es el clima", "cuál es el clima"),
        ("Hey Yarbis abre Spotify", "abre spotify"),
        ("Oye Yarbis qué hora es", "qué hora es"),
        ("Ok Jarvis apaga el wifi", "apaga el wifi"),
    ]
    for input_text, expected_cleaned in cases:
        detected, cleaned = WakeWordValidator.detect_and_clean(input_text)
        assert detected is True, f"Fallo al detectar en: '{input_text}'"
        assert cleaned.lower() == expected_cleaned.lower()


def test_wake_word_not_present():
    detected, cleaned = WakeWordValidator.detect_and_clean("Enciende la linterna por favor")
    assert detected is False
    assert cleaned == "Enciende la linterna por favor"


def test_process_transcript_with_requirement():
    # Si require_wake_word=True y no está, retorna False
    valid, text = WakeWordValidator.process_transcript("enciende la linterna", require_wake_word=True)
    assert valid is False

    # Si require_wake_word=True y está, retorna True y limpio
    valid, text = WakeWordValidator.process_transcript("Yarbis, enciende la linterna", require_wake_word=True)
    assert valid is True
    assert text.lower() == "enciende la linterna"

    # Si require_wake_word=False, siempre procesa
    valid, text = WakeWordValidator.process_transcript("enciende la linterna", require_wake_word=False)
    assert valid is True
    assert text == "enciende la linterna"
