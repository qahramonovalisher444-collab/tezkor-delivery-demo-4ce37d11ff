import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


BACKEND = Path(__file__).resolve().parent


def wait_until_ready(origin, stop_event, timeout=600):
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("WEBAPP_URL HTTPS origin bo‘lishi kerak.")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if stop_event.is_set():
            return False
        try:
            with urlopen(origin.rstrip("/") + "/api/ready/", timeout=10) as response:
                if response.status == 200 and json.load(response).get("status") == "ok":
                    return True
        except (URLError, OSError, ValueError):
            pass
        stop_event.wait(2)
    raise RuntimeError("Web-ilova va baza belgilangan vaqtda tayyor bo‘lmadi.")


def supervise(commands, stop_event):
    processes = []
    try:
        for command in commands:
            if stop_event.is_set():
                return
            processes.append(subprocess.Popen(command, cwd=BACKEND))
        while not stop_event.wait(0.5):
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("Bot yoki xabarnoma jarayoni to‘xtadi; Render xizmatni qayta boshlashi kerak.")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    stop_event = threading.Event()
    for stop_signal in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(stop_signal, lambda *_: stop_event.set())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.production")
    print("Render: web-ilova va bazani kutyapman.", flush=True)
    if not wait_until_ready(os.environ.get("WEBAPP_URL", ""), stop_event):
        return
    print("Render: bot va xabarnoma xizmatlari boshlanmoqda.", flush=True)
    supervise([
        [sys.executable, str(BACKEND / "manage.py"), "runbot"],
        [sys.executable, str(BACKEND / "manage.py"), "process_notifications"],
    ], stop_event)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr, flush=True)
        raise SystemExit(1)
