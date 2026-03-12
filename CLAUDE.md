# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Run CLI version: `python chess.py`
- Run web server: `python server.py` (access at http://localhost:8080)

## Architecture

The project consists of two interfaces sharing the same Pikafish chess engine:

**`chess.py`** - Command-line interface
- `XiangqiBoard` class: Board representation, FEN parsing/generation, move execution
- `PikafishEngine` class: UCI protocol wrapper for the AI engine
- Human input uses Chinese notation (列行 - 列行，e.g., `32-36`), converted to UCI format

**`server.py`** - Web backend
- `XiangqiGame` class: Maintains game state, move history, and engine communication
- HTTP API endpoints: `/api/newgame`, `/api/move`, `/api/ai`, `/api/undo`
- Uses Python's built-in `http.server` module

**`index.html`** - Web frontend
- Vanilla JS/CSS single-page application
- Communicates with server via Fetch API
- Board rendering with SVG lines and DOM-based pieces

## Key Conventions

- FEN format: Black pieces lowercase (rnbakabnr), Red pieces uppercase (RNBAKABNR)
- UCI coordinates: columns a-i (right to left), rows 1-10 (bottom to top)
- Red (human) moves first; AI responds at depth 10 by default
