# Technology Stack

## Language and runtime

- Python application; no explicit Python version declaration was found in the repository.
- FastAPI `>=0.110.0` with Uvicorn `>=0.28.0`.
- Async execution uses Python coroutines, `asyncio.to_thread`, `aiofiles`, and HTTPX/OpenAI async clients.

## Dependencies

- Validation/configuration: Pydantic `>=2.6.0`, pydantic-settings `>=2.2.0`, python-dotenv `>=1.0.1`.
- HTTP/form/files: python-multipart `>=0.0.9`, aiofiles `>=23.2.1`, httpx `>=0.27.0`.
- LLM: openai `>=1.30.0`.
- Audio/STT/TTS: edge-tts `>=6.1.10`, SpeechRecognition `>=3.10.0`, pyaudio `>=0.2.14`, imageio-ffmpeg `>=0.5.1`, av `>=12.0.0`.
- Testing: pytest `>=8.0.0`, pytest-asyncio `>=0.23.0`.

## Framework wiring and configuration

- FastAPI routers are mounted under `/api/v1`.
- `Settings` loads `.env` and environment variables through `pydantic-settings`.
- Provider selection is runtime-configurable through `STT_PROVIDER` and `TTS_PROVIDER`.
- OpenAI-compatible LLM/STT/TTS clients use `OPENAI_BASE_URL` and `OPENAI_API_KEY`.
- Static audio is mounted at `/static`, while generated audio is exposed through `/api/v1/voice/audio/{filename}`.
- CORS defaults to `["*"]`.

No target stack, migration path, or deprecation judgment is inferred here; this records the repository's declared stack only.
