"""Local MedRay supervisor. Starts services in order and owns their lifecycle."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def supported_node(version):
    try:
        major, minor, *_ = map(int, version.strip().lstrip("v").split("."))
        return (major == 22 and minor >= 12) or major >= 24
    except ValueError:
        return False


def free_port(host, start, count):
    for port in range(start, start + count):
        with socket.socket() as candidate:
            try:
                candidate.bind((host, port))
                return port
            except OSError:
                pass
    raise RuntimeError("No free port is available. Close another local service and retry.")


def wait_ready(process, url, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("A service stopped before it was ready. Run Setup MedRay and retry.")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.3)
    raise RuntimeError("A service did not become ready in time. Check firewall settings and the technical logs.")


def acquire_lock(path):
    stream = path.open("a+b")
    stream.seek(0)
    if path.stat().st_size == 0:
        stream.write(b"0")
        stream.flush()
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        return None
    return stream


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("MEDRAY_HOST", "127.0.0.1"))
    parser.add_argument("--backend-port", type=int, default=int(os.getenv("MEDRAY_PORT", "8765")))
    parser.add_argument("--frontend-port", type=int, default=int(os.getenv("MEDRAY_FRONTEND_PORT", "5173")))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    processes, logs = [], []
    lock = None
    job = None
    try:
        if args.host not in {"localhost", "127.0.0.1"}:
            raise RuntimeError("For local-first safety, MedRay must run on this computer's loopback address.")
        if not (1024 <= args.backend_port <= 65485 and 1024 <= args.frontend_port <= 65515):
            raise RuntimeError("Choose local ports between 1024 and 65485.")
        node = shutil.which("node")
        if not node or not supported_node(subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5).stdout):
            raise RuntimeError("Node is missing or too old. Install Node.js 22.12+ or 24 LTS, then run Setup MedRay.")
        cache = ROOT / "data/cache"
        cache.mkdir(parents=True, exist_ok=True)
        lock = acquire_lock(cache / "launcher.lock")
        if lock is None:
            print("MedRay is already starting or running. Use the existing window.")
            try:
                existing = json.loads((cache / "launcher.json").read_text())
                port = int(existing["frontend_port"])
                if not args.no_browser and 1024 <= port <= 65535:
                    webbrowser.open(f"http://127.0.0.1:{port}")
            except (OSError, ValueError, KeyError, TypeError):
                pass
            return 0
        host = "127.0.0.1"
        backend_port = free_port(host, args.backend_port, 50)
        frontend_port = free_port(host, args.frontend_port, 20)
        if frontend_port == backend_port:
            frontend_port = free_port(host, frontend_port + 1, 20)
        api_base = f"http://{host}:{backend_port}/api"
        frontend_url = f"http://{host}:{frontend_port}"
        env = {**os.environ, "VITE_API_BASE": api_base}
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        if os.name == "nt":
            from windows_job import WindowsJob
            job = WindowsJob()

        def start(command, cwd, log_name):
            log = (cache / log_name).open("w", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log, creationflags=flags)
            processes.append(process)
            if job:
                job.assign(process.pid)
            return process

        print("Starting backend…", flush=True)
        backend = start([sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(backend_port), "--app-dir", "backend"], ROOT, "backend.log")
        wait_ready(backend, api_base + "/health")
        print("Backend ready. Starting frontend…", flush=True)
        frontend = start([node, "node_modules/vite/bin/vite.js", "--host", host, "--port", str(frontend_port), "--strictPort"], ROOT / "frontend", "frontend.log")
        wait_ready(frontend, frontend_url)
        nonce = uuid4().hex
        (cache / "launcher.json").write_text(json.dumps({"frontend_port": frontend_port, "nonce": nonce}))
        print(f"MedRay ready: {frontend_url}\nOpen AI Setup to choose your AI.\nPress Ctrl+C to stop MedRay.", flush=True)
        if not args.no_browser:
            webbrowser.open(frontend_url)
        while all(process.poll() is None for process in processes):
            try:
                request = json.loads((cache / "launcher-stop.json").read_text())
                if request.get("nonce") == nonce:
                    print("Stopping MedRay and releasing its ports…", flush=True)
                    return 0
            except (OSError, ValueError, AttributeError):
                pass
            time.sleep(0.5)
        raise RuntimeError("A MedRay service stopped. Restart MedRay; if it happens again, run Setup MedRay.")
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"\nMedRay could not start or continue.\nWhat happened: {exc}\nHow to fix: run Setup MedRay, then Start MedRay again.\nTechnical details: data/cache/backend.log and frontend.log", file=sys.stderr)
        return 1
    finally:
        for process in reversed(processes):
            stop(process)
        for log in logs:
            log.close()
        if job:
            job.close()
        if lock:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
