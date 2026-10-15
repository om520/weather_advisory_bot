import sys
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_VENV_PYTHON = _ROOT / ".venv" / "Scripts" / "python.exe"

# If started with system Python (e.g., Python 3.14) instead of the venv Python (3.11),
# auto-switch to the venv Python so binary extensions (pydantic_core) load properly.
if _VENV_PYTHON.exists() and Path(sys.executable).resolve() != _VENV_PYTHON.resolve():
    print(f"Switching to project virtual environment ({_VENV_PYTHON}) ...", flush=True)
    sys.exit(subprocess.call([str(_VENV_PYTHON), *sys.argv]))

import uvicorn
from api.main import app

if __name__ == "__main__":
    print("Starting Weather Advisory Chatbot Server on http://127.0.0.1:8000 ...", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000)

