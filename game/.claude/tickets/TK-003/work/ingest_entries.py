"""Загрузка entries.jsonl (записи К4 сборщика reverse-kit) в mechanics.db.

    python ingest_entries.py --entries path/entries.jsonl [--db copy.db] [--no-embed]

- запись -> коллекция по полю collection (пусто -> эвристика ingest.assign_collection);
- без дублей: со спекой/данными игры (не-К4 строки) и внутри файла — по хешу нормализованного title+body;
- К4-строки живут в системах со slug 'k4/<system_slug>'; повторный запуск заменяет только их;
- векторы кэшируются по text_hash (по всей БД и по прежним К4-строкам); формат текста как в ingest.py.
Порядок: сначала ingest.py (он стирает все строки игры, включая К4), затем ingest_entries.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import time
from pathlib import Path

import common as C

EMBED_CHARS = 1800
K4 = "k4/"


def norm_key(title: str, body: str) -> str:
    s = re.sub(r"\s+", " ", f"{title}\n{body}").strip().lower()
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--entries", required=True)
    ap.add_argument("--db", help="путь к копии БД (по умолчанию основная mechanics.db)")
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--model", default=C.MODEL_NAME)
    a = ap.parse_args()
    if a.db:
        C.DB_PATH = Path(a.db)
    import ingest as I
    con = C.connect()
    if C.TAXONOMY_PATH.exists():
        C.load_taxonomy(con)
    now = dt.datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    rows = [json.loads(l) for l in open(a.entries, encoding="utf-8") if l.strip()]
    slugs = {r["game"] for r in rows}
    for game in sorted(slugs):
        g = con.execute("SELECT id FROM games WHERE slug=?", (game,)).fetchone()
        if not g:
            raise SystemExit(f"игры {game} нет в БД: сначала ingest.py")
        gid = g["id"]
        mine = [r["id"] for r in con.execute(
            "SELECT e.id FROM entries e JOIN systems s ON s.id=e.system_id WHERE e.game_id=? AND s.slug LIKE ?",
            (gid, K4 + "%"))]
        # кэш векторов: вся игра (до удаления К4-строк)
        cache = {r[0]: r[1] for r in con.execute(
            "SELECT m.text_hash, m.vec FROM embeddings m JOIN entries e ON e.id=m.entry_id "
            "WHERE e.game_id=? AND m.model=?", (gid, a.model))}
        for k in range(0, len(mine), 500):
            part = mine[k:k + 500]
            q = ",".join("?" * len(part))
            con.execute(f"DELETE FROM entries_fts WHERE rowid IN ({q})", part)
            con.execute(f"DELETE FROM embeddings WHERE entry_id IN ({q})", part)
            con.execute(f"DELETE FROM links WHERE from_id IN ({q}) OR to_id IN ({q})", part + part)
            con.execute(f"DELETE FROM record_tags WHERE entry_id IN ({q})", part)
            con.execute(f"DELETE FROM entries WHERE id IN ({q})", part)
        con.execute("DELETE FROM systems WHERE game_id=? AND slug LIKE ?", (gid, K4 + "%"))
        before = con.execute("SELECT COUNT(*) FROM entries WHERE game_id=?", (gid,)).fetchone()[0]

        seen = {norm_key(r["title"], r["body_md"] or "") for r in con.execute(
            "SELECT title, body_md FROM entries WHERE game_id=?", (gid,))}
        sysid, new, dup_spec, dup_self = {}, [], 0, 0
        spec_keys = set(seen)
        for r in rows:
            if r["game"] != game:
                continue
            k = norm_key(r["title"], r["body_md"] or "")
            if k in seen:
                if k in spec_keys:
                    dup_spec += 1
                else:
                    dup_self += 1
                continue
            seen.add(k)
            sk = (r.get("system_slug") or "none")
            if sk not in sysid:
                sysid[sk] = con.execute(
                    "INSERT INTO systems(game_id,slug,title,spec_file) VALUES(?,?,?,?)",
                    (gid, K4 + sk, r.get("system_title") or sk, r.get("spec_file") or "")).lastrowid
            coll = r.get("collection")
            if not coll:
                coll = I.assign_collection((r.get("system_id") or r.get("spec_file") or "")[:3].rstrip("-_."),
                                           r["kind"], r["title"], "")
            nums = r.get("numbers_json")
            if isinstance(nums, (dict, list)):
                nums = json.dumps(nums, ensure_ascii=False)
            tags = r.get("tags") or ""
            title, summary, body = r["title"], r.get("summary") or "", r.get("body_md") or ""
            eid = con.execute(
                "INSERT INTO entries(game_id,system_id,collection,kind,title,summary,body_md,numbers_json,tags,"
                "spec_file,anchor,source_ref,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (gid, sysid[sk], coll, r["kind"], title, summary, body, nums, tags,
                 r.get("spec_file"), r.get("anchor"), r.get("source_ref"), now)).lastrowid
            con.execute("INSERT INTO entries_fts(rowid,title,summary,body,tags) VALUES(?,?,?,?,?)",
                        (eid, C.stem_text(title), C.stem_text(summary), C.stem_text(body), C.stem_text(tags)))
            ctx = f"{r.get('system_title') or sk}"
            new.append((eid, f"{ctx}\n{title}\n{body}\nТеги: {tags}"[:EMBED_CHARS]))
        con.commit()
        print(f"[k4] {game}: в файле {sum(r['game']==game for r in rows)}, дубли со спекой {dup_spec}, "
              f"дубли внутри {dup_self}, загружено {len(new)}; записей игры {before} -> {before + len(new)}")

        todo = [(i, t) for i, t in new if C.text_hash(t) not in cache]
        print(f"[embed] из кэша {len(new) - len(todo)}, новых {len(todo)}"
              + ("" if not a.no_embed else " (пропущены: --no-embed)"))
        for eid, t in new:
            h = C.text_hash(t)
            if h in cache:
                con.execute("INSERT INTO embeddings(entry_id,model,dim,vec,text_hash) VALUES(?,?,?,?,?)",
                            (eid, a.model, len(cache[h]) // 4, cache[h], h))
        con.commit()
        if not a.no_embed and todo:
            for k in range(0, len(todo), 512):
                part = todo[k:k + 512]
                arr = C.embed([t for _, t in part], "passage", a.model)
                for (eid, t), v in zip(part, arr):
                    con.execute("INSERT INTO embeddings(entry_id,model,dim,vec,text_hash) VALUES(?,?,?,?,?)",
                                (eid, a.model, len(v), v.tobytes(), C.text_hash(t)))
                    cache[C.text_hash(t)] = v.tobytes()
                con.commit()
                print(f"[embed] {min(k + 512, len(todo))}/{len(todo)} ({time.time() - t0:.0f}s)", flush=True)
    import tag  # теги новых записей К4 (идемпотентно, вся игра)
    for game in sorted(slugs):
        tag.tag_game(con, game)
    con.execute("PRAGMA optimize")
    con.close()
    print(f"[k4] готово за {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
