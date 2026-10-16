# Architecture Index

This index is a navigation aid for implementation and design workers. **This index is not the full contract. Do not implement from this file alone; follow the artifact paths below.**

## Implementation Guide

### Global artifacts

- `unit_graph.yaml` — all workers; use unit boundaries, source anchors, exported signatures, dependencies, dynamic entry points, and shared-reference subsets.
- `migration_boundary.yaml` — all workers; use `must_rewrite`, `copy_as_is`, and `legacy_allowed_to_remain`. For this analysis-only request, `must_rewrite` is empty.
- `wire_contracts.yaml` — workers touching HTTP, file, or client contracts; filter rows by `unit`.
- `shared_modules.yaml` — workers touching shared code; filter rows where `used_by_units` includes the assigned unit and use only the listed fields.
- `cross_unit_state.yaml` — workers touching session or audio hand-offs; filter flows where the unit is writer or reader.
- `seams.yaml` — workers touching the audio URL/file boundary; filter `cut_between` and obey the frozen-side rule.
- `project-structure.md`, `tech-stack.md`, `data-model.md` — global orientation and existing-stack/data evidence.

### Unit: `root_info`

- external trigger: `GET /`
- must read `units/root_info/behavior.yaml` for observable metadata behavior.
- must read `units/root_info/bindings.yaml` for direct FastAPI route wiring and `APP_NAME`.
- must read `units/root_info/unit_decomposition.yaml` for advisory split candidates.
- relevant global rows: `wire_contracts.yaml` where `unit: root_info`; `shared_modules.yaml` where `used_by_units` includes `root_info`.
- before DONE report: artifacts read, preserved metadata keys, unresolved/deferred contracts, and verification evidence.

### Unit: `health_api`

- external trigger: `GET /api/v1/health`
- must read `units/health_api/behavior.yaml`, `bindings.yaml`, and `unit_decomposition.yaml`.
- relevant global rows: `wire_contracts.yaml` where `unit: health_api`; `shared_modules.yaml` where `used_by_units` includes `health_api`.
- before DONE report: artifacts read, preserved status/version/readiness shape, unresolved/deferred contracts, and verification evidence.

### Unit: `command_api`

- external trigger: `POST /api/v1/command/process`
- must read `units/command_api/behavior.yaml` for pipeline branches and session side effects.
- must read `units/command_api/bindings.yaml` for route/DI/config wiring.
- must read `units/command_api/unit_decomposition.yaml`; candidates are advisory only because `commit: false`.
- relevant global rows: `wire_contracts.yaml` for `command_api`; `shared_modules.yaml` for `settings`, `response_contract`, and `orchestrator`; `cross_unit_state.yaml` flows touching `command_api`; `seams.yaml` only if audio output is changed.
- before DONE report: artifacts read, implemented `must_preserve` branches/effects, unresolved/deferred contracts, and build/test/runtime evidence.

### Unit: `voice_pipeline`

- external trigger: `POST /api/v1/voice/process`
- must read `units/voice_pipeline/behavior.yaml` for upload, STT, wake-word, TTS, cleanup, and error behavior.
- must read `units/voice_pipeline/bindings.yaml` for multipart, DI, and provider configuration.
- must read `units/voice_pipeline/unit_decomposition.yaml`; candidates are advisory only because `commit: false`.
- relevant global rows: `wire_contracts.yaml` for `voice_pipeline`; `shared_modules.yaml` for `settings`, `response_contract`, `audio_utilities`, and `orchestrator`; `cross_unit_state.yaml` flows touching `voice_pipeline`; `seams.yaml` for the audio delivery cut.
- before DONE report: artifacts read, preserved audio/error/cleanup contracts, unresolved/deferred contracts, and build/test/runtime evidence.

### Unit: `audio_delivery`

- external trigger: `GET /api/v1/voice/audio/{filename}`
- must read `units/audio_delivery/behavior.yaml` for 404 and media-type behavior.
- must read `units/audio_delivery/bindings.yaml` for route and `AUDIO_DIR` wiring.
- must read `units/audio_delivery/unit_decomposition.yaml`.
- relevant global rows: `wire_contracts.yaml` for `audio_delivery`; `shared_modules.yaml` for `settings` and `audio_utilities`; `cross_unit_state.yaml` for generated audio; `seams.yaml` for the frozen URL/file bridge.
- before DONE report: artifacts read, preserved basename/path-safety/media-type behavior, unresolved/deferred contracts, and verification evidence.

### Unit: `session_api`

- external trigger: session history/context/list/reset routes under `/api/v1/session`
- must read `units/session_api/behavior.yaml` for TTL, unknown-session, and reset behavior.
- must read `units/session_api/bindings.yaml` for route and dependency injection wiring.
- must read `units/session_api/unit_decomposition.yaml`; candidates are advisory only because `commit: false`.
- relevant global rows: `shared_modules.yaml` for `settings` and `session_store`; `cross_unit_state.yaml` flows where `reader.unit` or `writer.unit` is `session_api`; `wire_contracts.yaml` for `session_api`.
- before DONE report: artifacts read, preserved session semantics, unresolved/deferred contracts, and verification evidence.

## Completeness and authority notes

- `unit_decomposition.yaml` files intentionally set `commit: false`; final splits belong to design.
- `source_anchors` identify evidence and are not rewrite scope.
- `must_preserve` and `must_appear_in_target` entries are hard fidelity requirements.
- Inferred seams are advisory; no user-declared seam was supplied.
