"""CLI базы механик: search / show / stats / similar / bench.

    mech.py search "рывок с неуязвимостью" [--game wol] [--kind boss] [--system 06] [-k 10] [--json]
    mech.py search --all "поджог burn" [--collection relic_catalog] [--game wol] [--kind relic] [--json]
        # полный перечень (без top-k); "рывок dash & неуязвимость" — оба понятия
    mech.py show 123
    mech.py stats
    mech.py similar 123 [--other-games]
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

import common as C

RRF_K = 60
POOL = 60  # сколько кандидатов берём из каждого списка перед слиянием


def where_clause(a) -> tuple[str, list]:
    w, p = [], []
    if getattr(a, "game", None):
        w.append("g.slug=?"); p.append(a.game)
    if getattr(a, "collection", None):
        cs = a.collection.split(",")
        w.append(f"e.collection IN ({','.join('?' * len(cs))})"); p += cs
    if getattr(a, "kind", None):
        ks = a.kind.split(",")
        w.append(f"e.kind IN ({','.join('?' * len(ks))})"); p += ks
    if getattr(a, "system", None):
        # slug целиком, либо префикс номера ("06"), либо подстрока ("enemy")
        w.append("(s.slug=? OR s.slug LIKE ? OR s.slug LIKE ?)")
        p += [a.system, a.system + "-%", f"%{a.system}%"]
    return " AND ".join(w), p


def fetch_entries(con, ids):
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    rows = con.execute(
        f"SELECT e.*, g.slug AS game, s.slug AS system FROM entries e JOIN games g ON g.id=e.game_id "
        f"LEFT JOIN systems s ON s.id=e.system_id WHERE e.id IN ({q})", list(ids)).fetchall()
    return {r["id"]: r for r in rows}


def bm25_search(con, query, where, params, n=POOL):
    fq = C.fts_query(query)
    if not fq:
        return []
    sql = ("SELECT f.rowid AS id, bm25(entries_fts, 5.0, 2.0, 1.0, 3.0) AS sc FROM entries_fts f "
           "JOIN entries e ON e.id=f.rowid JOIN games g ON g.id=e.game_id "
           "LEFT JOIN systems s ON s.id=e.system_id "
           "WHERE entries_fts MATCH ? " + (f"AND {where} " if where else "") +
           "ORDER BY sc LIMIT ?")
    return [(r["id"], r["sc"]) for r in con.execute(sql, [fq, *params, n])]


def vec_search(con, query, where, params, model, n=POOL, timing=None):
    t = time.time()
    ids, mat = C.load_vectors(con, model, where, tuple(params))
    if timing is not None:
        timing["load_vectors"] = time.time() - t
    if not len(ids):
        return []
    t = time.time()
    q = C.embed([query], "query", model)[0]
    if timing is not None:
        timing["embed_query"] = time.time() - t
    sims = mat @ q
    top = np.argsort(-sims)[:n]
    return [(int(ids[i]), float(sims[i])) for i in top]


def rrf(lists: dict[str, list[tuple[int, float]]]):
    fused: dict[int, dict] = {}
    for name, lst in lists.items():
        for rank, (i, raw) in enumerate(lst, 1):
            d = fused.setdefault(i, {"score": 0.0})
            d["score"] += 1.0 / (RRF_K + rank)
            d[f"{name}_rank"] = rank
            d[f"{name}_raw"] = raw
    return sorted(fused.items(), key=lambda kv: -kv[1]["score"])


def do_search(con, a, query=None, timing=None):
    query = query or a.query
    where, params = where_clause(a)
    lists = {}
    t = time.time()
    if a.mode in ("hybrid", "bm25"):
        lists["bm25"] = bm25_search(con, query, where, params)
    if timing is not None:
        timing["bm25"] = time.time() - t
    if a.mode in ("hybrid", "vector"):
        lists["vec"] = vec_search(con, query, where, params, a.model, timing=timing)
    fused = rrf(lists)[: a.k]
    ents = fetch_entries(con, [i for i, _ in fused])
    out = []
    for i, d in fused:
        e = ents[i]
        out.append({
            "id": i, "score": round(d["score"], 5), "title": e["title"], "game": e["game"],
            "collection": e["collection"],
            "system": e["system"], "kind": e["kind"], "summary": e["summary"],
            "ref": f"{e['spec_file']}#{e['anchor']}" if e["anchor"] else e["spec_file"],
            "source_ref": e["source_ref"], "tags": e["tags"],
            "bm25_rank": d.get("bm25_rank"), "vec_rank": d.get("vec_rank"),
            "cosine": round(d["vec_raw"], 4) if "vec_raw" in d else None,
            "numbers": json.loads(e["numbers_json"]) if e["numbers_json"] else None,
        })
    return out


PREFIX_MIN = 4  # токены короче — только точное совпадение ("ice" не должен ловить "iceberg")


def all_query(query: str, prefix: bool = True) -> str:
    """Запрос перечня -> FTS5-выражение. Слова группы — синонимы (OR), группы через « & » — все понятия сразу (AND)."""
    groups = []
    for part in query.split("&"):
        toks = list(dict.fromkeys(t for t in C.stem_tokens(part, drop_stop=True) if t))
        if toks:
            groups.append("(" + " OR ".join(
                f'"{t}"*' if prefix and len(t) >= PREFIX_MIN else f'"{t}"' for t in toks) + ")")
    return " AND ".join(groups)


def do_all(con, a, query=None):
    """Полный перечень: ВСЕ записи, совпавшие по FTS со словами понятия; без top-k, порядок — bm25, затем id."""
    query = query or a.query
    fq = all_query(query, prefix=not getattr(a, "exact", False))
    if not fq:
        return []
    where, params = where_clause(a)
    rows = con.execute(
        "SELECT e.id, e.title, e.summary, e.kind, e.collection, e.spec_file, e.anchor, e.source_ref, "
        "g.slug AS game, s.slug AS system, bm25(entries_fts, 5.0, 2.0, 1.0, 3.0) AS sc "
        "FROM entries_fts f JOIN entries e ON e.id=f.rowid JOIN games g ON g.id=e.game_id "
        "LEFT JOIN systems s ON s.id=e.system_id WHERE entries_fts MATCH ? " +
        (f"AND {where} " if where else "") + "ORDER BY sc, e.id", [fq, *params]).fetchall()
    return [{"id": r["id"], "score": round(-r["sc"], 4), "title": r["title"], "game": r["game"],
             "collection": r["collection"], "system": r["system"], "kind": r["kind"], "summary": r["summary"],
             "ref": f"{r['spec_file']}#{r['anchor']}" if r["anchor"] else r["spec_file"],
             "source_ref": r["source_ref"]} for r in rows]


def print_table(hits):
    if not hits:
        return
    w = {c: max(len(c), *(len(str(h[c] or "")) for h in hits)) for c in ("id", "game", "collection", "kind")}
    print("  ".join(f"{c:<{w[c]}}" for c in w) + "  title")
    for h in hits:
        t = h["title"] if len(h["title"]) <= 70 else h["title"][:69] + "…"
        print("  ".join(f"{str(h[c] or ''):<{w[c]}}" for c in w) + f"  {t}")


def print_hits(hits, show_numbers=False):
    for n, h in enumerate(hits, 1):
        print(f"{n:>2}. [{h['score']:.4f}] {h['title']}  ({h['game']}/{h['system']} · {h.get('collection')}/{h['kind']})  id={h['id']}")
        if h["summary"]:
            s = h["summary"] if len(h["summary"]) <= 160 else h["summary"][:159] + "…"
            print(f"      {s}")
        extra = []
        if h.get("bm25_rank"):
            extra.append(f"bm25#{h['bm25_rank']}")
        if h.get("vec_rank"):
            extra.append(f"vec#{h['vec_rank']} cos={h['cosine']}")
        print(f"      {h['ref']}  ({h['source_ref']})  " + " ".join(extra))


def cmd_search(con, a):
    if a.all:
        if a.mode != "hybrid":
            raise SystemExit("--all — перечень по FTS, --mode не применяется")
        t0 = time.time()
        hits = do_all(con, a)
        total = time.time() - t0
        if a.json:
            print(json.dumps({"query": a.query, "fts": all_query(a.query, not a.exact), "count": len(hits),
                              "latency_s": round(total, 3), "hits": hits}, ensure_ascii=False, indent=2))
        else:
            print_table(hits)
            print(f"\n{len(hits)} записей · {total * 1000:.0f} ms")
        return
    timing = {}
    t0 = time.time()
    hits = do_search(con, a, timing=timing)
    total = time.time() - t0
    if a.json:
        print(json.dumps({"query": a.query, "latency_s": round(total, 3),
                          "timing": {k: round(v, 3) for k, v in timing.items()}, "hits": hits},
                         ensure_ascii=False, indent=2))
    else:
        print_hits(hits)
        tm = ", ".join(f"{k} {v * 1000:.0f}ms" for k, v in timing.items())
        print(f"\nlatency: {total * 1000:.0f} ms ({tm})")


def cmd_bench(con, a):
    """Много запросов в одном процессе: модель грузится один раз (холодный старт отдельно)."""
    t = time.time()
    if a.mode != "bm25":
        C.get_model(a.model)
        C.embed(["прогрев"], "query", a.model)
    print(f"model load+warmup: {time.time() - t:.2f}s\n")
    for q in a.queries:
        tm = {}
        t = time.time()
        hits = do_search(con, a, q, timing=tm)
        dt_ = time.time() - t
        print(f"=== «{q}»  — {dt_ * 1000:.0f} ms")
        print_hits(hits[: a.top])
        print()


def cmd_show(con, a):
    e = con.execute("SELECT e.*, g.slug AS game, s.slug AS system, s.title AS system_title "
                    "FROM entries e JOIN games g ON g.id=e.game_id "
                    "LEFT JOIN systems s ON s.id=e.system_id WHERE e.id=?", (a.id,)).fetchone()
    if not e:
        raise SystemExit(f"нет записи {a.id}")
    d = dict(e)
    d["numbers"] = json.loads(d.pop("numbers_json")) if d["numbers_json"] else None
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return
    print(f"# {d['title']}   [id={d['id']}]")
    print(f"{d['game']} / {d['system']} ({d['system_title']}) · collection={d['collection']} · {d['kind']}")
    print(f"{d['spec_file']}#{d['anchor']}  ({d['source_ref']})")
    print(f"tags: {d['tags']}\n")
    print(d["body_md"])
    if d["numbers"]:
        print("\nnumbers:", json.dumps(d["numbers"], ensure_ascii=False))


def cmd_stats(con, a):
    q = lambda s, *p: [dict(r) for r in con.execute(s, p)]
    st = {
        "games": q("SELECT g.slug, g.title, g.spec_path, COUNT(e.id) AS entries FROM games g "
                   "LEFT JOIN entries e ON e.game_id=g.id GROUP BY g.id"),
        "by_collection": q("SELECT c.slug AS collection, c.title, c.family, g.slug AS game, COUNT(e.id) AS n "
                           "FROM collections c JOIN entries e ON e.collection=c.slug JOIN games g ON g.id=e.game_id "
                           "GROUP BY c.slug, g.slug ORDER BY c.rowid"),
        "by_kind": q("SELECT g.slug AS game, e.kind, COUNT(*) AS n FROM entries e JOIN games g ON g.id=e.game_id "
                     "GROUP BY g.slug, e.kind ORDER BY g.slug, n DESC"),
        "by_system": q("SELECT g.slug AS game, s.slug AS system, s.title, COUNT(e.id) AS n FROM systems s "
                       "JOIN games g ON g.id=s.game_id LEFT JOIN entries e ON e.system_id=s.id "
                       "GROUP BY s.id ORDER BY g.slug, s.slug"),
        "embeddings": q("SELECT model, dim, COUNT(*) AS n FROM embeddings GROUP BY model, dim"),
        "db_bytes": C.DB_PATH.stat().st_size,
    }
    if a.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return
    for g in st["games"]:
        print(f"game {g['slug']}: {g['entries']} записей  ({g['title']}; {g['spec_path']})")
    print("\nпо видам:")
    for r in st["by_kind"]:
        print(f"  {r['game']:<6}{r['kind']:<14}{r['n']:>6}")
    print("\nпо системам:")
    for r in st["by_system"]:
        print(f"  {r['game']:<6}{r['system']:<24}{r['n']:>6}  {r['title']}")
    for r in st["embeddings"]:
        print(f"\nэмбеддинги: {r['model']} dim={r['dim']} n={r['n']}")
    print(f"db: {st['db_bytes'] / 1e6:.1f} MB")


def cmd_list(con, a):
    where, params = where_clause(a)
    rows = con.execute(
        "SELECT e.id, e.title, e.summary, e.kind, e.collection, e.numbers_json, e.spec_file, e.anchor, "
        "e.source_ref, g.slug AS game, s.slug AS system FROM entries e JOIN games g ON g.id=e.game_id "
        "LEFT JOIN systems s ON s.id=e.system_id " + (f"WHERE {where} " if where else "") +
        "ORDER BY g.slug, e.collection, e.id LIMIT ? OFFSET ?", [*params, a.k, a.offset]).fetchall()
    if a.json:
        print(json.dumps([{**dict(r), "numbers": json.loads(r["numbers_json"]) if r["numbers_json"] else None,
                           "numbers_json": None} for r in rows], ensure_ascii=False, indent=2))
        return
    for r in rows:
        print(f"[{r['id']}] {r['title']}  ({r['game']}/{r['system']} · {r['collection']}/{r['kind']})")
        if r["summary"]:
            print(f"      {r['summary'][:160]}")


def cmd_collections(con, a):
    rows = con.execute(
        "SELECT c.slug, c.title, c.family, c.family_title, c.automation, c.priority, c.wol_count, "
        "c.description, c.cross_game_key, c.record_schema_json, "
        "(SELECT COUNT(*) FROM entries e WHERE e.collection=c.slug) AS n FROM collections c ORDER BY c.rowid").fetchall()
    games = {r[0]: r[1] for r in con.execute("SELECT slug, id FROM games")}
    per_game = {}
    for r in con.execute("SELECT e.collection, g.slug, COUNT(*) FROM entries e JOIN games g ON g.id=e.game_id "
                         "GROUP BY e.collection, g.slug"):
        per_game.setdefault(r[0], {})[r[1]] = r[2]
    if a.json:
        print(json.dumps([{**dict(r), "record_schema": json.loads(r["record_schema_json"] or "null"),
                           "record_schema_json": None, "per_game": per_game.get(r["slug"], {})} for r in rows],
                         ensure_ascii=False, indent=2))
        return
    fam = None
    for r in rows:
        if r["family_title"] != fam:
            fam = r["family_title"]
            print(f"\n{fam}")
        pg = ", ".join(f"{g}={n}" for g, n in per_game.get(r["slug"], {}).items()) or "—"
        print(f"  {r['slug']:<28}{r['n']:>6}  [{pg}] {r['automation'] or ''}/{r['priority'] or ''}  {r['title']}")
    print(f"\nвсего коллекций: {len(rows)}; пустых: {sum(1 for r in rows if not r['n'])}; записей: {sum(r['n'] for r in rows)}")


def cmd_serve(con, a):
    """Горячий сервер эмбеддингов: модель грузится один раз, search/bench/similar берут вектор запроса отсюда."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import os
    os.environ["MECH_NO_SERVER"] = "1"
    t = time.time()
    C.get_model(a.model)
    C.embed(["прогрев"], "query", a.model)
    print(f"модель готова за {time.time() - t:.1f}s; слушаю 127.0.0.1:{C.SERVE_PORT}  (Ctrl+C — выход)", flush=True)

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            v = C.embed(body["texts"], body["kind"], body.get("model") or a.model)
            out = json.dumps({"vecs": v.tolist()}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
            self.wfile.write(out)

        def log_message(self, *x):
            pass
    ThreadingHTTPServer(("127.0.0.1", C.SERVE_PORT), H).serve_forever()


def cmd_similar(con, a):
    src = con.execute("SELECT game_id FROM entries WHERE id=?", (a.id,)).fetchone()
    if not src:
        raise SystemExit(f"нет записи {a.id}")
    w, pr = where_clause(a)
    ids, mat = C.load_vectors(con, a.model, w, tuple(pr))
    pos = np.where(ids == a.id)[0]
    if not len(pos):
        raise SystemExit("у записи нет эмбеддинга для этой модели")
    sims = mat @ mat[pos[0]]
    order = np.argsort(-sims)
    cand = [int(ids[i]) for i in order if int(ids[i]) != a.id][: 400]
    ents = fetch_entries(con, cand)
    hits = []
    for i in order:
        eid = int(ids[i])
        if eid == a.id:
            continue
        e = ents.get(eid) or fetch_entries(con, [eid])[eid]
        if a.other_games and e["game_id"] == src["game_id"]:
            continue
        hits.append({"id": eid, "score": round(float(sims[i]), 4), "title": e["title"],
                     "game": e["game"], "system": e["system"], "kind": e["kind"],
                     "collection": e["collection"], "summary": e["summary"], "ref": f"{e['spec_file']}#{e['anchor']}",
                     "source_ref": e["source_ref"], "cosine": round(float(sims[i]), 4)})
        if len(hits) >= a.k:
            break
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    else:
        print_hits(hits)


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(prog="mech.py", description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, search=True):
        p.add_argument("--game"); p.add_argument("--collection", help="одна или несколько через запятую"); p.add_argument("--kind", help="один или несколько через запятую")
        p.add_argument("--system", help="slug, префикс номера (06) или подстрока (enemy)")
        p.add_argument("-k", type=int, default=10)
        p.add_argument("--json", action="store_true")
        p.add_argument("--model", default=C.MODEL_NAME)

    s = sub.add_parser("search"); s.add_argument("query"); common(s)
    s.add_argument("--mode", choices=["hybrid", "bm25", "vector"], default="hybrid")
    s.add_argument("--all", action="store_true",
                   help="полный перечень по словам понятия, без top-k (слова — синонимы/OR, группы через & — AND; -k игнорируется)")
    s.add_argument("--exact", action="store_true", help="с --all: без префиксного совпадения основ")
    b = sub.add_parser("bench", help="несколько запросов в одном процессе, тёплые задержки")
    b.add_argument("queries", nargs="+"); common(b); b.add_argument("--top", type=int, default=3)
    b.add_argument("--mode", choices=["hybrid", "bm25", "vector"], default="hybrid")
    li = sub.add_parser("list", help="перечень записей коллекции"); common(li); li.set_defaults(k=50)
    li.add_argument("--offset", type=int, default=0)
    sv = sub.add_parser("serve", help="держать модель в памяти (быстрые запросы)"); sv.add_argument("--model", default=C.MODEL_NAME)
    co = sub.add_parser("collections", help="коллекции таксономии со счётчиками"); co.add_argument("--json", action="store_true")
    sh = sub.add_parser("show"); sh.add_argument("id", type=int); sh.add_argument("--json", action="store_true")
    st = sub.add_parser("stats"); st.add_argument("--json", action="store_true")
    si = sub.add_parser("similar"); si.add_argument("id", type=int); common(si)
    si.add_argument("--other-games", action="store_true")
    a = ap.parse_args()

    con = C.connect()
    {"search": cmd_search, "bench": cmd_bench, "show": cmd_show,
     "stats": cmd_stats, "serve": cmd_serve, "collections": cmd_collections, "list": cmd_list, "similar": cmd_similar}[a.cmd](con, a)


if __name__ == "__main__":
    main()
