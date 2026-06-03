# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1-alpha] - 2026-06-03

### Changed

- Refactored `LettermintEmailBackend`: extracted string coercion logic to `_coerce_str()` method and simplified connection checks
- Removed unused `content_id` parameter from internal attachment handling
- Added type hints to client kwargs dict

### Tested

- Successfully sent first emails through Lettermint on testing environment

## [0.2.0] - 2026-06-03

### Added

- Documentation with getting started guides (installation, configuration, usage)
- MkDocs site generation and GitHub Actions deployment workflow

## [0.1.0] - 2026-05-30

### Added

- `LettermintEmailBackend` - Django `BaseEmailBackend` implementation using the Lettermint Python SDK
- Support for `to`, `cc`, `bcc`, `reply_to`, plain text, HTML, attachments, and custom headers
- `LETTERMINT_API_KEY`, `LETTERMINT_BASE_URL`, `LETTERMINT_ROUTE`, `LETTERMINT_TIMEOUT` settings
- Per-message route override via `X-Lettermint-Route` extra header
- Full test suite with pytest
- GitHub Actions for CI and PyPI publishing
