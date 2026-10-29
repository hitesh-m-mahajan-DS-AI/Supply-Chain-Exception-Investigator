"""Start one localhost server for both the API and the built React interface."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
from start_local import ensure_service

ROOT = Path(__file__).resolve().parent


def launch():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8532)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Choose a port from 1024 to 65535.")
    python = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file() or not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Run python setup_project.py first.")
    environment = dict(os.environ)
    environment["OMP_NUM_THREADS"] = "1"
    owned_model = ensure_service()
    print(f"Exception Desk: http://127.0.0.1:{args.port}  (Ctrl+C to stop)", flush=True)
    try:
        subprocess.run([str(python), "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", str(args.port)], cwd=ROOT, env=environment, check=True)
    except KeyboardInterrupt:
        pass
    finally:
        if owned_model and owned_model.poll() is None:
            owned_model.terminate()


if __name__ == "__main__":
    launch()
