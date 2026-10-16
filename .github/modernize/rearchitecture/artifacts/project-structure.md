# Project Structure

## Classification

Yarbis is a **backend** application with an external Kotlin/Android client. The runtime is an asynchronous FastAPI service; the Kotlin files are client integration code rather than a second deployable module in this repository.

## Modules and layers

- `app/main.py`: application factory, FastAPI lifespan, CORS, static-file mount, root metadata route, and Uvicorn entry point.
- `app/api/`: HTTP routing layer. `router.py` composes `/api/v1`; `v1/command.py`, `v1/voice.py`, and `v1/session.py` define the public API surfaces.
- `app/services/`: orchestration and provider services: session memory, LLM/tool calling, STT, and TTS.
- `app/core/`: runtime settings, prompt/personality, and wake-word normalization.
- `app/schemas/`: Pydantic request/response DTOs, action enums, and OpenAI tool schemas.
- `app/utils/`: audio persistence, URL generation, Base64 encoding, and cleanup.
- `clients/kotlin/`: Android HTTP client, response model, overlay/voice service, wake-word detector, and device action handler.
- `static/audio/`: generated or retained MP3 response files.
- `tests/`: pytest API and wake-word tests.

## Functional areas

1. Text command processing and device-control intent detection.
2. Voice processing: multipart upload, audio decode, STT, wake-word validation, LLM/tool decision, TTS, and response assembly.
3. Conversational session memory with TTL and sliding history.
4. Generated audio delivery to Android clients.
5. Health and root metadata endpoints.

## Runtime entry points

- `app.main:app` is the ASGI entry point.
- `POST /api/v1/command/process` accepts JSON text commands.
- `POST /api/v1/voice/process` accepts multipart audio.
- `GET /api/v1/voice/audio/{filename}` serves generated audio.
- Session routes inspect, list, and clear process-local memory.
- `GET /api/v1/health` provides readiness metadata.

The exact source-anchored unit boundaries and contracts are in `unit_graph.yaml` and the per-unit files; this document is a global orientation view, not a behavioral replacement for them.
