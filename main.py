from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse
import atexit
import signal
import socket
import subprocess
import threading
import time
import webbrowser
from typing import Any

import uvicorn

from ollama import ports as ollama_ports, server as ollama_server

DEFAULT_OLLAMA_PORT: int = ollama_ports.PORT_START
OLLAMA_BOOT_TIMEOUT_SECONDS: float = 30.0


def start_ollama_if_needed() -> subprocess.Popen | None:
    if ollama_server.is_running():
        port = ollama_server.current_port()
        print(f"[OLLAMA] Existing Ollama service detected running on port {port}.")
        return None

    print(f"[OLLAMA] No active Ollama service detected. Starting Ollama on port {DEFAULT_OLLAMA_PORT}...")
    try:
        proc = ollama_server.start(port=DEFAULT_OLLAMA_PORT)
    except Exception as exc:
        print(f"[OLLAMA] Error starting Ollama server process: {exc}")
        return None

    print("[OLLAMA] Waiting for Ollama service to become ready...")
    ready = ollama_server.wait_until_ready(port=DEFAULT_OLLAMA_PORT, timeout=OLLAMA_BOOT_TIMEOUT_SECONDS)
    if ready:
        print(f"[OLLAMA] Ollama server is online and ready on port {DEFAULT_OLLAMA_PORT}.")
    else:
        print(f"[OLLAMA] Warning: Timed out waiting for Ollama to respond on port {DEFAULT_OLLAMA_PORT}.")

    return proc


def stop_ollama(proc: subprocess.Popen | None) -> None:
    if proc is not None:
        try:
            print("[OLLAMA] Stopping spawned Ollama service...")
            ollama_server.stop(proc)
            print("[OLLAMA] Spawned Ollama service stopped.")
        except Exception as exc:
            print(f"[OLLAMA] Error stopping Ollama process: {exc}")


def open_browser_when_ready(url: str, host: str, port: int, timeout: float = 10.0, delay: float = 0.5) -> None:
    def _target() -> None:
        probe_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
        deadline = time.time() + timeout
        ready = False

        while time.time() < deadline:
            try:
                with socket.create_connection((probe_host, port), timeout=0.5):
                    ready = True
                    break
            except OSError:
                time.sleep(0.1)

        if delay > 0:
            time.sleep(delay)

        try:
            print(f"[BROWSER] Attempting to open default browser at: {url}")
            opened = webbrowser.open(url)
            if not opened:
                print(f"[BROWSER] Note: webbrowser.open returned false; please open {url} manually if not opened.")
        except Exception as exc:
            print(f"[BROWSER] Could not launch default browser ({exc}). Please visit {url} manually.")

    thread = threading.Thread(target=_target, daemon=True, name="WebGPT-BrowserOpener")
    thread.start()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WebGPT - Intelligent AI Procurement & Data Assistant",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "127.0.0.1"),
        help="Host address to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not attempt to open the default web browser",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload for development",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    host: str = args.host
    port: int = args.port

    display_host: str = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    url: str = f"http://{display_host}:{port}"

    print("=" * 65)
    print(" [LAUNCH] WebGPT - Intelligent AI Procurement & Data Assistant")
    print(f" [ONLINE] Web GUI URL: {url}")
    print(f" [SERVER] Bound to:    http://{host}:{port}")
    print("=" * 65)

    ollama_proc = start_ollama_if_needed()
    if ollama_proc is not None:
        atexit.register(stop_ollama, ollama_proc)

    if not args.no_browser:
        open_browser_when_ready(url=url, host=host, port=port)
    else:
        print("[BROWSER] Skipping browser launch (--no-browser requested).")

    try:
        uvicorn.run("server:app", host=host, port=port, reload=args.reload, log_level="info")
    finally:
        if ollama_proc is not None:
            stop_ollama(ollama_proc)


if __name__ == "__main__":
    main()
