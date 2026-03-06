# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python CLI tool for controlling Audinate Dante network audio devices without Dante Controller. Uses reverse-engineered UDP protocol commands to communicate with devices discovered via mDNS (zeroconf). This is a fork with XML subscription import support.

## Build & Run Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run netaudio

# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Verbose/debug mode
uv run netaudio -v

# Build windows package
uv run pyinstaller --noconfirm --onedir --name netaudio packages/netaudio/src/netaudio/__main__.py
```

## Architecture

### Monorepo Structure (uv workspaces)

- `packages/netaudio-lib/` — Core library: device discovery, protocol, UDP commands
- `packages/netaudio/` — CLI application built on **typer**
- `packages/netaudio-tui/` — TUI interface (separate package)

### Key Components

**CLI Layer** (`packages/netaudio/src/netaudio/`):
- `cli.py` — Main typer app, global state, output format handling
- `commands/` — Command modules (device.py, channel.py, subscription.py, etc.)
- `_common.py` — Shared helpers: `_command_context()`, `_discover()`, `find_device()`, `find_channel()`, `output_table()`, etc.
- `_exit_codes.py` — Exit code constants

**Library Layer** (`packages/netaudio-lib/src/netaudio_lib/`):
- `dante/device.py` — `DanteDevice` model
- `dante/device_commands.py` — `DanteDeviceCommands` builds raw UDP packets
- `dante/browser.py` — `DanteBrowser` for mDNS discovery
- `dante/application.py` — `DanteApplication` manages lifecycle (startup/shutdown/discover)
- `daemon/` — Optional daemon mode for persistent device monitoring

**Command Pattern:**
Each CLI command uses `asyncio.run()` on an async `_run()` closure. For commands that send packets, use `_command_context()` which yields `(devices, send)`. Use `find_device()` and `find_channel()` to locate targets, then `DanteDeviceCommands` to build packets and `send()` to transmit.

### Important Conventions

- CLI framework: **typer** (not cleo)
- Build system: **uv** (not poetry)
- Formatter/linter: **ruff** (not black/pylint)
- All device communication is async
- Commands use `@app.command()` decorator pattern
