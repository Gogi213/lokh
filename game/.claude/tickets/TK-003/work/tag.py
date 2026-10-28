"""Разметчик записей смысловыми тегами (понятия taxonomy/tags.yaml) — общий словарь на все игры.

    python tag.py [--game wol] [--db путь] [--tags путь] [--semantic]    # разметить (идемпотентно)
    python tag.py --explain 650                                          # почему записи поставлены теги
    python tag.py --sample 50 [--seed 1] [--game wol]                    # выборка записей с тегами для проверки глазами
    python tag.py --report [--game wol]                                  # охват и частоты

Как ставятся теги (по порядку):
 1. text — скрипт: синонимы понятий (RU/EN, основы слов, «слово*» = префикс, фраза = слова подряд) ищутся в
    title / summary / body_md / ключах и строках numbers_json. Очки: заголовок 3; summary 2; тело — число
    вхождений (не больше 3); numbers_json 1. Тег ставится при сумме >= SCORE_MIN.
 2. coll — понятие-коллекция (поле collections в tags.yaml): каждая запись коллекции получает его неявно.
 3. model (только с --semantic) — для записей БЕЗ text-тега: ближайшее понятие по e5-вектору записи (уже лежит в
    embeddings) и вектору определения понятия; берётся top-1 при cos >= SEM_MIN и отрыве от второго >= SEM_GAP.
Родитель тегов не дублируется в record_tags: поиск по тегу включает потомков (descendants()).
Вызывается из ingest.py / ingest_entries.py после загрузки игры; повторный запуск заменяет теги игры целиком.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import time
from collections import defaultdict
from pathlib import Path

import common as C

TAGS_PATH = Path(os.environ.get("MECH_TAGS", C.ROOT / "taxonomy" / "tags.yaml"))
SCORE_MIN = 3        # порог очков text-тега
W_TITLE, W_SUMMARY, W_BODY_MAX, W_NUMBERS = 3, 2, 3, 1
PREFIX_MIN = 3       # префиксный синоним «ab*» короче — ошибка словаря
SEM_MIN, SEM_GAP = 0.80, 0.015  # порог model-тега по косинусу и отрыв от второго кандидата

SCHEMA = """
CREATE TABLE IF NOT EXISTS tags(
  id TEXT PRIMARY KEY, name_ru TEXT, name_en TEXT, definition TEXT, parent TEXT, level TEXT);
CREATE TABLE IF NOT EXISTS tag_syn(tag_id TEXT NOT NULL, syn TEXT NOT NULL, lang TEXT, PRIMARY KEY(tag_id, syn));
CREATE TABLE IF NOT EXISTS record_tags(
  entry_id INTEGER NOT NULL, tag_id TEXT NOT NULL, score REAL, source TEXT, PRIMARY KEY(entry_id, tag_id));
CREATE INDEX IF NOT EXISTS ix_record_tags_tag ON record_tags(tag_id, entry_id);
"""

_TOK = re.compile(r"[^\W_]+", re.UNICODE)
_CAMEL = re.compile(r"(?<=[a-zа-яё])(?=[A-ZА-ЯЁ])")


def ensure_schema(con) -> None:
    con.executescript(SCHEMA)


def norm_token(t: str, _cache: dict = {}) -> str:
    r = _cache.get(t)
    if r is None:
        if t.isascii():
            r = t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t
        else:
            r = C.stemmer().stemWord(t)
        _cache[t] = r
    return r


def tokens(text: str) -> list[str]:
    return _TOK.findall(_CAMEL.sub(" ", text or "").lower().replace("ё", "е"))


def load_concepts(path: Path = TAGS_PATH) -> list[dict]:
    import yaml
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    cs = d["concepts"]
    ids = {c["id"] for c in cs}
    if len(ids) != len(cs):
        raise SystemExit("tags.yaml: повторяющиеся id")
    allowed = {"id", "ru", "en", "def", "syn_ru", "syn_en", "parent", "collections", "weak"}
    for c in cs:
        if set(c) - allowed or any(v is None for v in c.values()):
            raise SystemExit(f"tags.yaml: {c.get('id')}: лишние/пустые поля {set(c) - allowed} (запятая в имени? возьмите в кавычки)")
        if c.get("parent") and c["parent"] not in ids:
            raise SystemExit(f"tags.yaml: {c['id']}: нет родителя {c['parent']}")
    return cs


class Matcher:
    """Индекс синонимов: первое слово фразы -> кандидаты; точное (основа) и префиксное."""

    def __init__(self, concepts: list[dict]):
        self.weak: set[str] = set()
        self.exact = defaultdict(list)
        self.prefix = defaultdict(list)
        self.plen = set()
        self.coll = defaultdict(list)
        for c in concepts:
            for k in c.get("collections") or []:
                self.coll[k].append(c["id"])
            if c.get("weak"):
                self.weak.add(c["id"])
            names = [c["ru"], c["en"]] if c.get("parent") else []  # имя семейства — не синоним
            for syn in list(c.get("syn_ru") or []) + list(c.get("syn_en") or []) + names:
                words = re.findall(r"[^\W_]+\*?", str(syn).lower().replace("ё", "е"))
                if not words:
                    continue
                phrase = []
                for w in words:
                    if w.endswith("*"):
                        if len(w) - 1 < PREFIX_MIN:
                            raise SystemExit(f"tags.yaml: {c['id']}: префикс «{w}» короче {PREFIX_MIN}")
                        phrase.append(("p", w[:-1]))
                    else:
                        phrase.append(("e", norm_token(w)))
                item = (c["id"], tuple(phrase), str(syn))
                kind, val = phrase[0]
                if kind == "e":
                    self.exact[val].append(item)
                else:
                    self.prefix[val].append(item)
                    self.plen.add(len(val))

    def find(self, text: str) -> dict[str, int]:
        """Вернёт {tag_id: число вхождений любых его синонимов}."""
        toks = tokens(text)
        norm = [norm_token(t) for t in toks]
        out: dict[str, int] = defaultdict(int)
        for i, t in enumerate(toks):
            cands = list(self.exact.get(norm[i], ()))
            for L in self.plen:
                if len(t) >= L:
                    cands += self.prefix.get(t[:L], ())
            for cid, phrase, _ in cands:
                if i + len(phrase) > len(toks):
                    continue
                ok = True
                for j, (kind, val) in enumerate(phrase):
                    if (norm[i + j] != val) if kind == "e" else (not toks[i + j].startswith(val)):
                        ok = False
                        break
                if ok:
                    out[cid] += 1
        return out


def flatten_numbers(nj) -> str:
    if not nj:
        return ""
    try:
        v = json.loads(nj)
    except Exception:
        return str(nj)
    out: list[str] = []

    def walk(x, depth=0):
        if isinstance(x, dict):
            for k, y in x.items():
                out.append(str(k))
                walk(y, depth + 1)
        elif isinstance(x, list):
            for y in x[:40]:
                walk(y, depth + 1)
        elif isinstance(x, str):
            out.append(x)

    walk(v)
    return " . ".join(out)


def score_entry(m: Matcher, title, summary, body, numbers_json):
    """-> {tag_id: (score, {поле: n})} только для тегов, прошедших порог."""
    ft, fs, fb = m.find(title), m.find(summary), m.find(body)
    fn = m.find(flatten_numbers(numbers_json))
    res = {}
    for cid in set(ft) | set(fs) | set(fb) | set(fn):
        sc = (W_TITLE if cid in ft else 0) + (W_SUMMARY if cid in fs else 0) + min(fb.get(cid, 0), W_BODY_MAX) \
            + (W_NUMBERS if cid in fn else 0)
        if sc >= SCORE_MIN and (cid not in m.weak or cid in ft or cid in fs):  # «слабые» (общие) понятия — только по заголовку/summary
            res[cid] = (float(sc), {"title": ft.get(cid, 0), "summary": fs.get(cid, 0), "body": fb.get(cid, 0),
                                    "numbers": fn.get(cid, 0)})
    return res


def sync_tags(con, concepts: list[dict]) -> None:
    ensure_schema(con)
    con.execute("DELETE FROM tags")
    con.execute("DELETE FROM tag_syn")
    for c in concepts:
        level = "collection" if c.get("collections") else ("family" if not c.get("parent") else "concept")
        con.execute("INSERT INTO tags(id,name_ru,name_en,definition,parent,level) VALUES(?,?,?,?,?,?)",
                    (c["id"], c["ru"], c["en"], c.get("def"), c.get("parent"), level))
        for lang, key in (("ru", "syn_ru"), ("en", "syn_en")):
            for s in c.get(key) or []:
                con.execute("INSERT OR IGNORE INTO tag_syn(tag_id,syn,lang) VALUES(?,?,?)", (c["id"], str(s), lang))


def tag_game(con, game_slug: str | None = None, semantic: bool = False, concepts=None, verbose=True) -> dict:
    """Разметить игру (или все игры). Идемпотентно: теги игры заменяются целиком."""
    t0 = time.time()
    concepts = concepts or load_concepts()
    sync_tags(con, concepts)
    m = Matcher(concepts)
    q = ("SELECT e.id, e.collection, e.title, e.summary, e.body_md, e.numbers_json, e.game_id FROM entries e "
         "JOIN games g ON g.id=e.game_id " + ("WHERE g.slug=?" if game_slug else ""))
    rows = con.execute(q, ((game_slug,) if game_slug else ())).fetchall()
    ids = [r["id"] for r in rows]
    for k in range(0, len(ids), 500):
        part = ids[k:k + 500]
        con.execute(f"DELETE FROM record_tags WHERE entry_id IN ({','.join('?' * len(part))})", part)
    out, with_text = [], set()
    for r in rows:
        for cid, (sc, _) in score_entry(m, r["title"], r["summary"], r["body_md"], r["numbers_json"]).items():
            out.append((r["id"], cid, sc, "text"))
            with_text.add(r["id"])
        for cid in m.coll.get(r["collection"], ()):
            out.append((r["id"], cid, 1.0, "coll"))
    out_text = sum(1 for o in out if o[3] == "text")
    n_model = 0
    if semantic:
        sem = semantic_tags([r["id"] for r in rows if r["id"] not in with_text], concepts, con)
        out += sem
        n_model = len(sem)
    con.executemany("INSERT OR IGNORE INTO record_tags(entry_id,tag_id,score,source) VALUES(?,?,?,?)", out)
    con.commit()
    stat = {"entries": len(rows), "with_text_tag": len(with_text), "text_tags": out_text,
            "coll_tags": sum(1 for o in out if o[3] == "coll"), "model_tags": n_model,
            "seconds": round(time.time() - t0, 1)}
    if verbose:
        print(f"[tag] {game_slug or 'все игры'}: записей {stat['entries']}, с text-тегом {stat['with_text_tag']} "
              f"({100 * stat['with_text_tag'] / max(1, stat['entries']):.1f}%), text {out_text}, "
              f"coll {stat['coll_tags']}, model {n_model}, {stat['seconds']} c")
    return stat


def semantic_tags(entry_ids, concepts, con, model=C.MODEL_NAME):
    """Дешёвая модель только для записей без text-тега: косинус вектора записи и вектора определения понятия."""
    import numpy as np
    leaf = [c for c in concepts if not c.get("collections") and c.get("parent")]
    texts = [f"{c['ru']} ({c['en']}). {c.get('def') or ''} " + ", ".join((c.get("syn_ru") or [])[:6]) for c in leaf]
    cv = C.embed(texts, "passage", model)
    res = []
    want = set(entry_ids)
    for k in range(0, len(entry_ids), 2000):
        part = entry_ids[k:k + 2000]
        rows = con.execute(f"SELECT entry_id, vec FROM embeddings WHERE model=? AND entry_id IN "
                           f"({','.join('?' * len(part))})", [model, *part]).fetchall()
        if not rows:
            continue
        ev = np.vstack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        sims = ev @ cv.T
        top = np.argsort(-sims, axis=1)[:, :2]
        for i, r in enumerate(rows):
            a, b = top[i]
            if sims[i, a] >= SEM_MIN and sims[i, a] - sims[i, b] >= SEM_GAP and r["entry_id"] in want:
                res.append((r["entry_id"], leaf[a]["id"], round(float(sims[i, a]), 4), "model"))
    return res


# ---------- запросы к тегам (для mech.py) ----------
def descendants(con, tag_ids) -> set[str]:
    kids = defaultdict(list)
    for r in con.execute("SELECT id, parent FROM tags WHERE parent IS NOT NULL"):
        kids[r["parent"]].append(r["id"])
    out, stack = set(), list(tag_ids)
    while stack:
        t = stack.pop()
        if t not in out:
            out.add(t)
            stack += kids.get(t, [])
    return out


def resolve(con, term: str) -> list[str]:
    """Слово/фраза/id -> id понятий (через id, имя RU/EN или синонимы словаря)."""
    term = term.strip()
    low = term.lower().replace("ё", "е")
    ids = {r["id"] for r in con.execute("SELECT id FROM tags WHERE id=? OR lower(name_ru)=? OR lower(name_en)=?",
                                        (term, term.lower(), term.lower()))}
    if ids:
        return sorted(ids)
    concepts = [dict(id=r["id"], ru=r["name_ru"], en=r["name_en"],
                     syn_ru=[s["syn"] for s in con.execute("SELECT syn FROM tag_syn WHERE tag_id=? AND lang='ru'",
                                                           (r["id"],))],
                     syn_en=[s["syn"] for s in con.execute("SELECT syn FROM tag_syn WHERE tag_id=? AND lang='en'",
                                                           (r["id"],))])
                for r in con.execute("SELECT id,name_ru,name_en FROM tags WHERE level='concept'")]
    hits = Matcher(concepts).find(low)
    return sorted(hits, key=lambda k: -hits[k])


def entry_tags(con, entry_id: int) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT t.tag_id, g.name_ru, g.level, t.score, t.source FROM record_tags t JOIN tags g ON g.id=t.tag_id "
        "WHERE t.entry_id=? ORDER BY CASE t.source WHEN 'text' THEN 0 WHEN 'model' THEN 1 ELSE 2 END, t.score DESC",
        (entry_id,))]


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--game")
    ap.add_argument("--db")
    ap.add_argument("--tags")
    ap.add_argument("--semantic", action="store_true", help="model-теги для записей без text-тега")
    ap.add_argument("--explain", type=int)
    ap.add_argument("--sample", type=int)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.db:
        C.DB_PATH = Path(a.db)
    global TAGS_PATH
    if a.tags:
        TAGS_PATH = Path(a.tags)
    con = C.connect()
    ensure_schema(con)
    if a.explain:
        e = con.execute("SELECT * FROM entries WHERE id=?", (a.explain,)).fetchone()
        m = Matcher(load_concepts())
        print(f"[{e['id']}] {e['title']}")
        for cid, (sc, parts) in sorted(score_entry(m, e["title"], e["summary"], e["body_md"], e["numbers_json"]).items(),
                                       key=lambda kv: -kv[1][0]):
            print(f"  {cid:<22} {sc:>4.0f}  {parts}")
        print("  в базе:", [(t["tag_id"], t["source"]) for t in entry_tags(con, e["id"])])
        return
    if a.sample:
        rnd = random.Random(a.seed)
        w = "WHERE g.slug=?" if a.game else ""
        ids = [r[0] for r in con.execute(
            f"SELECT DISTINCT e.id FROM entries e JOIN games g ON g.id=e.game_id JOIN record_tags t ON t.entry_id=e.id "
            f"AND t.source!='coll' {w} ORDER BY e.id", (a.game,) if a.game else ())]
        for eid in sorted(rnd.sample(ids, min(a.sample, len(ids)))):
            e = con.execute("SELECT id,title,collection,substr(body_md,1,200) b FROM entries WHERE id=?", (eid,)).fetchone()
            tg = ", ".join(f"{t['tag_id']}({t['source']})" for t in entry_tags(con, eid) if t["source"] != "coll")
            print(f"[{e['id']}] {e['collection']} | {e['title']}\n    {(e['b'] or '').replace(chr(10), ' ')[:160]}\n    => {tg}")
        return
    if a.report:
        w = "AND g.slug=?" if a.game else ""
        p = (a.game,) if a.game else ()
        n = con.execute(f"SELECT COUNT(*) FROM entries e JOIN games g ON g.id=e.game_id WHERE 1 {w}", p).fetchone()[0]
        nt = con.execute(f"SELECT COUNT(DISTINCT t.entry_id) FROM record_tags t JOIN entries e ON e.id=t.entry_id "
                         f"JOIN games g ON g.id=e.game_id WHERE t.source IN ('text','model') {w}", p).fetchone()[0]
        print(f"записей {n}, с содержательным тегом (text/model) {nt} ({100 * nt / max(1, n):.1f}%)")
        for r in con.execute(f"SELECT e.collection c, COUNT(*) n, SUM(EXISTS(SELECT 1 FROM record_tags t WHERE "
                             f"t.entry_id=e.id AND t.source IN ('text','model'))) k FROM entries e JOIN games g "
                             f"ON g.id=e.game_id WHERE 1 {w} GROUP BY e.collection ORDER BY n DESC", p):
            print(f"  {r['c']:<28} {r['n']:>6}  с тегом {r['k']:>6}  ({100 * r['k'] / r['n']:.0f}%)")
        return
    tag_game(con, a.game, a.semantic)


if __name__ == "__main__":
    main()
