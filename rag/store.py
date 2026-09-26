from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from typing import Any

import numpy as np
import requests

from ollama import ports
from utils.errors import Error

from .chunker import Chunk

try:
    import chromadb
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
    HAS_CHROMADB = True
except Exception:
    chromadb = None
    HAS_CHROMADB = False
    Documents = list[str]
    Embeddings = list[list[float]]
    EmbeddingFunction = object

CHROMA_DIR: Path = Path.home() / ".webgpt" / "rag" / "chroma"
COLLECTION_NAME: str = "knowledge"
EMBED_MODEL: str = "nomic-embed-text"
OLLAMA_URL: str = "http://127.0.0.1:11434"
EMBEDDINGS_PATH: str = "/api/embeddings"
EMBED_TIMEOUT_SECONDS: int = 120
DEFAULT_TOP_K: int = 8
ALL_CHUNKS: int = 0

def _resolve_k_helper(collection: Any, top_k: int) -> int:
    count: int = collection.count()
    if top_k <= 0 or top_k > count:
        return count
    return top_k

_store: VectorStore | None = None

def get_store(port: int | None = None) -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore(port=port)
    elif port is not None:
        _store.set_port(port)
    return _store

def reset_store() -> None:
    global _store
    _store = None

class OllamaEmbeddingFunction(EmbeddingFunction):
    def __init__(self, url: str | None = None, model_name: str = EMBED_MODEL, port: int | None = None) -> None:
        self._url = url
        self._port = port
        self._model_name = model_name

    def set_port(self, port: int | None) -> None:
        self._port = port
        if port is not None:
            self._url = f"http://127.0.0.1:{port}"

    def _resolved_url(self) -> str:
        if self._url:
            return self._url
        if self._port:
            return f"http://127.0.0.1:{self._port}"
        live_port = ports.find_ollama()
        if live_port:
            return f"http://127.0.0.1:{live_port}"
        return OLLAMA_URL

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        url = self._resolved_url()
        for text in input:
            try:
                response = requests.post(
                    f"{url}{EMBEDDINGS_PATH}",
                    json={"model": self._model_name, "prompt": text},
                    timeout=EMBED_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
            except Exception:
                embeddings.append([0.0] * 768)
        return embeddings

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "local-ollama-embedding"

class SQLiteCollection:
    def __init__(self, db_path: Path, embed_fn: OllamaEmbeddingFunction):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._embed = embed_fn
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document TEXT,
                    source TEXT,
                    category TEXT,
                    active INTEGER,
                    embedding TEXT
                )
            """)

    def count(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM chunks WHERE active = 1")
            row = cur.fetchone()
            return row[0] if row else 0

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        embeddings = self._embed(documents)
        with sqlite3.connect(self._db_path) as conn:
            for cid, doc, meta, emb in zip(ids, documents, metadatas, embeddings):
                conn.execute(
                    "INSERT OR REPLACE INTO chunks (id, document, source, category, active, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                    (cid, doc, meta.get("source", ""), meta.get("category", ""), 1 if meta.get("active", True) else 0, json.dumps(emb)),
                )

    def update(self, ids: list[str], metadatas: list[dict[str, Any]]) -> None:
        with sqlite3.connect(self._db_path) as conn:
            for cid, meta in zip(ids, metadatas):
                active = 1 if meta.get("active", True) else 0
                conn.execute("UPDATE chunks SET active = ? WHERE id = ?", (active, cid))

    def delete(self, ids: list[str]) -> None:
        with sqlite3.connect(self._db_path) as conn:
            for cid in ids:
                conn.execute("DELETE FROM chunks WHERE id = ?", (cid,))

    def get(
        self,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        query = "SELECT id, document, source, category, active FROM chunks WHERE 1=1"
        params: list[Any] = []
        if ids:
            placeholders = ",".join("?" for _ in ids)
            query += f" AND id IN ({placeholders})"
            params.extend(ids)
        if where:
            if "category" in where:
                cat_val = where["category"]
                if isinstance(cat_val, dict) and "$ne" in cat_val:
                    query += " AND category != ?"
                    params.append(cat_val["$ne"])
                else:
                    query += " AND category = ?"
                    params.append(cat_val)
            if "active" in where:
                query += " AND active = ?"
                params.append(1 if where["active"] else 0)
        if where_document and "$contains" in where_document:
            query += " AND document LIKE ?"
            params.append(f"%{where_document['$contains']}%")
        if limit:
            query += f" LIMIT {int(limit)}"

        with sqlite3.connect(self._db_path) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            out_ids = [r[0] for r in rows]
            out_docs = [r[1] for r in rows]
            out_metas = [{"source": r[2], "category": r[3], "active": bool(r[4])} for r in rows]
            return {"ids": out_ids, "documents": out_docs, "metadatas": out_metas}

    def query(
        self,
        query_texts: list[str],
        n_results: int = 8,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not query_texts:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        query_text = query_texts[0]
        q_emb_list = self._embed([query_text])[0]
        q_emb = np.array(q_emb_list, dtype=np.float32)
        q_norm = np.linalg.norm(q_emb)

        query = "SELECT id, document, source, category, active, embedding FROM chunks WHERE active = 1"
        params: list[Any] = []
        if where:
            if "$and" in where:
                for cond in where["$and"]:
                    if "category" in cond:
                        c_val = cond["category"]
                        if isinstance(c_val, dict) and "$ne" in c_val:
                            query += " AND category != ?"
                            params.append(c_val["$ne"])
                        else:
                            query += " AND category = ?"
                            params.append(c_val)
                    if "active" in cond:
                        query += " AND active = ?"
                        params.append(1 if cond["active"] else 0)
            elif "category" in where:
                query += " AND category = ?"
                params.append(where["category"])

        with sqlite3.connect(self._db_path) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()

        scored = []
        for r in rows:
            doc_id, doc, src, cat, act, emb_str = r
            if not emb_str:
                continue
            emb = np.array(json.loads(emb_str), dtype=np.float32)
            d_norm = np.linalg.norm(emb)
            if q_norm > 0 and d_norm > 0:
                cosine_sim = float(np.dot(q_emb, emb) / (q_norm * d_norm))
                dist = 1.0 - cosine_sim
            else:
                dist = 1.0
            scored.append((dist, doc, {"source": src, "category": cat, "active": bool(act)}))

        scored.sort(key=lambda x: x[0])
        top = scored[:n_results]
        return {
            "documents": [[x[1] for x in top]],
            "metadatas": [[x[2] for x in top]],
            "distances": [[x[0] for x in top]],
        }

class VectorStore:
    def __init__(self, port: int | None = None, url: str | None = None) -> None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self._embed = OllamaEmbeddingFunction(url=url, model_name=EMBED_MODEL, port=port)
        self._use_chroma = HAS_CHROMADB
        if self._use_chroma:
            try:
                self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            except Exception:
                self._use_chroma = False

        if not self._use_chroma:
            self._sqlite_collection = SQLiteCollection(
                db_path=CHROMA_DIR / "vectors.sqlite3",
                embed_fn=self._embed,
            )

    def set_port(self, port: int | None) -> None:
        self._embed.set_port(port)

    def collection(self) -> Any:
        if self._use_chroma:
            try:
                return self._client.get_or_create_collection(
                    name=COLLECTION_NAME, embedding_function=self._embed,
                )
            except Exception:
                self._use_chroma = False
                self._sqlite_collection = SQLiteCollection(
                    db_path=CHROMA_DIR / "vectors.sqlite3",
                    embed_fn=self._embed,
                )
        return self._sqlite_collection

    def add_chunks(self, chunks: list[Chunk]) -> Error | None:
        if not chunks:
            return None
        return _add_safe_helper(collection=self.collection(), chunks=chunks)

    def deactivate_chunks(self, chunk_ids: list[str]) -> Error | None:
        if not chunk_ids:
            return None
        return _deactivate_safe_helper(collection=self.collection(), chunk_ids=chunk_ids)

    def delete_chunks(self, chunk_ids: list[str]) -> Error | None:
        if not chunk_ids:
            return None
        return _delete_safe_helper(collection=self.collection(), chunk_ids=chunk_ids)

    def query(self, text: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]] | Error:
        return _query_safe_helper(collection=self.collection(), text=text, top_k=top_k)

    def count(self) -> int:
        return self.collection().count()

def _add_safe_helper(collection: Any, chunks: list[Chunk]) -> Error | None:
    try:
        collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[_meta_helper(chunk=c) for c in chunks],
        )
    except Exception as exc:
        return Error(message=str(exc))
    return None

def _meta_helper(chunk: Chunk) -> dict[str, Any]:
    return {"source": chunk.source, "category": chunk.category, "active": True}

def _deactivate_safe_helper(collection: Any, chunk_ids: list[str]) -> Error | None:
    try:
        existing: dict[str, Any] = collection.get(ids=chunk_ids)
        new_metas: list[dict[str, Any]] = [
            {**m, "active": False} for m in existing.get("metadatas", [])
        ]
        collection.update(ids=existing["ids"], metadatas=new_metas)
    except Exception as exc:
        return Error(message=str(exc))
    return None

def _delete_safe_helper(collection: Any, chunk_ids: list[str]) -> Error | None:
    try:
        collection.delete(ids=chunk_ids)
    except Exception as exc:
        return Error(message=str(exc))
    return None

def _extract_identifiers(text: str) -> list[str]:
    tokens = re.findall(r"\b[A-Za-z0-9_-]{4,20}\b", text)
    ids: list[str] = []
    for t in tokens:
        if (any(c.isdigit() for c in t) and any(c.isalpha() for c in t)) or t.upper().startswith("PN"):
            ids.append(t)
    return list(dict.fromkeys(ids))

def _query_safe_helper(collection: Any, text: str, top_k: int) -> list[dict[str, Any]] | Error:
    last: Exception | None = None
    for _ in range(2):
        try:
            count = collection.count()
            if count == 0:
                return []

            exact_matches: list[dict[str, Any]] = []
            seen_texts: set[str] = set()

            candidates = _extract_identifiers(text)
            for code in candidates:
                try:
                    res = collection.get(
                        where_document={"$contains": code},
                        where={"active": True},
                        limit=top_k,
                    )
                    for doc, meta in zip(res.get("documents", []), res.get("metadatas", [])):
                        if doc not in seen_texts:
                            seen_texts.add(doc)
                            exact_matches.append({
                                "text": doc,
                                "source": meta.get("source", ""),
                                "category": meta.get("category", ""),
                            })
                except Exception:
                    pass

            mem_items: list[dict[str, Any]] = []
            try:
                mem_res = collection.query(
                    query_texts=[text],
                    n_results=min(top_k, count),
                    where={"$and": [{"category": "memory"}, {"active": True}]},
                )
                mem_items = _flatten_with_dist_helper(raw=mem_res)
            except Exception:
                pass

            kb_items: list[dict[str, Any]] = []
            try:
                kb_res = collection.query(
                    query_texts=[text],
                    n_results=min(top_k, count),
                    where={"$and": [{"category": {"$ne": "memory"}}, {"active": True}]},
                )
                kb_items = _flatten_with_dist_helper(raw=kb_res)
            except Exception:
                try:
                    fallback_res = collection.query(
                        query_texts=[text],
                        n_results=min(top_k, count),
                        where={"active": True},
                    )
                    kb_items = _flatten_with_dist_helper(raw=fallback_res)
                except Exception:
                    pass

            vector_matches = sorted(mem_items + kb_items, key=lambda x: x.get("dist", 9999.0))

            combined: list[dict[str, Any]] = list(exact_matches)
            for item in vector_matches:
                if item["text"] not in seen_texts:
                    seen_texts.add(item["text"])
                    combined.append({
                        "text": item["text"],
                        "source": item["source"],
                        "category": item["category"],
                    })

            max_allowed = max(top_k, len(exact_matches))
            return combined[:max_allowed]
        except Exception as exc:
            last = exc
    return Error(message=str(last))

def _flatten_with_dist_helper(raw: dict[str, Any]) -> list[dict[str, Any]]:
    docs = raw.get("documents", [[]])
    metas = raw.get("metadatas", [[]])
    dists = raw.get("distances", [[]])
    if not docs or not docs[0]:
        return []
    doc_list = docs[0]
    meta_list = metas[0] if metas and metas[0] else [{}] * len(doc_list)
    dist_list = dists[0] if dists and dists[0] else [9999.0] * len(doc_list)
    return [
        {
            "text": doc,
            "source": meta.get("source", ""),
            "category": meta.get("category", ""),
            "dist": dist,
        }
        for doc, meta, dist in zip(doc_list, meta_list, dist_list)
    ]

def _flatten_helper(raw: dict[str, Any]) -> list[dict[str, Any]]:
    docs = raw.get("documents", [[]])
    metas = raw.get("metadatas", [[]])
    if not docs or not docs[0]:
        return []
    return [
        {"text": doc, "source": meta.get("source", ""), "category": meta.get("category", "")}
        for doc, meta in zip(docs[0], metas[0])
    ]
