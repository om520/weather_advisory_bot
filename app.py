import sys
from pathlib import Path

# Explicitly add .venv site-packages to sys.path
_ROOT = Path(__file__).resolve().parent
_VENV_SITE = _ROOT / ".venv" / "Lib" / "site-packages"
if _VENV_SITE.exists() and str(_VENV_SITE) not in sys.path:
    sys.path.insert(0, str(_VENV_SITE))

import uvicorn
from api.main import app

if __name__ == "__main__":
    print("Starting Weather Advisory Chatbot Server on http://127.0.0.1:8000 ...", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000)
