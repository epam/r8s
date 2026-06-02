# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-02
### Added
- Python 3.14 support (`requires-python` now `>=3.10,<3.15`).

### Changed
- Synced dependency versions with `modular-mcp` for consistency across the suite:
  - `mcp` `>=1.6.0` -> `>=1.26.0`
  - `starlette` `>=0.37.0` -> `>=0.52.1`
  - `pyyaml` `>=6.0.0` -> `>=6.0.3`
  - `pydantic` `>=2.7.0` -> `>=2.12.5`
  - `pytest` (dev) `>=8.0.0` -> `>=9.0.2`
- Capped supported Python version to `<3.15` to align with the modular-mcp host.

### Fixed
- Removed duplicate `python-dotenv` dependency entry (was pinned to both
  `>=1.0.0` and `>=1.2.1`); now declared once as `>=1.2.1`.
- Corrected HTTP error handling in `R8SClient`: connection failures
  (`httpx.ConnectError`) are now handled separately from HTTP status errors
  (`httpx.HTTPStatusError`), preventing an `AttributeError` when accessing
  `.response` on exceptions that do not carry a response object.

## [1.0.0] - 2026-05-29
* Initial release of RightSizer MCP server.