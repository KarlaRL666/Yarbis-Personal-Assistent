# Data Model

## Persistence classification

No ORM, database driver, migration file, or persistent entity model was found. The application stores conversational state in process memory and audio files on the local filesystem.

## In-memory entities

- `SessionHistory` (`app/services/session_service.py:6`): session identifier, message list, timestamps, and semantic context.
- `messages` (`app/services/session_service.py:9`): dictionaries with `role`, `content`, and optional tool-call metadata.
- `context` (`app/services/session_service.py:13`): `last_topic`, `last_entity`, `last_action_type`, `last_command`, `last_parameters`, `last_user_query`, and `last_assistant_response`.
- `YarbisResponse` (`app/schemas/response.py:6`): external response DTO with action, command, parameters, text, optional audio, transcription, and session ID.
- `CommandProcessRequest` (`app/schemas/request.py:5`): text-command request DTO and per-request behavior flags.

## Relationships and lifecycle

- `SessionService._sessions` maps one `session_id` to one `SessionHistory`.
- A session contains an ordered message list; the sliding window retains at most `SESSION_MAX_HISTORY_TURNS * 3` messages.
- Sessions are removed after `SESSION_TTL_MINUTES` of inactivity.
- Generated audio files are keyed by unique filenames in `AUDIO_DIR` and are referenced by `YarbisResponse.audio_url`.
- There are no database transaction boundaries. Session and file operations are process-local and filesystem-based.

## Key entities summary

1. `SessionHistory`: conversation history and semantic follow-up context.
2. `SessionService`: process-local session registry and TTL policy.
3. `YarbisResponse`: Kotlin-facing response contract.
4. `CommandProcessRequest`: JSON text command input.
5. Tool parameter models: structured schemas for alarms, timers, reminders, device toggles, apps, messaging, and media.
6. `Settings`: environment-backed runtime configuration.

This documents the existing model only; it does not propose persistence or schema redesign.
