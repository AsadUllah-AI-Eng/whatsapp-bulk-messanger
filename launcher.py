"""
Launcher entry point — Flask in a daemon thread + native pywebview window.

Diagnostic-heavy variant: every interesting event lands in
%APPDATA%\\WhatsAppBulkMessenger\\launcher.log so silent failures inside
a windowed PyInstaller build are debuggable from the user's machine.

Key tricks:
  * In windowed frozen mode sys.stdout/sys.stderr are None — anything Flask
    or werkzeug prints disappears. We replace them with a line-buffered file
    handle on launcher.log so we capture Flask's startup banner AND any
    werkzeug tracebacks.
  * The Flask thread is wrapped in a try/except that logs the full traceback,
    so a crashing app.run() no longer just dies in the dark.
  * The HTTP probe treats any HTTP response (including 5xx) as "alive". The
    previous version returned False on 500, which would falsely report
    "Flask never responded" when Flask was up and just returning an error page.
"""
import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime

import webview


HOST = "127.0.0.1"
PORT = 8765
APP_URL = f"http://{HOST}:{PORT}/"
WINDOW_TITLE = "WhatsApp Bulk Messenger"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
MIN_SIZE = (1000, 650)

SERVER_READY_TIMEOUT = 45.0
PROBE_INTERVAL = 0.4


SPLASH_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Loading...</title>
<style>
  html,body { height:100%; margin:0; font-family:'Segoe UI',sans-serif;
              background:#0b1220; color:#e8eefc;
              display:flex; align-items:center; justify-content:center; }
  .box { text-align:center; }
  .spinner { width:42px; height:42px; margin:0 auto 18px; border-radius:50%;
             border:4px solid #1f3a5f; border-top-color:#4fc3f7;
             animation:spin .9s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  h1 { margin:0 0 6px; font-size:18px; font-weight:600; }
  p  { margin:0; opacity:.7; font-size:13px; }
</style></head>
<body><div class="box">
  <div class="spinner"></div>
  <h1>Starting WhatsApp Bulk Messenger</h1>
  <p>Initialising local server&hellip;</p>
</div></body></html>"""


def _error_html(message: str) -> str:
    safe = message.replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Startup failed</title>
<style>
  html,body {{ height:100%; margin:0; font-family:'Segoe UI',sans-serif;
               background:#1a0f0f; color:#ffe8e8;
               display:flex; align-items:center; justify-content:center; }}
  .box {{ max-width:680px; padding:24px; }}
  h1 {{ margin:0 0 12px; color:#ff7a7a; }}
  pre {{ background:#2a1818; padding:14px; border-radius:6px;
         white-space:pre-wrap; word-break:break-word; font-size:12px; }}
  p  {{ opacity:.85; font-size:13px; }}
</style></head>
<body><div class="box">
  <h1>Couldn't start the local server</h1>
  <p>Please close the app and try again. Details:</p>
  <pre>{safe}</pre>
  <p>Full log: <code>%APPDATA%\\WhatsAppBulkMessenger\\launcher.log</code></p>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _log_dir() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(appdata, "WhatsAppBulkMessenger")
    os.makedirs(path, exist_ok=True)
    return path


_LOG_PATH = os.path.join(_log_dir(), "launcher.log")


def _log(msg: str) -> None:
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")


def _log_traceback(prefix: str, exc: BaseException) -> None:
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n--- {datetime.now().isoformat()} :: {prefix} ---\n")
        f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        f.write("---\n")


def _redirect_streams_to_log() -> None:
    """Frozen --windowed apps have stdout==stderr==None. Anything Flask
    prints (including tracebacks from request handlers) vanishes. Redirect
    both streams to the same log file so they're recoverable."""
    if not getattr(sys, 'frozen', False):
        return
    try:
        f = open(_LOG_PATH, "a", encoding="utf-8", buffering=1)  # line-buffered
        sys.stdout = f
        sys.stderr = f
    except Exception as exc:  # noqa: BLE001
        # If even THIS fails we have nowhere to write — just give up silently.
        _log(f"stream redirect failed: {exc!r}")


# ---------------------------------------------------------------------------
# Flask thread — serves via waitress (production WSGI), not werkzeug's dev
# server. Werkzeug's app.run() is unreliable inside a frozen --windowed exe
# on Windows: the listening socket comes up but connections hang. Waitress
# is single-file, pure-Python, and well-tested inside PyInstaller bundles.
# ---------------------------------------------------------------------------
def _start_flask() -> None:
    try:
        _log("flask-thread: importing app module")
        from app import app, DB_PATH, UPLOAD_FOLDER
        _log(f"flask-thread: app imported. template_folder={app.template_folder}")
        _log(f"flask-thread: DB_PATH={DB_PATH} (exists={os.path.exists(DB_PATH)})")
        _log(f"flask-thread: UPLOAD_FOLDER={UPLOAD_FOLDER} (exists={os.path.exists(UPLOAD_FOLDER)})")

        _log("flask-thread: importing waitress")
        from waitress import serve

        _log(f"flask-thread: waitress.serve on {HOST}:{PORT}")
        serve(app, host=HOST, port=PORT, threads=6, _quiet=False)
        _log("flask-thread: waitress.serve returned (server shut down)")
    except BaseException as exc:  # noqa: BLE001 — log absolutely everything
        _log("flask-thread: EXCEPTION — see traceback below")
        _log_traceback("flask-thread", exc)


# ---------------------------------------------------------------------------
# HTTP probe
# ---------------------------------------------------------------------------
# Build a urllib opener with proxies disabled — Windows urllib reads system
# proxy settings (IE/Edge config) by default, and a misconfigured corporate
# or VPN proxy can cause localhost connects to silently hang for the full
# timeout on every probe iteration. ProxyHandler({}) forces a direct route.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _flask_responding(attempt: int) -> bool:
    """Any HTTP response means Flask is alive — including 4xx/5xx.

    Returns True even for HTTPError, because an error page still proves
    the server is reachable. The probe's job is "did werkzeug/waitress
    answer", not "is the app healthy".
    """
    t0 = time.time()
    try:
        with _NO_PROXY_OPENER.open(APP_URL, timeout=1.5) as resp:
            _log(f"probe[{attempt}]: HTTP {resp.status} in {time.time()-t0:.2f}s — alive")
            return resp.status >= 100
    except urllib.error.HTTPError as e:
        _log(f"probe[{attempt}]: HTTP {e.code} in {time.time()-t0:.2f}s — alive")
        return True
    except (urllib.error.URLError, ConnectionError, OSError, TimeoutError) as e:
        # Don't spam the log for every connection refused — log only the
        # first and then every fifth attempt.
        if attempt == 1 or attempt % 5 == 0:
            _log(f"probe[{attempt}]: not yet ({type(e).__name__}: {e})")
        return False
    except Exception as exc:  # noqa: BLE001
        _log(f"probe[{attempt}]: unexpected error: {exc!r}")
        return False


def _wait_for_flask(timeout: float = SERVER_READY_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        if _flask_responding(attempt):
            return True
        time.sleep(PROBE_INTERVAL)
    _log(f"probe: gave up after {attempt} attempts ({timeout}s)")
    return False


# ---------------------------------------------------------------------------
# Window driver
# ---------------------------------------------------------------------------
# The previous version passed _drive_window as `func` to webview.start(...).
# Empirically pywebview 6.x does not always invoke that callback — Flask
# came up but the navigate-on-ready code never ran. We replaced it with a
# loaded-event hook, which fires deterministically once the splash HTML
# finishes rendering.

_window_driven = False  # guard so we don't double-fire load_url


def _drive_window(window) -> None:
    """Wait for Flask, then point the window at it. Called from a worker
    thread spawned by the on-loaded handler."""
    global _window_driven
    if _window_driven:
        return
    _window_driven = True

    _log("driver: thread started")
    try:
        if _wait_for_flask():
            _log(f"driver: navigating window to {APP_URL}")
            window.load_url(APP_URL)
            return

        last_lines = ""
        try:
            with open(_LOG_PATH, "r", encoding="utf-8") as f:
                last_lines = "".join(f.readlines()[-30:])
        except Exception:
            pass

        _log("driver: rendering error page (Flask never answered)")
        window.load_html(_error_html(
            f"Flask did not respond on {APP_URL} within "
            f"{SERVER_READY_TIMEOUT:.0f}s.\n\nLast log lines:\n{last_lines}"
        ))
    except BaseException as exc:  # noqa: BLE001
        _log_traceback("driver", exc)
        try:
            window.load_html(_error_html(repr(exc)))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
def main() -> None:
    _redirect_streams_to_log()

    _log("=== launcher start ===")
    _log(f"python={sys.version.split()[0]}  frozen={getattr(sys, 'frozen', False)}")
    _log(f"executable={sys.executable}")
    _log(f"_MEIPASS={getattr(sys, '_MEIPASS', '<not set>')}")
    _log(f"APPDATA={os.environ.get('APPDATA')}")
    _log(f"cwd={os.getcwd()}")

    threading.Thread(target=_start_flask, daemon=True, name="flask").start()

    window = webview.create_window(
        title=WINDOW_TITLE,
        html=SPLASH_HTML,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=MIN_SIZE,
        resizable=True,
        confirm_close=False,
    )

    # Hook the splash's loaded event — that's our signal that WebView2 is
    # alive and window.load_url(...) is safe to call. We spin the actual
    # probe + navigation onto a worker thread so we don't block the GUI.
    def _on_loaded() -> None:
        _log("event: window 'loaded' fired (splash visible)")
        threading.Thread(
            target=_drive_window, args=(window,), daemon=True, name="driver"
        ).start()

    window.events.loaded += _on_loaded
    _log("event: 'loaded' handler attached")

    try:
        _log("webview.start(gui='edgechromium')")
        webview.start(gui='edgechromium', debug=False)
    except Exception as exc:
        _log(f"edgechromium backend failed: {exc!r}; retrying with default backend")
        _log_traceback("edgechromium-start", exc)
        _log("webview.start(default backend)")
        webview.start(debug=False)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        _log_traceback("main", exc)
        raise
