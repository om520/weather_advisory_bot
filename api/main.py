"""
api/main.py — FastAPI server for the weather advisory chatbot.

Serves:
  POST /chat          → invoke LangGraph, return structured reply
  GET  /              → serve the HTML template
  GET  /health        → liveness check

Session memory: each browser tab gets a unique session_id (UUID).
The LangGraph MemorySaver keyed on that session_id handles follow-ups.
"""

import uuid
import yaml
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph import compile_graph

_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _ROOT / "sops" / "config.yaml"
TEMPLATE_DIR = _ROOT / "template"

# Compile graph once at startup (holds MemorySaver in memory)
_graph = None
_config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _config
    with open(CONFIG_PATH, encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    _graph = compile_graph()
    yield


app = FastAPI(title="Weather Advisory Chatbot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""   # empty = new session


class ChatResponse(BaseModel):
    reply: str
    severity: str | None
    badge_label: str
    badge_icon: str
    primary_sop: str | None
    also_applies: list[str]
    location: str
    activity: str
    time_window: str
    reply_source: str
    session_id: str
    turn_id: str
    weather_snapshot: dict | None  # full weather values used for this request
    error: dict | None = None


# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    turn_id = str(uuid.uuid4())

    init_state = {
        "user_message": req.message,
        "config": _config,
        "turn_id": turn_id,
        "weather_values": {},
        "raw_forecast": None,
        "matched_sops": [],
        "also_applies": [],
        "primary_sop": None,
        "geo_result": None,
        "geo_failed": False,
        "weather_failed": False,
        "reply_source": "",
        "severity": None,
    }

    try:
        result = _graph.invoke(
            init_state,
            config={"configurable": {"thread_id": session_id}},
        )
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "too many requests" in err_str.lower() or "rate limit" in err_str.lower():
            code = "RATE_LIMIT_EXCEEDED"
            meaning = "API Rate Limit Exceeded"
            what_happened = "You asked questions too rapidly, exceeding the backend AI provider's quota (4 RPM)."
            what_to_do = "Please wait 15 seconds before sending your next question."
        elif "timed out" in err_str.lower() or "read timeout" in err_str.lower():
            code = "API_TIMEOUT"
            meaning = "Upstream API Timeout"
            what_happened = "An upstream service (like the LLM or Open-Meteo) took too long to respond."
            what_to_do = "Please try asking your question again."
        else:
            code = "SYSTEM_ERROR"
            meaning = "Internal Backend Exception"
            what_happened = "The server encountered a critical boundary failure while evaluating your request."
            what_to_do = "Review the technical details below."

        return ChatResponse(
            reply="",
            severity="danger",
            badge_label="System Error",
            badge_icon="⚠️",
            primary_sop=None,
            also_applies=[],
            location="",
            activity="",
            time_window="",
            reply_source="error_handler",
            session_id=session_id,
            turn_id=turn_id,
            weather_snapshot=None,
            error={
                "code": code,
                "meaning": meaning,
                "what_happened": what_happened,
                "what_to_do": what_to_do,
                "technical": err_str
            }
        )

    primary = result.get("primary_sop")
    also = result.get("also_applies", [])

    geo = result.get("geo_result") or {}
    return ChatResponse(
        reply=result.get("reply", ""),
        severity=result.get("severity"),
        badge_label=result.get("badge_label", "No guidance"),
        badge_icon=result.get("badge_icon", ""),
        primary_sop=primary["id"] if primary else None,
        also_applies=[s["id"] for s in also],
        location=geo.get("name") or result.get("location", ""),
        activity=result.get("activity", ""),
        time_window=result.get("time_window_label", "today"),
        reply_source=result.get("reply_source", ""),
        session_id=session_id,
        turn_id=turn_id,
        weather_snapshot=result.get("weather_values") or None,
        error=result.get("error"),
    )



@app.get("/", response_class=HTMLResponse)
def index():
    html_path = TEMPLATE_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
