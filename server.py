from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import shutil
import sys
import threading
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from attachments import extract as attachment_extract
from chat import controller, modes as chat_modes
from config import sessions
from config.sessions import Session, SessionMeta
from local.catalog import CATEGORIES, FileCatalog, category_for_path
from ollama import client as ollama_client, ports as ollama_ports
from rag import build_index, format_context, retrieve
from rag.memory import index_session_memory, remove_session_memory
from rag.store import get_store
from utils.errors import Error

WEBGPT_HOME: Path = Path.home() / ".webgpt"
UPLOADS_DIR: Path = WEBGPT_HOME / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
def _get_static_dir() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = base_dir / "static"
        if candidate.exists():
            return candidate
        exe_candidate = Path(sys.executable).parent / "static"
        if exe_candidate.exists():
            return exe_candidate
    return Path(__file__).parent / "static"

STATIC_DIR: Path = _get_static_dir()
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

PROCUREMENT_DOWNLOADS_DIR: Path = Path("/home/jamaica/Downloads/GPT-Procurement_Intelligent")

_active_stops: dict[str, threading.Event] = {}
_stops_lock = threading.Lock()
_current_model: str = ""

def get_current_model(port: int | None) -> str:
    global _current_model
    if _current_model:
        return _current_model
    if port:
        _current_model = controller.default_model(port)
    return _current_model or "deepseek-r1:7b"

@asynccontextmanager
async def lifespan(app: FastAPI):
    WEBGPT_HOME.mkdir(parents=True, exist_ok=True)
    (WEBGPT_HOME / "rag").mkdir(parents=True, exist_ok=True)
    sessions.ensure_dir()
    yield

app = FastAPI(title="WebGPT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def get_status() -> dict[str, Any]:
    port = controller.detect_port()
    model = get_current_model(port)
    installed_models: list[str] = []
    if port:
        res = ollama_client.list_models(port=port)
        if isinstance(res, list):
            installed_models = res

    catalog = FileCatalog()
    all_files = catalog.entries()
    active_files = [f for f in all_files if f.active]

    vector_count = 0
    try:
        store = get_store(port=port)
        vector_count = store.count()
    except Exception:
        pass

    all_sessions = sessions.list_sessions()

    return {
        "status": "online",
        "ollama": {
            "running": port is not None,
            "port": port,
            "active_model": model,
            "available_models": installed_models,
        },
        "rag": {
            "vectors_count": vector_count,
            "documents_count": len(all_files),
            "active_documents_count": len(active_files),
        },
        "sessions_count": len(all_sessions),
        "procurement_demo_available": PROCUREMENT_DOWNLOADS_DIR.exists(),
    }

@app.get("/api/models")
def list_models() -> dict[str, Any]:
    port = controller.detect_port()
    installed: list[str] = []
    if port:
        res = ollama_client.list_models(port=port)
        if isinstance(res, list):
            installed = res
    active = get_current_model(port)
    return {"models": installed, "active_model": active}

class ModelSelectRequest(BaseModel):
    model: str

@app.post("/api/models/select")
def select_model(req: ModelSelectRequest) -> dict[str, Any]:
    global _current_model
    _current_model = req.model.strip()
    return {"status": "ok", "active_model": _current_model}

@app.get("/api/sessions")
def list_chat_sessions() -> list[dict[str, Any]]:
    metas = sessions.list_sessions()
    result: list[dict[str, Any]] = []
    for m in metas:
        s = sessions.load_session(m.id)
        msg_count = len(s.messages) if not isinstance(s, Error) else 0
        last_msg = s.messages[-1].get("content", "")[:120] if not isinstance(s, Error) and s.messages else ""
        result.append({
            "id": m.id,
            "title": m.title,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
            "message_count": msg_count,
            "snippet": last_msg,
        })
    return result

class SessionCreateRequest(BaseModel):
    title: str | None = None

@app.post("/api/sessions")
def create_chat_session(req: SessionCreateRequest | None = None) -> dict[str, Any]:
    s = sessions.create_session()
    if req and req.title:
        sessions.rename_session(s.meta.id, req.title)
        s.meta.title = req.title
    return {
        "id": s.meta.id,
        "title": s.meta.title,
        "created_at": s.meta.created_at,
        "updated_at": s.meta.updated_at,
        "messages": s.messages,
        "modes": s.modes,
    }

@app.get("/api/sessions/{session_id}")
def get_chat_session(session_id: str) -> dict[str, Any]:
    s = sessions.load_session(session_id)
    if isinstance(s, Error):
        raise HTTPException(status_code=404, detail=str(s))
    return {
        "id": s.meta.id,
        "title": s.meta.title,
        "created_at": s.meta.created_at,
        "updated_at": s.meta.updated_at,
        "messages": s.messages,
        "modes": s.modes,
    }

class SessionUpdateRequest(BaseModel):
    title: str | None = None
    modes: list[str] | None = None

@app.patch("/api/sessions/{session_id}")
def update_chat_session(session_id: str, req: SessionUpdateRequest) -> dict[str, Any]:
    if req.title is not None:
        err = sessions.rename_session(session_id, req.title)
        if isinstance(err, Error):
            raise HTTPException(status_code=400, detail=str(err))
    if req.modes is not None:
        err = sessions.set_modes(session_id, req.modes)
        if isinstance(err, Error):
            raise HTTPException(status_code=400, detail=str(err))

    s = sessions.load_session(session_id)
    if isinstance(s, Error):
        raise HTTPException(status_code=404, detail=str(s))
    return {
        "id": s.meta.id,
        "title": s.meta.title,
        "created_at": s.meta.created_at,
        "updated_at": s.meta.updated_at,
        "messages": s.messages,
        "modes": s.modes,
    }

@app.delete("/api/sessions/{session_id}")
def delete_chat_session(session_id: str) -> dict[str, Any]:
    remove_session_memory(session_id)
    err = sessions.delete_session(session_id)
    if isinstance(err, Error):
        raise HTTPException(status_code=400, detail=str(err))
    return {"status": "ok", "deleted": session_id}

class ChatStreamRequest(BaseModel):
    session_id: str
    prompt: str
    model: str | None = None
    modes: list[str] = ["deepthink"]
    attachments: list[dict[str, str]] = []

@app.post("/api/chat/stream")
async def chat_stream(req: ChatStreamRequest):
    port = controller.detect_port()
    if not port:
        raise HTTPException(status_code=503, detail="Ollama server is not running on port range 11434-11550.")

    model = req.model or get_current_model(port)
    session_id = req.session_id

    append_err = sessions.append_message(session_id, "user", req.prompt)
    if isinstance(append_err, Error):
        raise HTTPException(status_code=400, detail=str(append_err))

    stop_event = threading.Event()
    with _stops_lock:
        _active_stops[session_id] = stop_event

    async def sse_event_generator():
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_token(token: str):
            loop.call_soon_threadsafe(queue.put_nowait, ("token", token))

        def on_thinking(thought: str):
            loop.call_soon_threadsafe(queue.put_nowait, ("thinking", thought))

        def background_worker():
            try:
                s = sessions.load_session(session_id)
                history = s.messages[:-1] if not isinstance(s, Error) else []

                att_tuples: list[tuple[str, str]] = [
                    (att.get("name", "attachment"), att.get("content", ""))
                    for att in req.attachments
                ]

                search_query = controller._contextual_query_helper(prompt=req.prompt, history=history)
                chunks = retrieve(search_query, port=port)
                loop.call_soon_threadsafe(queue.put_nowait, ("rag", chunks))

                augmented = controller._augment_helper(prompt=req.prompt, attachments=att_tuples, modes=set(req.modes))
                context = format_context(chunks)
                if context:
                    augmented = f"{context}\n\n{augmented}"

                messages_payload: list[ollama_client.ChatMessage] = [
                    {"role": "system", "content": controller.SYSTEM_PROMPT}
                ]
                for msg in history:
                    r = msg.get("role")
                    c = msg.get("content")
                    if r in ("user", "assistant") and c:
                        messages_payload.append({"role": r, "content": c})
                messages_payload.append({"role": "user", "content": augmented})

                think_enabled = "deepthink" in req.modes

                full_result: str | Error = ollama_client.stream_chat(
                    port=port,
                    model=model,
                    messages=messages_payload,
                    on_token=on_token,
                    on_thinking=on_thinking,
                    think=think_enabled,
                    stop_event=stop_event,
                )

                if isinstance(full_result, Error):
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", str(full_result)))
                else:
                    sessions.append_message(session_id, "assistant", full_result)
                    loaded = sessions.load_session(session_id)
                    if not isinstance(loaded, Error):
                        index_session_memory(loaded)
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", full_result))

            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("finished", None))
                with _stops_lock:
                    _active_stops.pop(session_id, None)

        thread = threading.Thread(target=background_worker, daemon=True)
        thread.start()

        yield f"event: start\ndata: {json.dumps({'session_id': session_id, 'model': model})}\n\n"

        while True:
            ev_type, payload = await queue.get()
            if ev_type == "finished":
                break
            elif ev_type == "rag":
                yield f"event: rag\ndata: {json.dumps({'chunks': payload})}\n\n"
            elif ev_type == "thinking":
                yield f"event: thinking\ndata: {json.dumps({'content': payload})}\n\n"
            elif ev_type == "token":
                yield f"event: token\ndata: {json.dumps({'content': payload})}\n\n"
            elif ev_type == "done":
                updated_title = ""
                s = sessions.load_session(session_id)
                if not isinstance(s, Error):
                    updated_title = s.meta.title
                yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'title': updated_title, 'full_content': payload})}\n\n"
            elif ev_type == "error":
                yield f"event: error\ndata: {json.dumps({'error': payload})}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

class StopRequest(BaseModel):
    session_id: str

@app.post("/api/chat/stop")
def stop_generation(req: StopRequest) -> dict[str, Any]:
    with _stops_lock:
        stop_ev = _active_stops.get(req.session_id)
        if stop_ev:
            stop_ev.set()
            return {"status": "stopped", "session_id": req.session_id}
    return {"status": "not_running", "session_id": req.session_id}

@app.get("/api/knowledge")
def list_knowledge_entries() -> list[dict[str, Any]]:
    catalog = FileCatalog()
    entries = catalog.entries()
    out: list[dict[str, Any]] = []
    for e in entries:
        p = Path(e.path)
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        out.append({
            "path": e.path,
            "filename": p.name,
            "category": e.category,
            "active": e.active,
            "last_hash": e.last_hash,
            "chunk_count": len(e.chunk_ids),
            "indexed_at": e.indexed_at,
            "exists": exists,
            "size": size,
        })
    return out

@app.post("/api/knowledge/upload")
async def upload_knowledge_file(file: UploadFile = File(...), category: str | None = Form(None)):
    clean_filename = Path(file.filename or "upload").name
    dest_path = UPLOADS_DIR / clean_filename

    with dest_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    resolved_category = category
    if not resolved_category:
        try:
            resolved_category = category_for_path(str(dest_path)).value
        except Exception:
            resolved_category = "txt"

    catalog = FileCatalog()
    err = catalog.add(path=str(dest_path), category=resolved_category)
    if isinstance(err, Error):
        raise HTTPException(status_code=400, detail=str(err))
    save_err = catalog.save()
    if isinstance(save_err, Error):
        raise HTTPException(status_code=500, detail=str(save_err))

    return {
        "status": "uploaded",
        "path": str(dest_path),
        "filename": dest_path.name,
        "category": resolved_category,
        "size": dest_path.stat().st_size,
    }

class KnowledgeUpdateRequest(BaseModel):
    path: str
    category: str | None = None
    active: bool | None = None

@app.patch("/api/knowledge/entry")
def update_knowledge_entry(req: KnowledgeUpdateRequest) -> dict[str, Any]:
    catalog = FileCatalog()
    if req.category is not None:
        err = catalog.set_category(req.path, req.category)
        if isinstance(err, Error):
            raise HTTPException(status_code=400, detail=str(err))
    if req.active is not None:
        if req.active:
            err = catalog.activate(req.path)
        else:
            err = catalog.deactivate(req.path)
        if isinstance(err, Error):
            raise HTTPException(status_code=400, detail=str(err))

    save_err = catalog.save()
    if isinstance(save_err, Error):
        raise HTTPException(status_code=500, detail=str(save_err))
    return {"status": "ok", "path": req.path}

class KnowledgeDeleteRequest(BaseModel):
    path: str

@app.delete("/api/knowledge/entry")
def delete_knowledge_entry(req: KnowledgeDeleteRequest) -> dict[str, Any]:
    catalog = FileCatalog()
    err = catalog.remove(req.path)
    if isinstance(err, Error):
        raise HTTPException(status_code=400, detail=str(err))
    save_err = catalog.save()
    if isinstance(save_err, Error):
        raise HTTPException(status_code=500, detail=str(save_err))
    return {"status": "deleted", "path": req.path}

class KnowledgeSyncRequest(BaseModel):
    force: bool = False

@app.post("/api/knowledge/sync")
def sync_knowledge_index(req: KnowledgeSyncRequest | None = None) -> dict[str, Any]:
    force = req.force if req else False
    report, _manifest = build_index(force=force)
    port = controller.detect_port()
    store = get_store(port=port)
    vector_count = store.count()
    return {
        "status": "synced",
        "summary": report.summary(),
        "details": {
            "added": report.added,
            "updated": report.updated,
            "unchanged": report.unchanged,
            "deactivated": report.deactivated,
            "removed": report.removed,
            "memories": report.memories,
            "errors": report.errors,
        },
        "total_vectors": vector_count,
    }

@app.get("/api/procurement/available")
def get_procurement_available() -> dict[str, Any]:
    if not PROCUREMENT_DOWNLOADS_DIR.exists():
        return {"available": False, "files": []}

    files = []
    for f in PROCUREMENT_DOWNLOADS_DIR.iterdir():
        if f.is_file() and not f.name.startswith("."):
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "ext": f.suffix.lower(),
            })
    return {"available": True, "files": files, "count": len(files)}

@app.post("/api/procurement/import")
def import_procurement_data() -> dict[str, Any]:
    if not PROCUREMENT_DOWNLOADS_DIR.exists():
        raise HTTPException(status_code=404, detail="Procurement directory not found.")

    catalog = FileCatalog()
    imported: list[str] = []
    skipped: list[str] = []

    for f in PROCUREMENT_DOWNLOADS_DIR.iterdir():
        if f.is_file() and not f.name.startswith("."):
            dest = UPLOADS_DIR / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
            try:
                cat = category_for_path(str(dest)).value
                err = catalog.add(path=str(dest), category=cat)
                if isinstance(err, Error):
                    skipped.append(f.name)
                else:
                    imported.append(f.name)
            except Exception:
                skipped.append(f.name)

    catalog.save()
    report, _ = build_index(force=False)
    return {
        "imported": imported,
        "skipped": skipped,
        "report": report.summary(),
    }

@app.post("/api/attachments/extract")
async def extract_attachment(file: UploadFile = File(...)):
    clean_name = Path(file.filename or "attachment").name
    tmp_path = UPLOADS_DIR / f"_tmp_{clean_name}"
    try:
        with tmp_path.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)

        content = attachment_extract.read(str(tmp_path))
        if isinstance(content, Error):
            raise HTTPException(status_code=400, detail=str(content))

        return {
            "name": clean_name,
            "content": content,
            "size": tmp_path.stat().st_size,
        }
    finally:
        tmp_path.unlink(missing_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(status_code=404, content={"message": "Frontend not found. Please build static assets."})
    return FileResponse(str(index_file))

def main() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Starting WebGPT server on http://{host}:{port} ...")
    uvicorn.run("server:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
