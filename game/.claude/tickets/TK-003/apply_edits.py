"""Правки common.py / ingest.py / ingest_entries.py / mech.py в work/ (база для патча — base/)."""
import os

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "work"))


def sub(s, old, new):
    assert old in s, old[:70]
    return s.replace(old, new, 1)


def edit(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        s = sub(s, old, new)
    open(path, "w", encoding="utf-8").write(s)


edit("common.py", [(
    '''    if TAXONOMY_PATH.exists() and not con.execute("SELECT 1 FROM collections LIMIT 1").fetchone():''',
    '''    import tag as _tag  # таблицы тегов (tags, tag_syn, record_tags) — см. tag.py
    _tag.ensure_schema(con)
    if TAXONOMY_PATH.exists() and not con.execute("SELECT 1 FROM collections LIMIT 1").fetchone():''')])

edit("ingest.py", [(
    '''            con.execute(f"DELETE FROM links WHERE from_id IN ({qq}) OR to_id IN ({qq})", part + part)
    con.execute("DELETE FROM entries WHERE game_id=?", (gid,))''',
    '''            con.execute(f"DELETE FROM links WHERE from_id IN ({qq}) OR to_id IN ({qq})", part + part)
            con.execute(f"DELETE FROM record_tags WHERE entry_id IN ({qq})", part)
    con.execute("DELETE FROM entries WHERE game_id=?", (gid,))'''), (
    '''    con.execute("PRAGMA optimize")
    con.execute("VACUUM")''',
    '''    import tag  # смысловые теги (taxonomy/tags.yaml); для каждой новой игры — автоматически
    tag.tag_game(con, game)
    con.execute("PRAGMA optimize")
    con.execute("VACUUM")''')])

edit("ingest_entries.py", [(
    '''            con.execute(f"DELETE FROM links WHERE from_id IN ({q}) OR to_id IN ({q})", part + part)''',
    '''            con.execute(f"DELETE FROM links WHERE from_id IN ({q}) OR to_id IN ({q})", part + part)
            con.execute(f"DELETE FROM record_tags WHERE entry_id IN ({q})", part)'''), (
    '''    con.execute("PRAGMA optimize")
    con.close()
    print(f"[k4] готово''',
    '''    import tag  # теги новых записей К4 (идемпотентно, вся игра)
    for game in sorted(slugs):
        tag.tag_game(con, game)
    con.execute("PRAGMA optimize")
    con.close()
    print(f"[k4] готово''')])

MECH = []
MECH.append(('''    mech.py show 123''', '''    mech.py search --tag поджог [--game wol] [--collection ...] [--json]   # все записи с понятием (и потомками)
    mech.py search "урон" --tag огонь --tag рывок      # --tag повторять = И; "огонь,лёд" = ИЛИ; то же у list
    mech.py tags [поджог] [--level concept] [--game wol] [-k 40]             # частоты тегов / карточка понятия
    mech.py show 123'''))
MECH.append(('''    mech.py similar 123 [--other-games]''', '''    mech.py similar 123 [--other-games] [--no-tags]   # косинус + общие теги (RRF)'''))
MECH.append(('''    return " AND ".join(w), p


def fetch_entries''', '''    for ids in getattr(a, "tag_ids", None) or []:  # --tag: разобран в main() -> id понятий вместе с потомками
        w.append(f"EXISTS (SELECT 1 FROM record_tags rt WHERE rt.entry_id=e.id AND rt.tag_id IN "
                 f"({','.join('?' * len(ids))}))")
        p += ids
    return " AND ".join(w), p


def resolve_tags(con, a):
    """--tag "поджог" / "ignite" / id / "огонь,лёд" (ИЛИ) -> a.tag_ids: по списку id (с потомками) на каждый --tag."""
    import tag as T
    a.tag_ids = []
    if not con.execute("SELECT 1 FROM tags LIMIT 1").fetchone():
        raise SystemExit("теги не размечены: python tag.py")
    for spec in getattr(a, "tag", None) or []:
        ids = set()
        for term in spec.split(","):
            r = T.resolve(con, term)
            if not r:
                raise SystemExit(f"нет понятия «{term.strip()}» в словаре тегов (mech.py tags — список)")
            ids |= set(r)
        a.tag_ids.append(sorted(T.descendants(con, ids)))


def fetch_entries'''))
MECH.append(('''def cmd_search(con, a):
    if a.all:''', '''def do_tag_list(con, a):
    """search --tag без запроса: ВСЕ записи с понятием; порядок — сила тега (text/model раньше coll), затем id."""
    where, params = where_clause(a)
    flat = sorted({i for ids in a.tag_ids for i in ids})
    sc = (f"(SELECT MAX(rt.score + CASE rt.source WHEN 'coll' THEN 0 ELSE 100 END) FROM record_tags rt "
          f"WHERE rt.entry_id=e.id AND rt.tag_id IN ({','.join('?' * len(flat))}))")
    rows = con.execute(
        f"SELECT e.id, e.title, e.summary, e.kind, e.collection, e.spec_file, e.anchor, e.source_ref, g.slug AS game, "
        f"s.slug AS system, {sc} AS sc FROM entries e JOIN games g ON g.id=e.game_id LEFT JOIN systems s ON "
        f"s.id=e.system_id WHERE {where} ORDER BY sc DESC, e.id", [*flat, *params]).fetchall()
    return [{"id": r["id"], "score": r["sc"], "title": r["title"], "game": r["game"], "collection": r["collection"],
             "system": r["system"], "kind": r["kind"], "summary": r["summary"],
             "ref": f"{r['spec_file']}#{r['anchor']}" if r["anchor"] else r["spec_file"],
             "source_ref": r["source_ref"]} for r in rows]


def cmd_search(con, a):
    if a.query is None:
        if not getattr(a, "tag_ids", None):
            raise SystemExit("нужен запрос или --tag")
        t0 = time.time()
        hits = do_tag_list(con, a)
        total = time.time() - t0
        if a.json:
            print(json.dumps({"tag": a.tag, "count": len(hits), "latency_s": round(total, 3), "hits": hits},
                             ensure_ascii=False, indent=2))
        else:
            print_table(hits)
            print(f"\\n{len(hits)} записей · {total * 1000:.0f} ms")
        return
    if a.all:'''))
MECH.append(('''def cmd_collections(con, a):''', '''def cmd_tags(con, a):
    """Частоты тегов (фильтры --game/--collection/--source/--level) или карточка понятия: tags поджог."""
    import tag as T
    where, params = where_clause(a)
    if a.term:
        ids = T.resolve(con, a.term)
        if not ids:
            raise SystemExit(f"нет понятия «{a.term}»")
        for tid in ids:
            t = con.execute("SELECT * FROM tags WHERE id=?", (tid,)).fetchone()
            syn = [r["syn"] for r in con.execute("SELECT syn FROM tag_syn WHERE tag_id=? ORDER BY lang, syn", (tid,))]
            kids = [r["id"] for r in con.execute("SELECT id FROM tags WHERE parent=?", (tid,))]
            dsc = sorted(T.descendants(con, [tid]))
            n = con.execute("SELECT COUNT(DISTINCT rt.entry_id) FROM record_tags rt JOIN entries e ON e.id=rt.entry_id "
                            "JOIN games g ON g.id=e.game_id LEFT JOIN systems s ON s.id=e.system_id "
                            f"WHERE rt.tag_id IN ({','.join('?' * len(dsc))}) " + (f"AND {where}" if where else ""),
                            [*dsc, *params]).fetchone()[0]
            print(f"{t['id']} · {t['name_ru']} / {t['name_en']} · {t['level']} · родитель {t['parent']}\\n"
                  f"  {t['definition']}\\n  синонимы: {', '.join(syn)}\\n  потомки: {', '.join(kids) or '—'}\\n"
                  f"  записей (с потомками): {n}")
        return
    q = ("SELECT t.id, t.name_ru, t.name_en, t.level, t.parent, COUNT(DISTINCT rt.entry_id) AS n FROM tags t "
         "LEFT JOIN (record_tags rt JOIN entries e ON e.id=rt.entry_id JOIN games g ON g.id=e.game_id "
         "LEFT JOIN systems s ON s.id=e.system_id) ON rt.tag_id=t.id " + ("AND rt.source=? " if a.source else "") +
         (f"AND {where} " if where else "") + ("WHERE t.level=? " if a.level else "") +
         "GROUP BY t.id ORDER BY n DESC, t.id LIMIT ?")
    args = ([a.source] if a.source else []) + params + ([a.level] if a.level else []) + [a.k]
    rows = con.execute(q, args).fetchall()
    if a.json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
        return
    for r in rows:
        print(f"{r['n']:>6}  {r['id']:<22} {r['name_ru']} / {r['name_en']}  [{r['level']}]")


def cmd_collections(con, a):'''))
MECH.append(('''    sims = mat @ mat[pos[0]]
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
            break''', '''    sims = mat @ mat[pos[0]]
    order = np.argsort(-sims)
    cos = {int(ids[i]): float(sims[i]) for i in order if int(ids[i]) != a.id}
    game_of = dict(con.execute("SELECT id, game_id FROM entries WHERE id IN (%s)" % ",".join(map(str, cos))).fetchall()) \\
        if a.other_games else {}
    vec_list = [(eid, c) for eid, c in cos.items() if not a.other_games or game_of[eid] != src["game_id"]][:400]
    tag_list, shared = ([], {}) if a.no_tags else tag_neighbors(con, a, src["game_id"], set(cos))
    if tag_list:  # общие понятия: слияние RRF со списком по косинусу
        ranked = rrf({"vec": vec_list, "tags": tag_list})
    else:
        ranked = [(eid, {"score": c}) for eid, c in vec_list]
    ents = fetch_entries(con, [eid for eid, _ in ranked[: a.k * 3]])
    hits = []
    for eid, d in ranked:
        e = ents.get(eid) or fetch_entries(con, [eid])[eid]
        h = {"id": eid, "score": round(d["score"], 4), "title": e["title"],
             "game": e["game"], "system": e["system"], "kind": e["kind"],
             "collection": e["collection"], "summary": e["summary"], "ref": f"{e['spec_file']}#{e['anchor']}",
             "source_ref": e["source_ref"], "cosine": round(cos.get(eid, 0.0), 4)}
        if shared.get(eid):
            h["shared_tags"] = shared[eid]
        hits.append(h)
        if len(hits) >= a.k:
            break'''))
MECH.append(('''def cmd_similar(con, a):''', '''def tag_neighbors(con, a, game_id, allowed):
    """Записи с общими понятиями: вес понятия = ln(N/df) (редкое весит больше), coll-теги в 0.3.
    -> ([(id, вес)], {id: [теги]})."""
    import math
    mine = {r["tag_id"]: r["source"] for r in con.execute("SELECT tag_id, source FROM record_tags WHERE entry_id=?", (a.id,))}
    if not mine:
        return [], {}
    n = con.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    q = ",".join("?" * len(mine))
    df = {r[0]: r[1] for r in con.execute(
        f"SELECT tag_id, COUNT(*) FROM record_tags WHERE tag_id IN ({q}) GROUP BY tag_id", list(mine))}
    wt = {t: math.log(n / df[t]) * (0.3 if mine[t] == "coll" else 1.0) for t in mine if t in df}
    sc, shared = {}, {}
    for r in con.execute(f"SELECT entry_id, tag_id FROM record_tags WHERE tag_id IN ({q})", list(mine)):
        eid = r["entry_id"]
        if eid == a.id or eid not in allowed:
            continue
        sc[eid] = sc.get(eid, 0.0) + wt[r["tag_id"]]
        shared.setdefault(eid, []).append(r["tag_id"])
    if a.other_games and sc:
        keep = {r[0] for r in con.execute(
            f"SELECT id FROM entries WHERE game_id!=? AND id IN ({','.join(map(str, sc))})", [game_id])}
        sc = {k: v for k, v in sc.items() if k in keep}
    return sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))[:400], shared


def cmd_similar(con, a):'''))
MECH.append(('''        p.add_argument("--json", action="store_true")
        p.add_argument("--model", default=C.MODEL_NAME)''', '''        p.add_argument("--json", action="store_true")
        p.add_argument("--model", default=C.MODEL_NAME)
        p.add_argument("--tag", action="append",
                       help="понятие (RU/EN/синоним/id); повторять = И, через запятую = ИЛИ; потомки входят")'''))
MECH.append(('''    s = sub.add_parser("search"); s.add_argument("query"); common(s)''',
             '''    s = sub.add_parser("search"); s.add_argument("query", nargs="?"); common(s)'''))
MECH.append(('''    si.add_argument("--other-games", action="store_true")''', '''    si.add_argument("--other-games", action="store_true")
    si.add_argument("--no-tags", action="store_true", help="не учитывать общие теги (только косинус)")
    tg = sub.add_parser("tags", help="частоты тегов / карточка понятия"); common(tg); tg.set_defaults(k=40)
    tg.add_argument("term", nargs="?"); tg.add_argument("--level", choices=["concept", "collection", "family"])
    tg.add_argument("--source", choices=["text", "coll", "model"])'''))
MECH.append(('''    con = C.connect()
    {"search"''', '''    con = C.connect()
    if getattr(a, "tag", None):
        resolve_tags(con, a)
    {"search"'''))
MECH.append(('''"list": cmd_list, "similar": cmd_similar}''', '''"list": cmd_list, "similar": cmd_similar,
     "tags": cmd_tags}'''))
edit("mech.py", MECH)
print("ok")
