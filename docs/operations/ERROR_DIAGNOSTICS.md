# Garmin Ops error diagnostics

Public diagnostic contract; private local activation records remain in ignored local logs.

MCP text content, structuredContent, isError, legacy error/http_status and partial-write recovery records remain available. Additive fields: code, stage, cause, action, retriable (null means unknown), error_chain (ordered exception types only). No original message, URL, response body, credentials or health payload is copied into diagnostics. Audited static contract messages retain their useful detail; unknown or dynamic contract messages receive a safe generic detail.

Known HTTP statuses and typed SDK/requests/curl failures determine classifications. 403 reports the observed status with unknown reason. Generic connection exceptions without transport or HTTP evidence remain unknown_failure. Local catalog/input/policy errors retain their stable existing codes. Session resume and upstream reads identify their source stage; writes identify request versus verification. A failed sent write always has retriable=false and retry_requires_state_check=true, preserving completed_requests/last_request for recovery.

Garmin SDK logging is disabled at the Garmin Ops CLI/server startup, not at library import because its raw response/debug logs may expose personal data even when tool output is sanitized. Other application logging is unchanged. Existing recovery records may contain authorized resource data; these are client results, not diagnostic logs.

Packaging source allowlist includes errors.py. Shared publication remains outside this task. A private local update uses the existing marketplace and supported host installation flow, affects only this user’s local Garmin Ops installation, and requires no account, permission, or remote changes. The installed dev.35 process continues using its existing code until local packaging/reinstallation and a new server session. Same-version cache refresh and current-session hot reload are not verified; do not edit installed cache files or restart unrelated tasks.
