# Changelog

## [0.1.6] - 2025-11-28
### Added
- Decoupled notification cadence from flush interval; added optional one-time test Slack message via `LOGCOST_NOTIFICATION_TEST_DELAY`.
- Hardened environment variable parsing with safe defaults for tracker/notifier/sidecar.
- CLI now emits user-friendly errors for missing or malformed stats files.
- Added notifier tests for Slack success/failure paths.

## [0.1.0] - 2024-05-XX
- Initial open-source release with runtime tracker, analyzer, CLI, exporter helpers, framework examples, and documentation.
