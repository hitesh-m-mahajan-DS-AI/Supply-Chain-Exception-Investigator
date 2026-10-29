"""Find an existing local Ollama service or start an installed/portable runtime."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import time
from urllib.request import urlopen
from urllib.error import URLError

ROOT=Path(__file__).resolve().parent


def available():
    try:
        with urlopen("http://127.0.0.1:11434/api/version",timeout=1) as response:
            return json.load(response).get("version")
    except (URLError,TimeoutError,ValueError,OSError):
        return None


def ensure_service():
    if available():
        print("Using the existing local Ollama service.",flush=True)
        return None
    # The optional portfolio cache is runtime setup infrastructure, not another project.
    portable=ROOT.parents[1]/".tools/ollama/runtime/ollama.exe"
    installed=shutil.which("ollama")
    configured=os.environ.get("F2_OLLAMA_EXE")
    executable=configured or installed or (str(portable) if portable.is_file() else None)
    if not executable:
        print("Ollama is not installed. The app will still support evidence search.",flush=True)
        return None
    environment=dict(os.environ)
    environment.update({"OLLAMA_HOST":"127.0.0.1:11434","OLLAMA_NO_CLOUD":"1","OLLAMA_NUM_PARALLEL":"1"})
    if not configured and not installed and portable.is_file():
        environment["OLLAMA_MODELS"]=str(portable.parent.parent/"models")
    runtime=ROOT/"runtime"
    runtime.mkdir(exist_ok=True)
    try:
        with (runtime/"ollama.log").open("ab") as log:
            process=subprocess.Popen([executable,"serve"],env=environment,stdout=log,stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    except OSError:
        print("Could not start Ollama. Evidence search remains available.",flush=True)
        return None
    for _ in range(24):
        if available():
            print("Started a localhost Ollama service; no models were downloaded.",flush=True)
            return process
        if process.poll() is not None:
            return None
        time.sleep(.25)
    process.terminate()
    print("Ollama did not become ready. Evidence search remains available.",flush=True)
    return None


if __name__=="__main__":
    print("Local service version:",available() or "unavailable")
    print("This app never downloads a model inside an investigation.")
