from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"


def find_command(name: str) -> str | None:
    candidates = [name]
    if os.name == "nt":
        candidates = [f"{name}.cmd", f"{name}.bat", name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start_process(command: list[str], cwd: Path, name: str) -> subprocess.Popen[str]:
    print(f"Starting {name}: {' '.join(command)}")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=None,
        stderr=None,
        stdin=None,
        text=True,
        env=os.environ.copy(),
    )


def main() -> int:
    python_exe = sys.executable
    backend_cmd = [python_exe, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8001"]
    npm_cmd = find_command("npm")
    if not npm_cmd:
        print("npm was not found on PATH. Install Node.js and npm to run the frontend.")
        return 1

    frontend_cmd = [npm_cmd, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3001"]

    backend_process = None
    frontend_process = None

    if is_port_in_use(8001):
        print("Backend is already running on http://127.0.0.1:8001")
    else:
        backend_process = start_process(backend_cmd, ROOT, "backend")

    if is_port_in_use(3001):
        print("Frontend is already running on http://127.0.0.1:3001")
    else:
        frontend_process = start_process(frontend_cmd, FRONTEND_DIR, "frontend")

    print("\nService status:")
    print("Backend: http://127.0.0.1:8001")
    print("Frontend: http://127.0.0.1:3001")
    print("Press Ctrl+C to stop any services started by this launcher.\n")

    def stop_all() -> None:
        for process in (backend_process, frontend_process):
            if process is None:
                continue
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
        for process in (backend_process, frontend_process):
            if process is None:
                continue
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    try:
        while True:
            if backend_process is not None and backend_process.poll() is not None:
                print("Backend exited unexpectedly. Stopping frontend...")
                stop_all()
                return backend_process.returncode
            if frontend_process is not None and frontend_process.poll() is not None:
                print("Frontend exited unexpectedly. Stopping backend...")
                stop_all()
                return frontend_process.returncode
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        stop_all()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
