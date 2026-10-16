from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la aplicación Yarbis."""

    # Configuración de Servidor
    APP_NAME: str = "Yarbis Backend"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SERVER_BASE_URL: str = "http://192.168.1.27:8000"
    CORS_ORIGINS: List[str] = ["*"]

    # Identidad y Comportamiento del Asistente
    ASSISTANT_NAME: str = "Yarbis"
    # Si REQUIRE_WAKE_WORD=True, rechaza o avisa cuando el audio no empiece por "Yarbis"
    REQUIRE_WAKE_WORD: bool = False

    # Proveedor LLM / OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 400

    # Proveedor de STT (Speech-to-Text): "openai" | "mock"
    STT_PROVIDER: str = "openai"

    # Proveedor de TTS (Text-to-Speech): "edge_tts" | "openai" | "mock"
    TTS_PROVIDER: str = "edge_tts"

    # Voces de síntesis
    EDGE_TTS_VOICE: str = "es-ES-AlvaroNeural"  # Voz profunda y profesional
    OPENAI_TTS_VOICE: str = "onyx"             # Voz autoritaria y calmada

    # Rutas del Sistema
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STATIC_DIR: Path = BASE_DIR / "static"
    AUDIO_DIR: Path = STATIC_DIR / "audio"

    # Memoria de Sesión
    SESSION_MAX_HISTORY_TURNS: int = 10
    SESSION_TTL_MINUTES: int = 60

    # Configuración de URLs de Audio para Kotlin / Android (Relativas vs Absolutas)
    # Si USE_RELATIVE_AUDIO_URL es True, se devuelve "/api/v1/voice/audio/..."
    # para que el cliente Kotlin le anteponga su baseUrl configurado y no falle en emuladores o Wi-Fi físico.
    USE_RELATIVE_AUDIO_URL: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Retorna una instancia singleton cacheada de Settings sin efectos secundarios."""
    return Settings()

