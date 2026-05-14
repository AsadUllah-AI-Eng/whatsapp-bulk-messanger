"""Standalone smoke test: just Flask + waitress, no pywebview."""
import threading, time, urllib.request, socket
from app import app
from waitress import serve

def s():
    print("calling waitress.serve...", flush=True)
    serve(app, host='127.0.0.1', port=5000, threads=4)

t = threading.Thread(target=s, daemon=True)
t.start()
print(f"[{time.strftime('%H:%M:%S')}] thread started, sleeping 5s", flush=True)
time.sleep(5)

# Raw socket — does the port even accept TCP?
try:
    s_ = socket.create_connection(('127.0.0.1', 5000), timeout=2.0)
    print(f"[{time.strftime('%H:%M:%S')}] TCP connect OK", flush=True)
    s_.close()
except Exception as e:
    print(f"[{time.strftime('%H:%M:%S')}] TCP connect FAILED: {e!r}", flush=True)

# HTTP — does waitress respond?
try:
    r = urllib.request.urlopen('http://127.0.0.1:5000/', timeout=3)
    print(f"[{time.strftime('%H:%M:%S')}] HTTP {r.status}  body bytes={len(r.read())}", flush=True)
except Exception as e:
    print(f"[{time.strftime('%H:%M:%S')}] HTTP FAILED: {e!r}", flush=True)
