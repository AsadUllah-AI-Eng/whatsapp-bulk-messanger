"""
Launcher entry point — starts Flask in a background thread and renders the
UI inside a native pywebview window (EdgeChromium / WebView2 on Windows).

Why this layout:
  * Flask must run in a daemon thread, NOT the main thread. pywebview's GUI
    event loop has to own the main thread on Windows or it can't pump
    messages.
  * use_reloader=False is required because the Flask reloader spawns a child
    process — fatal inside a frozen exe.
  * We wait for the socket to actually accept connections before we hand the
    URL to pywebview, otherwise the window briefly shows ERR_CONNECTION_REFUSED.
  * Top-level try/except writes any startup failure to launcher_error.log so
    silent crashes (no console window) are still diagnosable.
"""
import os
import socket
import threading
import time
import traceback
from datetime import datetime

import webview


HOST = "127.0.0.1"
PORT = 5000
WINDOW_TITLE = "WhatsApp Bulk Messenger"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
MIN_SIZE = (1000, 650)


def _log_dir() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(appdata, "WhatsAppBulkMessenger")
    os.makedirs(path, exist_ok=True)
    return path


def _log_error(exc: BaseException) -> None:
    log_path = os.path.join(_log_dir(), "launcher_error.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n=== {datetime.now().isoformat()} ===\n")
        f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _wait_for_server(host: str, port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _start_flask() -> None:
    # Imported here so any import-time error in app.py surfaces inside main()'s
    # try/except (where _log_error can capture it) rather than at module load.
    from app import app
    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


def main() -> None:
    threading.Thread(target=_start_flask, daemon=True).start()

    if not _wait_for_server(HOST, PORT, timeout=20.0):
        raise RuntimeError(
            f"Flask server did not start listening on {HOST}:{PORT} within 20s."
        )

    webview.create_window(
        title=WINDOW_TITLE,
        url=f"http://{HOST}:{PORT}",
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=MIN_SIZE,
        resizable=True,
        confirm_close=False,
    )
    # Blocks the main thread until the window is closed. EdgeChromium is the
    # default on Windows 10/11 and is auto-detected. If WebView2 runtime is
    # missing, pywebview falls back to MSHTML (legacy IE) — still functional
    # but worse rendering.
    webview.start()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — we want everything in the log
        _log_error(exc)
        raise
