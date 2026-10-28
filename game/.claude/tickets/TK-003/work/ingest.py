"""Загрузка папки спеков игры в mechanics.db (идемпотентно: строки игры заменяются).

    python ingest.py --game wol --spec "C:/.../docs/spec" [--title ...] [--engine ...] [--no-embed]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path

import numpy as np

import common as C

MAX_CHARS = 1100        # длина куска тела секции (≈ 300-400 токенов)
EMBED_CHARS = 1800      # потолок текста для эмбеддинга (строка таблицы)

# ---------- конфиг по файлам (по префиксу номера) ----------
ROW_KIND = {  # kind для строк таблиц с >=3 колонок
    "05b": "spell", "05c": "spell", "15b": "relic",
    "06": "enemy", "30": "enemy", "10": "boss", "16": "catalog_item",
    "18": "room", "20": "catalog_item", "21": "catalog_item",
}
SECTION_KIND = {"24": "audio", "25": "ui", "18": "room"}
SKIP_FILES = ("coverage", "changelog", "readme")

NAME_HEADERS = ["имя", "приём", "прием", "босс", "тип", "враг", "реликвия", "название",
                "облик", "комната", "статус", "параметр", "поле", "эффект", "стихия",
                "источник", "достижение", "предмет", "событие", "звук", "экран", "действие"]

# ---------- авто-теги: regex -> теги (рус + англ) ----------
TAG_RULES = [
    (r"огн|пламен|поджог|горени", "огонь fire"),
    (r"вод[аыуе]|лёд|лед[яоян]|заморо|ледян", "вода/лёд water ice"),
    (r"воздух|ветр|ветер", "воздух air"),
    (r"земл|камен|шип", "земля earth"),
    (r"молни|шок|электр", "молния lightning"),
    (r"хаос", "хаос chaos"),
    (r"поджог", "поджог burn"),
    (r"заморо", "заморозка freeze"),
    (r"\bяд|отрав", "яд poison"),
    (r"замедлен", "замедление slow"),
    (r"корн[иея]|оплет", "корни root"),
    (r"рывок|рывк|dash", "рывок dash"),
    (r"парир|отби[вт]", "парирование parry"),
    (r"неуязвим|имм\.|i-?frame", "неуязвимость iframes"),
    (r"оглуш", "оглушение stun"),
    (r"отбрасыв|откид", "отбрасывание knockback"),
    (r"перезарядк|кулдаун|\bКД\b", "перезарядка cooldown"),
    (r"комбо|серия удар|цепочк", "комбо combo"),
    (r"отмен[аыу]|окн[оа] отмен", "отмена cancel"),
    (r"ульт", "ульта ultimate"),
    (r"крит", "крит crit"),
    (r"проклят|проклят", "проклятие curse"),
    (r"телеграф|замах|предупрежден", "телеграф telegraph"),
    (r"хитстоп|hit-?stop|замирани", "хитстоп hitstop"),
    (r"тряск|shake", "тряска screenshake"),
    (r"лут|дроп|выпад|добыч", "лут loot"),
    (r"золот|кристалл|валют", "экономика economy"),
    (r"магазин|лавк|цен[аыу]", "магазин shop"),
    (r"генерац|разъ[её]м|сид\b|seed", "генерация levelgen"),
    (r"софтлок|тупик|недостижим", "софтлок softlock"),
    (r"босс|финальн", "босс boss"),
    (r"элит", "элита elite"),
    (r"призыв|призван|summon", "призыв summon"),
    (r"снаряд|projectile", "снаряд projectile"),
    (r"прыжок|jump", "прыжок jump"),
    (r"луч|beam", "луч beam"),
    (r"реликв", "реликвия relic"),
    (r"аркан", "аркана spell"),
    (r"подстройк|компенсац|баланс", "подстройка adaptive"),
    (r"ИИ|состояни|автомат|выбор приёма|тревог", "ИИ ai"),
    (r"камер", "камера camera"),
    (r"здоровь|\bHP\b|сердц", "здоровье health"),
    (r"мета|открыти|разблок", "мета meta"),
    (r"кооп|pvp|напарник", "кооп coop"),
]
TAG_RULES = [(re.compile(p, re.I), t) for p, t in TAG_RULES]
ARCHETYPES = ["melee_combo", "projectile", "dash", "jump", "beam", "zone", "summon"]


FILE_COLL = {  # префикс файла спеки -> id коллекции из taxonomy/collections.yaml
    "00": "code_architecture_patterns", "01": "locomotion_profiles", "02": "attack_timelines",
    "03": "juice_feedback", "04": "status_effects", "05": "arcana_catalog", "05b": "arcana_catalog",
    "05c": "arcana_catalog", "06": "enemy_ai_behaviors", "07": "floor_generation_rules",
    "08": "encounter_composition", "09": "drop_tables", "10": "boss_patterns", "11": "run_structure",
    "12": "meta_unlocks", "13": "multiplayer_modes", "14": "stat_pipelines", "15": "effect_templates",
    "15b": "relic_catalog", "16": "outfits", "17": "special_rooms_services", "18": "special_rooms_services",
    "19": "boss_patterns", "20": "props_hazards", "21": "summons_allies", "22": "status_effects",
    "23": "camera_behaviors", "24": "audio_cues", "25": "ui_surfaces", "26": "input_bindings",
    "27": "dialog_localization", "28": "achievements_stats", "29": "tutorial_onboarding",
    "30": "enemy_roster"}
KIND_COLL = {"enemy": "enemy_roster", "boss": "boss_patterns", "relic": "relic_catalog",
             "spell": "arcana_catalog", "audio": "audio_cues", "ui": "ui_surfaces"}
TITLE_COLL = [  # ключевые слова в заголовке (проверяются раньше файла)
    (re.compile(r"затухан|кривая|кривые|easing|lerp|демпф|сглаживан|плавн|экспоненц", re.I), "value_curves"),
    (re.compile(r"подстройк|компенсац", re.I), "difficulty_adaptation"),
    (re.compile(r"хитстоп|тряск", re.I), "juice_feedback"),
]


def assign_collection(prefix: str, kind: str, title: str, sec_title: str) -> str:
    for rx, coll in TITLE_COLL:
        if rx.search(title) or rx.search(sec_title):
            return coll
    if prefix == "09" and re.search(r"цен|валют|магазин", title + " " + sec_title, re.I):
        return "currencies_prices"
    if kind in KIND_COLL:
        return KIND_COLL[kind]
    return FILE_COLL.get(prefix, "code_architecture_patterns")


def auto_tags(system_slug: str, title: str, text: str, extra: list[str] | None = None) -> str:
    tags = [system_slug]
    hay = title + "\n" + text[:2500]
    for rx, t in TAG_RULES:
        if rx.search(hay):
            tags.append(t)
    for a in ARCHETYPES:
        if re.search(rf"\b{a}\b", hay):
            tags.append(a)
    tags += extra or []
    seen, out = set(), []
    for t in " ".join(tags).split():
        if t not in seen:
            seen.add(t)
            out.append(t)
    return " ".join(out)


# ---------- разбор markdown ----------
def slugify(h: str) -> str:
    s = re.sub(r"[`*_]", "", h.strip().lower())
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s", "-", s.strip())


def strip_md(s: str) -> str:
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return s.strip()


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    parts = re.split(r"(?<!\\)\|", line)
    return [p.replace("\\|", "|").strip() for p in parts]


def is_sep(line: str) -> bool:
    return bool(re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", line))


class Section:
    def __init__(self, level, title, line, parents):
        self.level, self.title, self.line, self.parents = level, title, line, parents
        self.text: list[tuple[int, str]] = []          # (lineno, line) вне таблиц
        self.tables: list[tuple[int, list[str], list[tuple[int, list[str]]]]] = []


def parse_md(text: str):
    """-> (h1_title, [Section]). Секция = заголовок любого уровня + то, что до следующего."""
    lines = text.splitlines()
    h1 = None
    stack: list[tuple[int, str]] = []
    sections = [Section(0, "", 1, [])]
    in_code = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            in_code = not in_code
            sections[-1].text.append((i + 1, ln))
            i += 1
            continue
        m = None if in_code else re.match(r"^(#{1,6})\s+(.*\S)\s*$", ln)
        if m:
            lvl, title = len(m.group(1)), strip_md(m.group(2))
            if lvl == 1 and h1 is None:
                h1 = title
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            sections.append(Section(lvl, title, i + 1, [t for _, t in stack]))
            stack.append((lvl, title))
            i += 1
            continue
        if not in_code and ln.lstrip().startswith("|") and i + 1 < len(lines) and is_sep(lines[i + 1]):
            hdr = split_row(ln)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, split_row(lines[j])))
                j += 1
            sections[-1].tables.append((i + 1, hdr, rows))
            i = j
            continue
        sections[-1].text.append((i + 1, ln))
        i += 1
    return h1, sections


# ---------- числа ----------
NUM = re.compile(r"^[+\-−]?\d+(?:[.,]\d+)?\s*(?:%|×|x)?$")
LIST = re.compile(r"^\[\s*[+\-−\d.,\s/→]+\]$")


def to_num(s: str):
    s2 = s.replace("−", "-").replace(",", ".").replace("%", "").replace("×", "").replace("x", "").strip()
    try:
        f = float(s2)
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def parse_cell(c: str):
    c = strip_md(c).strip()
    if not c or c in ("—", "-"):
        return None
    if NUM.match(c):
        n = to_num(c)
        if n is not None:
            return n
    if LIST.match(c):
        vals = [to_num(x) for x in re.split(r"[,\s]+", c.strip("[] ")) if x]
        if vals and all(v is not None for v in vals):
            return vals
    return c


UNIT = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s?(с|м/с|м|%|×|шт|ур\.?|HP)(?![\w])")


def text_numbers(text: str) -> dict | None:
    out = []
    for m in UNIT.finditer(text):
        v = to_num(m.group(1))
        if v is not None:
            out.append({"v": v, "u": m.group(2)})
        if len(out) >= 24:
            break
    return {"values": out} if out else None


# ---------- построение записей ----------
def first_sentence(text: str, n: int = 220) -> str:
    for ln in text.splitlines():
        ln = strip_md(re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", ln))
        if len(ln) > 15 and not ln.startswith("|"):
            return ln if len(ln) <= n else ln[: n - 1].rsplit(" ", 1)[0] + "…"
    return ""


def chunk_text(text: str, limit: int = MAX_CHARS) -> list[str]:
    paras = re.split(r"\n\s*\n", text.strip())
    units = []
    for p in paras:
        if len(p) <= limit:
            units.append(p)
        else:
            cur = ""
            for ln in p.split("\n"):
                while len(ln) > limit:  # очень длинная строка
                    cut = ln.rfind(". ", 0, limit)
                    cut = cut + 1 if cut > limit // 3 else limit
                    if cur:
                        units.append(cur)
                        cur = ""
                    units.append(ln[:cut])
                    ln = ln[cut:].lstrip()
                if len(cur) + len(ln) + 1 > limit and cur:
                    units.append(cur)
                    cur = ln
                else:
                    cur = (cur + "\n" + ln) if cur else ln
            if cur:
                units.append(cur)
    chunks, cur = [], ""
    for u in units:
        if cur and len(cur) + len(u) + 2 > limit:
            chunks.append(cur)
            cur = u
        else:
            cur = (cur + "\n\n" + u) if cur else u
    if cur:
        chunks.append(cur)
    return chunks


def pick_name_col(hdr: list[str]) -> int:
    low = [strip_md(h).lower() for h in hdr]
    for nh in NAME_HEADERS:
        for i, h in enumerate(low):
            if h == nh:
                return i
    for i, h in enumerate(low):
        if h not in ("№", "#", "n", "id"):
            return i
    return 0


def section_kind(prefix: str, sec: Section, body: str) -> str:
    t = sec.title.lower()
    if t.startswith("числа"):
        return "number"
    if t.startswith("критерии"):
        return "rule"
    if t.startswith("открытые вопросы") or t.startswith("цель"):
        return "other"
    if prefix == "10" and re.match(r"(босс|финальн)", t):
        return "boss"
    if prefix == "30" and re.match(r"\d+\.", t):
        return "enemy"
    if prefix in SECTION_KIND:
        return SECTION_KIND[prefix]
    lines = [l for l in body.splitlines() if l.strip()]
    listy = sum(1 for l in lines if re.match(r"^\s*(\d+[.)]|[-*])\s", l))
    if lines and listy / len(lines) >= 0.6 and len(lines) >= 3:
        return "rule"
    return "mechanic"


def build_entries(spec_file: str, text: str):
    """-> (system_title, [entry dict])"""
    prefix = re.match(r"^(\d+[a-z]?)", spec_file).group(1) if re.match(r"^\d", spec_file) else ""
    slug = Path(spec_file).stem
    h1, sections = parse_md(text)
    sys_title = h1 or slug
    entries = []
    for sec in sections:
        body = "\n".join(l for _, l in sec.text).strip()
        path = [p for p in sec.parents if p != h1]
        ctx = " / ".join([sys_title] + path + ([sec.title] if sec.title and sec.title != h1 else []))
        anchor = slugify(sec.title) if sec.title else ""
        # 1) текст секции
        if len(body) >= 25:
            kind = section_kind(prefix, sec, body) if sec.level else "other"
            chunks = chunk_text(body)
            for i, ch in enumerate(chunks):
                title = sec.title or sys_title
                if len(chunks) > 1:
                    title += f" ({i + 1}/{len(chunks)})"
                entries.append(dict(
                    kind=kind, title=title, summary=first_sentence(ch), body=ch,
                    numbers=text_numbers(ch), spec_file=spec_file, anchor=anchor,
                    source_ref=f"{spec_file}:{sec.line}", ctx=ctx,
                    tags=auto_tags(slug, sec.title, ch, [slugify(p) for p in path[-1:]] and
                                   [w for w in re.findall(r"\w+", " ".join(path).lower()) if len(w) > 3][:4])))
        # 2) таблицы: каталожные -> по строке; маленькие kv -> остаются в теле как текст
        for tline, hdr, rows in sec.tables:
            if len(hdr) < 3 or len(rows) < 1:
                tbl = "\n".join(" | ".join(r) for _, r in rows)
                if len(tbl) >= 25 and rows:
                    kvtext = "\n".join(f"{r[0]}: {' | '.join(r[1:])}" for _, r in rows if r)
                    for i, ch in enumerate(chunk_text(kvtext)):
                        entries.append(dict(
                            kind="number" if sec.title.lower().startswith("числа") or prefix != "" else "other",
                            title=f"{sec.title or sys_title} — таблица" + (f" ({i + 1})" if i else ""),
                            summary=first_sentence(ch), body=ch, numbers=text_numbers(ch),
                            spec_file=spec_file, anchor=anchor, source_ref=f"{spec_file}:{tline}",
                            ctx=ctx, tags=auto_tags(slug, sec.title, ch)))
                continue
            ni = pick_name_col(hdr)
            rkind = ROW_KIND.get(prefix, "number")
            if prefix in ("06", "30") and strip_md(hdr[ni]).lower() not in ("тип", "враг", "имя", "название"):
                rkind = "number"
            if prefix == "15b" and re.search(r"(группы|рецепты|взаимоисключения|базовые)", sec.title.lower()):
                rkind = "other"
            if prefix in ("05b", "05c") and re.match(r"(как читать|сквозные|исправления|открытые)", sec.title.lower()):
                rkind = "other"
            for rline, cells in rows:
                cells = cells + [""] * (len(hdr) - len(cells))
                name = strip_md(cells[ni]) or f"строка {rline}"
                if rkind not in ("spell", "relic") and sec.title:
                    name = f"{name} — {sec.title.split(' (')[0]}"
                nums = {}
                lines_b = []
                for hname, c in zip(hdr, cells):
                    hname = strip_md(hname)
                    v = parse_cell(c)
                    if v is not None:
                        nums[hname] = v
                        lines_b.append(f"{hname}: {strip_md(c)}")
                body_r = "\n".join(lines_b)
                others = [f"{strip_md(h)}: {strip_md(c)}" for k, (h, c) in enumerate(zip(hdr, cells))
                          if k != ni and strip_md(c) not in ("", "—") and strip_md(h) not in ("№",)]
                summ = (sec.title + ": " if sec.title else "") + "; ".join(others)
                summ = summ if len(summ) <= 240 else summ[:239].rsplit(" ", 1)[0] + "…"
                coll = None
                if prefix == "15b" and re.search(r"(группы|рецепты)", sec.title.lower()):
                    comps, res = [], []
                    for h, c in zip(hdr, cells):
                        ids = re.findall(r"`([^`]+)`", c)
                        hl = strip_md(h).lower()
                        if hl.startswith("части"):
                            comps = ids
                        elif hl.startswith(("результат", "контейнер")):
                            res = ids
                    is_rec = "рецепт" in sec.title.lower()
                    nums = {"components": comps, "result" if is_rec else "container": (res[0] if res else None),
                            "synergy": "recipe: части сливаются в результат" if is_rec
                                       else "group: контейнер объединяет части в одну позицию пула",
                            "rationale": name.split(" — ")[0]}
                    coll, rkind = "item_synergies", "catalog_item"
                entries.append(dict(
                    kind=rkind, title=name, summary=summ, body=body_r, numbers=nums or None,
                    spec_file=spec_file, anchor=anchor, source_ref=f"{spec_file}:{rline}",
                    ctx=ctx, collection=coll, tags=auto_tags(slug, f"{sec.title} {name}", body_r)))
    for e in entries:
        if not e.get("collection"):
            e["collection"] = assign_collection(prefix, e["kind"], e["title"], e["ctx"].split(" / ")[-1])
    return sys_title, entries


# ---------- запись в БД ----------
def ingest(game: str, spec: Path, title: str | None, engine: str | None, notes: str | None,
           embed: bool, model: str, extra: Path | None = None):
    con = C.connect()
    now = dt.datetime.now().isoformat(timespec="seconds")
    if C.TAXONOMY_PATH.exists():
        C.load_taxonomy(con)
    row = con.execute("SELECT id FROM games WHERE slug=?", (game,)).fetchone()
    if row:
        gid = row["id"]
        con.execute("UPDATE games SET title=COALESCE(?,title), engine=COALESCE(?,engine), "
                    "spec_path=?, notes=COALESCE(?,notes) WHERE id=?",
                    (title, engine, str(spec), notes, gid))
    else:
        gid = con.execute("INSERT INTO games(slug,title,engine,spec_path,notes) VALUES(?,?,?,?,?)",
                          (game, title or game, engine, str(spec), notes)).lastrowid

    # кэш эмбеддингов по хешу текста, чтобы re-ingest был дешёвым
    cache = {r["text_hash"]: r["vec"] for r in con.execute(
        "SELECT m.text_hash, m.vec FROM embeddings m JOIN entries e ON e.id=m.entry_id "
        "WHERE e.game_id=? AND m.model=?", (gid, model))}

    # полная замена строк игры
    ids = [r[0] for r in con.execute("SELECT id FROM entries WHERE game_id=?", (gid,))]
    if ids:
        q = ",".join("?" * len(ids))
        for chunk_start in range(0, len(ids), 500):
            part = ids[chunk_start:chunk_start + 500]
            qq = ",".join("?" * len(part))
            con.execute(f"DELETE FROM entries_fts WHERE rowid IN ({qq})", part)
            con.execute(f"DELETE FROM embeddings WHERE entry_id IN ({qq})", part)
            con.execute(f"DELETE FROM links WHERE from_id IN ({qq}) OR to_id IN ({qq})", part + part)
            con.execute(f"DELETE FROM record_tags WHERE entry_id IN ({qq})", part)
    con.execute("DELETE FROM entries WHERE game_id=?", (gid,))
    con.execute("DELETE FROM systems WHERE game_id=?", (gid,))

    files = sorted(p for p in spec.glob("*.md") if not p.stem.lower().startswith(SKIP_FILES))
    all_new = []  # (entry_id, embed_text)
    sources = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        sys_title, ents = build_entries(p.name, text)
        sources.append((dict(slug=p.stem, title=sys_title, spec_file=p.name), ents))
    if extra:
        import ingest_extra as X
        for fn in (X.anim_entries, X.curve_entries):
            sd, ents = fn(extra)
            if sd:
                sources.append((sd, ents))
        import ingest_data as D
        sources.extend(D.data_entries(extra.parent))
    sd, ents = X.coverage_entries(spec) if extra else (None, [])
    if sd:
        sources.append((sd, ents))
    for sysd, ents in sources:
        sid = con.execute("INSERT INTO systems(game_id,slug,title,spec_file) VALUES(?,?,?,?)",
                          (gid, sysd["slug"], sysd["title"], sysd["spec_file"])).lastrowid
        for e in ents:
            eid = con.execute(
                "INSERT INTO entries(game_id,system_id,collection,kind,title,summary,body_md,numbers_json,tags,"
                "spec_file,anchor,source_ref,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (gid, sid, e["collection"], e["kind"], e["title"], e["summary"], e["body"],
                 json.dumps(e["numbers"], ensure_ascii=False) if e["numbers"] else None,
                 e["tags"], e["spec_file"], e["anchor"], e["source_ref"], now)).lastrowid
            con.execute("INSERT INTO entries_fts(rowid,title,summary,body,tags) VALUES(?,?,?,?,?)",
                        (eid, C.stem_text(e["title"]), C.stem_text(e["summary"]),
                         C.stem_text(e["body"]), C.stem_text(e["tags"])))
            etext = f"{e['ctx']}\n{e['title']}\n{e['body']}\nТеги: {e['tags']}"[:EMBED_CHARS]
            all_new.append((eid, etext))
    con.commit()
    print(f"[ingest] {game}: {len(files)} файлов, {len(all_new)} записей")

    t0 = time.time()
    todo = [(i, t) for i, t in all_new if C.text_hash(t) not in cache]
    print(f"[embed] модель {model}; из кэша {len(all_new) - len(todo)}, новых {len(todo)}"
          + ("" if embed else " (пропущены: --no-embed)"))
    # сначала сохраняем то, что есть в кэше (так --no-embed не стирает векторы)
    for eid, t in all_new:
        if C.text_hash(t) in cache:
            blob = cache[C.text_hash(t)]
            con.execute("INSERT INTO embeddings(entry_id,model,dim,vec,text_hash) VALUES(?,?,?,?,?)",
                        (eid, model, len(blob) // 4, blob, C.text_hash(t)))
    con.commit()
    if embed and todo:
        # порциями с коммитом: прерванный прогон не теряет уже посчитанное (при повторе — из кэша)
        for k in range(0, len(todo), 512):
            part = todo[k:k + 512]
            arr = C.embed([t for _, t in part], "passage", model)
            for (eid, t), v in zip(part, arr):
                con.execute("INSERT INTO embeddings(entry_id,model,dim,vec,text_hash) VALUES(?,?,?,?,?)",
                            (eid, model, len(v), v.tobytes(), C.text_hash(t)))
            con.commit()
            print(f"[embed] {min(k + 512, len(todo))}/{len(todo)} ({time.time() - t0:.0f}s)", flush=True)
        print(f"[embed] готово за {time.time() - t0:.1f}s")
    import tag  # смысловые теги (taxonomy/tags.yaml); для каждой новой игры — автоматически
    tag.tag_game(con, game)
    con.execute("PRAGMA optimize")
    con.execute("VACUUM")
    con.close()


def main():
    C.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--game", required=True, help="slug игры, напр. wol")
    ap.add_argument("--spec", required=True, help="папка со спеками (*.md)")
    ap.add_argument("--title")
    ap.add_argument("--engine")
    ap.add_argument("--notes")
    ap.add_argument("--extra", help="папка data/extra референса (anim_*.csv, physics_bodies.csv, colliders.csv, extra_values.json); соседняя data/assets подхватывается")
    ap.add_argument("--no-embed", action="store_true", help="только текст+FTS, без векторов")
    ap.add_argument("--model", default=C.MODEL_NAME)
    a = ap.parse_args()
    spec = Path(a.spec)
    if not spec.is_dir():
        raise SystemExit(f"нет папки: {spec}")
    ingest(a.game, spec, a.title, a.engine, a.notes, not a.no_embed, a.model,
           Path(a.extra) if a.extra else None)


if __name__ == "__main__":
    main()
