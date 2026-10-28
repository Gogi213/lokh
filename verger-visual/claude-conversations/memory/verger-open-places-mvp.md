---
name: verger-open-places-mvp
description: "Verger MVP без Google (2026-10-16..21): своя база Overture+Foursquare, бесплатные LLM, 5 категорий, где лежит, как запускать, цифры, что дальше"
metadata:
  node_type: memory
  type: project
  originSessionId: f182c75a-76ea-434d-a76c-63e65b252d5c
  modified: 2026-10-21T18:31:41.367Z
---

**Цель (решение пользователя):** сначала MVP у себя локально, гонять на всех заведениях, что можно скачать; сервер verger и стейджинг НЕ трогать (запрет 2026-10-16/21). География продукта — Европа + T1.

**Код:** ветка `open-places` в `C:\vdev\verger` (ASCII-путь, отдельный клон). Коммит `2680e15` (прототип, локально, не запушен); всё после него НЕ закоммичено: 5 категорий, сведённая база, рейтинги Google в кэше с TTL, ускорение, фоновые теги. typecheck чистый, unit 326/326.
- Запуск: `pwsh -File C:\vdev\run-local.ps1` (лучше `Start-Process ... -WindowStyle Hidden`, иначе умирает с сессией) → http://localhost:3200, лог `C:\vdev\meteor-run.log`. Meteor на Windows только из ASCII-пути + патч npx.cmd в `C:\vdev\.meteor\packages\rspack\1.1.0\plugin.rspack.os\packages\tools-core.js` (os/lib/npm.js патчить нельзя — ломает сборку). `VENUES_REIMPORT=1` в env процесса → каждая правка сервера перегружает базу 10–13 мин; запускать без него.
- Локальный админ `admin@verger.local`, пароль в `C:\vdev\verger\.env` (ADMIN_PASSWORD). Mongo: `mongodb://127.0.0.1:3201`, БД `meteor`; драйвер для скриптов `C:\vdev\.meteor\packages\npm-mongo\6.16.2\npm\node_modules\mongodb`. Скрипты в `C:\vdev\tmp\*.cjs`.
- `.env` (gitignored): PLACES_SOURCE=open, VENUES_FILE, ENABLED_VENUE_TYPES=restaurant,bar,club,wine,cocktail, FIRST_COLLECTION_SIZE=8, LLM: ранжирование Groq `openai/gpt-oss-120b`, теги Ollama Cloud `gemma4:31b`, фолбеки Ollama gpt-oss:120b → Mistral ministral-14b. Ключи пользователя (Groq, Ollama, OpenRouter, HF, Mistral, NVIDIA) там же — попали в чат, советовал перевыпустить.

**Что сделано в коде:** openProvider (поиск/детали/фото из своей базы, точное имя без нечёткого скана), venueCandidates (кандидаты из базы: без сетей, сначала `attested` = есть в обеих картах, потом с сайтом; приоритет типов любимых мест), chatProvider (OpenAI-совместимые LLM, раунды по 8), типы `wine`/`cocktail` отдельно от `bar`, `enabledVenueTypes`, фото: og:image сайта → Google Photos при наличии GOOGLE_PLACES_KEY, рейтинги Google пачками по городу в `googleCache` с TTL 30 дней (Google разрешает только кэш ≤30 дн., навсегда — только place_id), `admin.places.probe`, замер `[trip timing]` в логе.

**База (46 городов):** `C:\verger-data\pilot\build_base.py all` → `venues.ndjson` 1,56 млн мест (обе карты 302k, только Overture 866k, только Foursquare 391k, закрыто по FSQ 36k). Поля `attested`, `vtype`, `chain` проставлены в Mongo (скрипты backfill). Foursquare по городам вырезан в `C:\verger-data\top\fsq_cities.parquet`.
**Скорость подборки:** было ~52 с → 7–15 с до показа (кандидаты 0,3 с, проверка 0,1 с, модель 7–13 с), теги дописываются в фоне ~15 с.

**Покрытие (C:\verger-data\top, coverage.py):** Мишлен Европа+T1 14 825: Overture 88,8%, Foursquare 90,7%, OSM 59,7% (только точки), все три 95,6%. Бары 20k (50 Best + Wikidata, перекос US/GB): 60,7/53,4/14,8 → 71,0%. Топ-100 баров после фикса поиска: ~90 правильно. OSM добавляет <1 п.п. и ODbL (share-alike) — в базу не вливать; AllThePlaces — одни сети.

**Цены Google (сверено):** IDs Only $0 (place_id, ссылки на фото); Essentials $5/1k; Pro $17/1k (название, статус); Enterprise $20/1k (рейтинг, часы, телефон, сайт); +Atmosphere $25/1k (отзывы); фото $7/1k; пачкой Text Search Pro/Ent/Atm $32/35/40 за 20 мест. Старый чек ~$0,55–0,90/поиск → ~$0,03–0,04 (только фото).

**Дальше:** тест на госреестрах (UK FSA ~50k пабов/баров, NY SLA ~70k, FR SIRENE с датой закрытия) — источники найдены, не скачаны; работа через плагин role-play-vibing: 2026-10-21 развёрнут в `C:deverger` (плагин local 2.0.6, rpv-init сделан, реестр В-1 «проекты через плагин, текущая сессия — CEO», диспетчер+сторож запущены, задача ОС rpv-supervise-3131fcb1). Сессия «Verger CEO» — CEO. Цель MVP/госреестры в реестр не записана — секретарь требует слов владельца. Код WIP не закоммичен — роли работают в worktree от HEAD ветки, нужен локальный коммит с «да» владельца. Связано: [[verger-project]], [[feedback-decide-dont-ask]], [[feedback-scope-discipline]].
