"""
brain.py

Solomon's backend entry point.

Starts a pure async WebSocket server on ws://localhost:8765.
Each incoming connection gets its own:
  - ConversationManager  (isolated history per session)
  - _SessionState        (active ring, abort flag)

This file is spawned as a child process by main.js (Electron).
It should never import anything Electron-specific.

Usage:
  python brain.py
"""

import asyncio
import json
import sys
import os

import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

from backend.ws_handlers import handle_message, _SessionState
from backend.conversation import ConversationManager
from backend.ollama_client import check_ollama_alive, list_models

# ── Config ────────────────────────────────────────────────────────────────────
HOST = "localhost"
PORT = 8765


# ── Per-connection handler ────────────────────────────────────────────────────

async def handler(websocket) -> None:
    """
    Called once per WebSocket connection.
    Creates isolated session state and runs the message loop.
    """
    remote = websocket.remote_address
    print(f"[brain] Client connected: {remote}")

    # Per-session state — each connection is fully independent
    conversation_manager = ConversationManager()
    session = _SessionState()

    # ── Authentication handshake ─────────────────────────────────────────────
    expected_token = os.environ.get("SOLOMON_AUTH_TOKEN")

    try:
        # Expect the first message to be a handshake containing the token
        first_raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
    except asyncio.TimeoutError:
        print(f"[brain] Handshake timeout from {remote}; closing connection.", file=sys.stderr)
        try:
            await websocket.close(code=4002, reason='Handshake timeout')
        except Exception:
            pass
        return

    try:
        first_msg = json.loads(first_raw)
    except json.JSONDecodeError:
        print(f"[brain] Invalid handshake JSON from {remote}; closing.", file=sys.stderr)
        try:
            await websocket.close(code=4003, reason='Invalid handshake')
        except Exception:
            pass
        return

    if first_msg.get('event') != 'handshake' or first_msg.get('token') != expected_token:
        print(f"[brain] Unauthorized connection attempt from {remote}", file=sys.stderr)
        try:
            await websocket.send(json.dumps({"event": "error", "message": "unauthorized"}))
            await websocket.close(code=4001, reason='Unauthorized')
        except Exception:
            pass
        return

    # Acknowledge successful handshake
    try:
        await websocket.send(json.dumps({"event": "handshake_auth", "status": "verified"}))
    except Exception:
        pass

    # ── On-connect continuation: check Ollama and send initial status
    ollama_ok = await check_ollama_alive()

    if not ollama_ok:
        print("[brain] WARNING: Ollama is not reachable at localhost:11434", file=sys.stderr)
        await websocket.send(json.dumps({
            "event": "status",
            "state": "ollama_offline",
        }))
    else:
        # Send idle status + available models so the frontend can populate
        # model selectors without needing a separate request
        models = await list_models()
        await websocket.send(json.dumps({"event": "status", "state": "idle"}))
        await websocket.send(json.dumps({"event": "models", "list": models}))
        print(f"[brain] Ollama online. {len(models)} model(s) available: {models}")

    # ── Message loop ──────────────────────────────────────────────────────────
    try:
        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                print(f"[brain] Received invalid JSON, ignoring: {raw_message!r}", file=sys.stderr)
                continue

            await handle_message(
                data=data,
                websocket=websocket,
                conversation_manager=conversation_manager,
                session=session,
            )

    except ConnectionClosedOK:
        print(f"[brain] Client disconnected cleanly: {remote}")
    except ConnectionClosedError as exc:
        print(f"[brain] Client disconnected with error: {remote} — {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"[brain] Unexpected error in handler for {remote}: {exc}", file=sys.stderr)


# ── Server startup ────────────────────────────────────────────────────────────

async def main() -> None:
    print(f"[brain] Solomon brain starting on ws://{HOST}:{PORT}")

    async with websockets.serve(handler, HOST, PORT):
        print(f"[brain] Listening. Waiting for Electron renderer to connect...")
        await asyncio.Future()  # Run forever until process is killed


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[brain] Shutting down.")
        sys.exit(0)
