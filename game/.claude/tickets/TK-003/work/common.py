"""Общее: схема БД, стемминг для FTS, эмбеддинги."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("MECH_DB", ROOT / "mechanics.db"))
MODEL_NAME = os.environ.get("MECH_MODEL", "intfloat/multilingual-e5-base")

KINDS = ["mechanic", "rule", "number", "catalog_item", "enemy", "boss", "spell",
         "relic", "room", "ui", "audio", "other"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS games(
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, title TEXT, engine TEXT,
  spec_path TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS systems(
  id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id),
  slug TEXT NOT NULL, title TEXT, spec_file TEXT, UNIQUE(game_id, slug));
CREATE TABLE IF NOT EXISTS entries(
  id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id),
  system_id INTEGER REFERENCES systems(id), collection TEXT, kind TEXT NOT NULL,
  title TEXT, summary TEXT, body_md TEXT, numbers_json TEXT, tags TEXT,
  spec_file TEXT, anchor TEXT, source_ref TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS collections(
  slug TEXT PRIMARY KEY, title TEXT, description TEXT);
CREATE INDEX IF NOT EXISTS ix_entries_system ON entries(system_id);
CREATE TABLE IF NOT EXISTS links(
  from_id INTEGER NOT NULL, to_id INTEGER NOT NULL, kind TEXT,
  PRIMARY KEY(from_id, to_id, kind));
CREATE TABLE IF NOT EXISTS embeddings(
  entry_id INTEGER NOT NULL, model TEXT NOT NULL, dim INTEGER NOT NULL,
  vec BLOB NOT NULL, text_hash TEXT, PRIMARY KEY(entry_id, model));
-- FTS хранит СТЕММИРОВАННЫЙ текст (русская морфология); rowid = entries.id
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
  title, summary, body, tags, tokenize='unicode61 remove_diacritics 2');
"""


TAXONOMY_PATH = Path(os.environ.get("MECH_TAXONOMY", ROOT / "taxonomy" / "collections.yaml"))
COLL_EXTRA_COLS = ["family", "family_title", "automation", "priority", "cross_game_key",
                   "record_schema_json", "extraction_source", "wol_count"]


def load_taxonomy(con) -> int:
    """collections <- taxonomy/collections.yaml (источник истины: reverse-kit/taxonomy). Вернёт число коллекций."""
    import yaml
    d = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    fam = {f["id"]: f["title_ru"] for f in d["families"]}
    import json as _j
    con.execute("DELETE FROM collections")
    for c in d["collections"]:
        con.execute(
            "INSERT INTO collections(slug,title,description,family,family_title,automation,priority,"
            "cross_game_key,record_schema_json,extraction_source,wol_count) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (c["id"], c["title_ru"], c.get("definition_ru"), c["family"], fam.get(c["family"]),
             c.get("automation"), c.get("priority"), c.get("cross_game_key"),
             _j.dumps(c.get("record_schema"), ensure_ascii=False), ",".join(c.get("extraction_source") or []),
             c.get("wol_count")))
    con.commit()
    return len(d["collections"])


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = [r[1] for r in con.execute("PRAGMA table_info(entries)")]
    if "collection" not in cols:  # миграция старой БД
        con.execute("ALTER TABLE entries ADD COLUMN collection TEXT")
    con.execute("CREATE INDEX IF NOT EXISTS ix_entries_game ON entries(game_id, kind)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_entries_coll ON entries(collection)")
    ccols = [r[1] for r in con.execute("PRAGMA table_info(collections)")]
    for col in COLL_EXTRA_COLS:
        if col not in ccols:
            con.execute(f"ALTER TABLE collections ADD COLUMN {col} " + ("INTEGER" if col == "wol_count" else "TEXT"))
    import tag as _tag  # таблицы тегов (tags, tag_syn, record_tags) — см. tag.py
    _tag.ensure_schema(con)
    if TAXONOMY_PATH.exists() and not con.execute("SELECT 1 FROM collections LIMIT 1").fetchone():
        load_taxonomy(con)
    con.commit()
    return con


def utf8_stdout() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


# ---------- стемминг ----------
_stem = None
_TOK = re.compile(r"[\w]+", re.UNICODE)
STOP = set("""и в во не на с со к по о об от до из за для при под над без что как это
этот эта эти то так а но или же бы ли ни у я мы вы он она они его ее их есть быть
был была были будет чтобы если когда где какой какая какие каким чем кто себя свой
своя свои также только уже ещё еще можно нужно""".split())


def stemmer():
    global _stem
    if _stem is None:
        import snowballstemmer
        _stem = snowballstemmer.stemmer("russian")
    return _stem


def stem_tokens(text: str, drop_stop: bool = False) -> list[str]:
    st = stemmer()
    out = []
    for t in _TOK.findall(text.lower().replace("ё", "е")):
        if drop_stop and t in STOP:
            continue
        out.append(st.stemWord(t) if not t.isascii() or len(t) > 3 else t)
    return out


def stem_text(text: str) -> str:
    return " ".join(stem_tokens(text or ""))


def fts_query(q: str) -> str:
    toks = [t for t in stem_tokens(q, drop_stop=True) if t]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(toks))


# ---------- эмбеддинги ----------
_model = None


DEVICE = os.environ.get("MECH_DEVICE")  # cpu | cuda; по умолчанию: ingest — cuda (если есть), поиск — cpu


def get_model(name: str = MODEL_NAME, prefer_cuda: bool = False):
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        dev = DEVICE or ("cuda" if prefer_cuda and torch.cuda.is_available() else "cpu")
        _model = SentenceTransformer(name, device=dev)
        _model.max_seq_length = 512
    return _model


def e5_prefix(model_name: str, kind: str) -> str:
    return (f"{kind}: " if "e5" in model_name.lower() else "")


SERVE_PORT = int(os.environ.get("MECH_PORT", "8765"))


def _remote_embed(texts, kind, name):
    """Если запущен `mech.py serve` — берём эмбеддинг у него (мгновенно, без загрузки torch)."""
    import json as _j
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{SERVE_PORT}/embed",
                                     _j.dumps({"texts": texts, "kind": kind, "model": name}).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return np.array(_j.loads(r.read())["vecs"], dtype=np.float32)
    except Exception:
        return None


def embed(texts: list[str], kind: str, name: str = MODEL_NAME, batch: int = 16) -> np.ndarray:
    if kind == "query" and len(texts) <= 8 and os.environ.get("MECH_NO_SERVER") != "1":
        v = _remote_embed(texts, kind, name)
        if v is not None:
            return v
    m = get_model(name, prefer_cuda=len(texts) > 32)
    pre = e5_prefix(name, kind)
    v = m.encode([pre + t for t in texts], batch_size=batch, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=len(texts) > 50)
    return v.astype(np.float32)


def text_hash(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:16]


def load_vectors(con, model: str, where: str = "", params: tuple = ()):
    """Вернёт (ids[int], matrix[N,dim]) для записей, подходящих под where (по entries e)."""
    sql = ("SELECT e.id, m.vec, m.dim FROM embeddings m JOIN entries e ON e.id=m.entry_id "
           "JOIN games g ON g.id=e.game_id LEFT JOIN systems s ON s.id=e.system_id "
           "WHERE m.model=? " + (f"AND {where}" if where else ""))
    rows = con.execute(sql, (model, *params)).fetchall()
    if not rows:
        return np.zeros(0, dtype=np.int64), np.zeros((0, 1), dtype=np.float32)
    ids = np.fromiter((r[0] for r in rows), dtype=np.int64, count=len(rows))
    mat = np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
    return ids, mat
