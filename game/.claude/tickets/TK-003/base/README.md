# mechanics-db — локальная коллекция всего, что можно собрать из игр (для изучения геймдизайна)

Бесплатная, офлайн, мультиигровая. Берёт папку поведенческих спеков игры (markdown) и структурные данные
(тайминги анимаций, физика, коллайдеры, цены, дропы, комнаты, умения…),
режет на записи и раскладывает по **коллекциям** таксономии (53 штуки в 9 семействах),
кладёт в один файл SQLite `mechanics.db` и ищет по ним **гибридно**:
BM25 (FTS5, русский стемминг) + векторное сходство (мультиязычные эмбеддинги), слияние через RRF.

Игра №1: `wol` — Wizard of Legend (`C:/visual projects/wol-study/docs/spec`).

## Установка (один раз)

```powershell
cd "C:\visual projects\mechanics-db"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install sentence-transformers numpy snowballstemmer pyyaml
```

Torch по умолчанию ставится CPU-сборкой (эмбеддинг ~6400 записей на CPU — часы). Для GTX 1660 Ti поставить CUDA-сборку
(в `.venv` уже стоит): `.\.venv\Scripts\python.exe -m pip install -U torch --index-url https://download.pytorch.org/whl/cu126 --no-deps`
— полный ingest WoL ≈ 2 минуты. ingest эмбеддит на GPU, запросы — на CPU (`MECH_DEVICE=cpu|cuda` переопределяет).
Модель скачивается с HuggingFace при первом запуске (~1.1 ГБ) и кэшируется.

## Модель и лицензия

`intfloat/multilingual-e5-base` (278M параметров, dim 768) — **лицензия MIT**, хорошо понимает русский.
Используются префиксы e5: `passage: ` для записей, `query: ` для запросов. Векторы — float32,
нормированные, хранятся BLOB-ами в `embeddings`; поиск — косинус (скалярное произведение) в numpy.
Другая модель: `--model intfloat/multilingual-e5-small` (быстрее, хуже) или переменная `MECH_MODEL`;
векторы разных моделей лежат рядом (ключ `entry_id, model`), но `search` использует ту, что указана.
Зависимости: sentence-transformers (Apache-2.0), numpy (BSD), snowballstemmer (BSD).

## Коллекции

Источник истины — `taxonomy/collections.yaml` (копия `C:/visual projects/reverse-kit/taxonomy/collections.yaml`;
чтобы обновить — скопировать файл поверх и сделать re-ingest, либо задать `MECH_TAXONOMY`). При каждом ingest
таблица `collections(slug, title, description, family, family_title, automation, priority, cross_game_key,
record_schema_json, extraction_source, wol_count)` перезагружается из YAML. Каждая запись принадлежит ровно одной
коллекции (`entries.collection`) + имеет теги.

Структурные payload'ы лежат в `numbers_json` по схеме коллекции, например:
- `anim_clips`: `{length_s, effective_length_s, fps, frames, loop, state_speed, events[{name,t}]}`
- `anim_event_timelines`: `{clip_length_s, events[{name,t,f?,i?}], n_events}`
- `value_curves`: `{type:"exp_decay", params:{linear:{drag,tau,half_life}, angular:{…}, bodies, mass_min, mass_max}}` (τ=1/drag, период полуспада=τ·ln2)
- `item_synergies` (группы/рецепты): `{components[], container|result, synergy, rationale}`
- `skill_records`: `{skill_id, side, damage[], knockbackMultiplier[], …}` как в данных

Что заполнено для WoL: спека → коллекции по файлам/ключевым словам (см. `FILE_COLL`/`TITLE_COLL` в `ingest.py`);
из `wol-ref/data/**` — `anim_clips`, `anim_event_timelines`, `anim_state_graphs`, `collision_geometry` (группы),
`physics_setup`, `value_curves` (затухание из drag), `skill_records`, `currencies_prices`, `drop_tables`, `room_templates`,
`camera_behaviors`, `outfits`, `props_hazards`, `enemy_roster`, `enemy_ai_behaviors`, `locomotion_profiles`,
плюс инвентарь счётчиков в `art_asset_inventory` (только числа, ассеты не копируются). Заголовки записей — собственные
(«враг №12: атака»); идентификаторы референса — только в `numbers`/`source_ref`/«Источник». `achievements_stats`
из данных не берётся (в `data/**` нет), есть только из спеки 28.

```powershell
& $py mech.py collections                       # коллекции со счётчиками по играм
& $py mech.py list --collection value_curves    # перечень записей коллекции (--json)
& $py mech.py search "затухание" --collection value_curves,anim_clips
```

## Схема (`mechanics.db`)

| Таблица | Суть |
|---|---|
| `collections(slug, title, description, family, …)` | таксономия коллекций (из YAML) |
| `games(id, slug, title, engine, spec_path, notes)` | игра |
| `systems(id, game_id, slug, title, spec_file)` | один спек-файл = одна система (`06-enemy-ai`) |
| `entries(id, game_id, system_id, collection, kind, title, summary, body_md, numbers_json, tags, spec_file, anchor, source_ref, updated_at)` | запись |
| `links(from_id, to_id, kind)` | ручные/кэшированные связи между играми (пока пусто; `similar` считает на лету) |
| `embeddings(entry_id, model, dim, vec, text_hash)` | векторы; `text_hash` нужен, чтобы re-ingest не пересчитывал неизменённое |
| `entries_fts` (FTS5) | title/summary/body/tags, **уже стеммированные** (rowid = entries.id) |

`kind`: `mechanic | rule | number | catalog_item | enemy | boss | spell | relic | room | ui | audio | other`.
`source_ref` = `файл:строка` в спеке, `anchor` = GitHub-слаг заголовка (`spec_file#anchor`).
`numbers_json`: для строк таблиц — `{колонка: число | список | текст}`; для текстовых записей —
`{"values":[{"v":1.25,"u":"м"},…]}` (числа с единицами с, м, м/с, %, ×).

### Как режется спека
- Каждый заголовок любого уровня = секция → запись (`mechanic`, `rule` если это в основном нумерованный список,
  `number` для «Числа…», `boss`/`enemy`/`room`/`ui`/`audio` по файлу). Тело > ~1100 символов режется на куски `(1/3)`.
- Таблицы с ≥ 3 колонками → **по записи на строку** (`05b`/`05c` → `spell`, `15b` → `relic`, `06`/`30` → `enemy`,
  `10` → `boss`, `16` → `catalog_item`, `18` → `room`, остальное → `number`). Таблицы из 2 колонок остаются записью-секцией.
- Пропускаются `README*`, `coverage*` и `CHANGELOG*` (аудит/журнал, не механики). Правка — `SKIP_FILES` в `ingest.py`.
- Авто-теги: slug системы + словарь ключевых слов (стихии, статусы, рывок/парирование/неуязвимость/оглушение,
  архетипы, триггеры…) на русском **и** английском — поэтому находится и запрос «dash iframes».

## Добавить игру

1. Положить спеки той же формы в папку (`*.md`, заголовки `#`, таблицы `|`; имя `NN-имя.md`).
2. ```powershell
   .\.venv\Scripts\python.exe ingest.py --game hades --spec "C:\path\to\hades\spec" --title "Hades" --engine "Unity"
   ```
   Если у игры другая раскладка файлов — добавить её префиксы в `ROW_KIND` / `SECTION_KIND` в `ingest.py`
   (по умолчанию строки таблиц получают kind `number`, секции — `mechanic`/`rule`).

## Перезалить (идемпотентно)

```powershell
.\.venv\Scripts\python.exe ingest.py --game wol --spec "C:\visual projects\wol-study\docs\spec"
```
Строки этой игры (записи, системы, FTS, векторы, связи) заменяются целиком; чужие игры не трогаются.
Векторы для неизменившегося текста берутся из кэша по `text_hash`, так что повторный прогон быстрый.
`--no-embed` — только текст и FTS (векторный поиск тогда недоступен до следующего ingest без флага).

## Запросы

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py mech.py search "рывок с неуязвимостью" -k 5
& $py mech.py search "окно отмены комбо" --game wol --kind mechanic,rule
& $py mech.py search "стихийный босс" --system 10 --json        # --system: slug, номер или подстрока
& $py mech.py search "поджог" --mode bm25                       # hybrid (по умолчанию) | bm25 | vector
& $py mech.py show 650                                          # запись целиком (--json для агентов)
& $py mech.py stats                                             # записи по играм / видам / системам
& $py mech.py similar 650 --other-games                         # ближайшие по смыслу (в других играх)
& $py mech.py bench "запрос 1" "запрос 2" --top 3               # много запросов в одном процессе
```

Вывод `search`: заголовок, `игра/система · вид`, одна строка summary, `spec_file#anchor (файл:строка)`,
скор RRF (+ позиции в BM25 / векторном списках и косинус). `--json` отдаёт те же поля плюс `numbers`, `tags`, тайминги.
Латентность: холодный CLI-запрос ≈ 20 с (импорт torch/sentence-transformers + загрузка модели).
Чтобы было быстро — запустить один раз `mech.py serve` (держит модель в памяти на 127.0.0.1:8765, `MECH_PORT`);
тогда каждый `search` ≈ 0.3 с (BM25 ≈ 80 мс, векторы ≈ 100 мс, эмбеддинг запроса ≈ 150 мс), без сервера — автоматический
откат на локальную загрузку модели. `bench` грузит модель один раз и меряет «тёплые» запросы (≈ 100–200 мс).

## Хранение БД в git

`mechanics.db` **коммитится**, пока < 50 МБ (сейчас ≈ 43 МБ для WoL: ~6400 записей × 768 float32 + текст; при добавлении игр лимит быстро кончится).
Если база разрастётся после добавления игр — раскомментировать `mechanics.db` в `.gitignore`
и пересоздавать её командой `ingest.py` (всё детерминированно собирается из спеков).
`.venv/` в git не попадает никогда.

## Ограничения
- Поиск — по смыслу и ключевым словам, не LLM-ответчик: результат — ссылки на места в спеке.
- Чанкинг по символам (≈1100), эмбеддинг режется до 512 токенов — у очень длинных строк-каталогов хвост не векторизуется
  (но остаётся в BM25 и в `show`).
- Русский стемминг — Snowball (без морфологического словаря): редкие формы могут не совпасть, векторный канал это страхует.

## Полная команда ingest для WoL (спека + структурные данные)

```powershell
.\.venv\Scripts\python.exe ingest.py --game wol --spec "C:\visual projects\wol-study\docs\spec" --extra "C:\visual projects\wol-ref\data\extra" --title "Wizard of Legend" --engine "Unity/Mono"
```
`--extra` — папка `data/extra` референса; соседняя `data/assets` подхватывается сама. Для новой игры с такой же
раскладкой — те же флаги; без `--extra` грузится только спека.
