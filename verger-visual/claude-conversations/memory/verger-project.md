---
name: verger-project
description: "Verger — чужой приватный репо yellowcubee/verger в проде; ревью 2026-10-08, фиксы P0/P1 в draft PR #1 (2026-10-09), что осталось проверить"
metadata:
  node_type: memory
  type: project
  originSessionId: 3febc44e-4f59-4677-9fc7-ed2805a97b97
  modified: 2026-10-21T18:31:51.760Z
---

Репо `yellowcubee/verger` (автор Dmitrii, GitHub `yellowcubee`), приватный, у пользователя (`Gogi213`) write-доступ с 2026-10-08. Клон: `C:\visual projects\verger`. Meteor 3.5 + React 18 + MongoDB, LLM Claude/OpenAI, Google Places. Продукт в проде, владелец считает его «кривым».

**Ревью (2026-10-08):** 5 ревьюеров + 5 критиков, отчёт: https://claude.ai/artifact/KYgrCTWfBwMLKPSEhvXHHt (коммит 43cd9b2). Жалобы прода: валидация почты, повторная регистрация, прыгает вёрстка, «Noto» без города не находит Тбилиси (автодополнение без locationBias).

**Обновление 2026-10-09 вечер:** Дмитрий влил PR #1 в main (merge ada6e67, предварительно смержив main в ветку) и добавил свои PR #2–#4: аналитика Amplitude (по умолчанию выключена, `AMPLITUDE_ENABLED=false`), админ-настройки рантайма с редактированием промптов (наши лимиты теперь читаются через `setting()`), пагинация админки, одноразовые ссылки-приглашения вместо временного пароля, оптимизация разметки LLM и пакетное сохранение интересов, затем откат промптов тегирования/ранжирования к исходным (5d0dca3, проверено им: 317 unit + 89 серверных интеграционных тестов). Локальный main = 5ebbbaf, typecheck чистый, 317/317 unit. Наши фиксы в main сохранились (квота, ретраи, unblock, Caddy, CI/deploy, cityPlaceId).

**Ревью чужих коммитов после PR #1 (2026-10-09, остановлено по просьбе пользователя):** сделана только часть по дизайнеру (коммиты «design-poop» f4431b6, f98acdd, 4cea4cb): откатил наш анти-CLS на лендинге (`#access-feedback:empty { min-height: 0 }` в early-access.css), скрыл голосового ассистента (`SHOW_VOICE_ASSISTANT = false` в LiveApp.tsx), после мержа остались ключ-сирота `"Go": "Да"` в messages.ts и конфликтующие правила `.recommendation-refresh` в finishing.css. Не отревьюены: приглашения b88bd18, runtime-настройки 7a1018f, пагинация e20f330, Amplitude fd26f44 + коммиты nikitafedsv-eng, LLM 20fb4a1/5d0dca3, картинка 1,1 МБ 5ebbbaf. Промпты пользователю показаны (promptTemplates.ts, taggingPrompt.ts, searchIntentPrompt.ts; админ может переопределить PROMPT_DISCOVERY/PROMPT_RANKING в БД).

**Прод LLM (со слов пользователя 2026-10-09):** провайдер OpenAI, модель «вроде gpt-5-mini или nano» — не подтверждено. После 7a1018f настройки (OPENAI_MODEL, LLM_PROVIDER, лимиты, промпты) один раз копируются из env в Mongo (`initializeRuntimeSettings`), дальше база главнее env — смотреть админку. Док для разработчика про кэш промптов (перестановка блоков RANKING_TEMPLATE + prompt_cache_key; экономия ≈$0,002/отбор на gpt-5, на mini/nano почти ноль): https://claude.ai/code/artifact/74189d8c-e16b-4ec2-a6d7-6bd61ca9f7a7

**Инцидент 2026-10-09 (найден ~16:25 UTC):** после PR #5 (dd12929, стейджинг на том же VPS) verger.city отдаёт стейджинг-приложение (в HTML `ROOT_URL=https://stage.verger.city`, 20/20 запросов). Причина: сервис стейджа называется `app` и подключён к общей сети `verger_edge`, а прод-Caddy проксирует на `app:3000`, и это имя теперь указывает на оба контейнера. Стейдж запущен с 15:17 UTC. Фикс на сервере за Дмитрием (у нас доступа нет). Пользователю сделан личный SSH-ключ `C:\Users\Георгий\.ssh\verger_friend` (без фразы); публичная часть ушла Дмитрию, Docker-доступ не просили.

**Состояние на 2026-10-16:** локальный main = origin/main = 0a64fa5 (pull 2026-10-13; после 5ebbbaf пришли стейджинг-деплой, изоляция прод-прокси от стейджа a6f8d2d, экран загрузки и танцующая Верги, уведомления на мобиле), зависимости не менялись; typecheck чистый, 321/321 unit. Ревью этих коммитов не делали.

**Плагин пользователя role-play-vibing** (github.com/Gogi213/role-play-vibing, v1.8.25) установлен для verger в scope `local` (2026-10-16 обновлён до 2.0.5 — апдейт шёл из сессии Alpha; в кэше остался неиспользуемый 2.0.4, 1.8.x/2.0.2/2.0.3 пользователь удалил сам; `/rpv-init` в verger ещё не запускали; обновлять: `claude plugin update role-play-vibing@role-play-vibing --scope local`) (`.claude/settings.local.json`, игнорируется глобальным gitignore) 2026-10-09. `/rpv-init` пользователь запускает сам (у команды disable-model-invocation); он добавит строки в отслеживаемый `.gitignore` verger.

**Фиксы P0/P1 (история):** ветка `review-fixes-p0-p1`, коммит 4dbbf83, **PR https://github.com/yellowcubee/verger/pull/1 (влит)** (открыт 2026-10-09 по просьбе пользователя; draft — пока кто-то не прогонит Mocha и живой запуск; PR привязан к сессии, CI на момент открытия ещё не стартовал). Сделано: Caddy geolocation/microphone=(self); CI (`ci.yml`: `npm run typecheck`, `npm run test:unit`), deploy только из main, после CI, бэкап до выката, `compose up --wait`, тег `verger-app:previous` только со здорового образа; возврат попытки при сбое (TRIP_REFUNDS_PER_USER=3, tokensUsed в лимите); ранкер до 20 мест; коды ошибок до клиента + журнал фоновых сбоев; unblock только для чтений; `domain/email.ts`, TTL только для open-заявок, вход с временным паролем включает доступ; places.search с cityPlaceId/locale; fetchWithRetry (LLM не ретраит таймауты); бюджет фото; reset пароля plaintext 10..256; лендинг RU; анти-CLS; клиентские фиксы после критика (квота перечитывается, меню города в потоке, IDN-почта и др.). Проверено: typecheck чистый, 269/269 unit-тестов, два ревью диффа.

**Не проверено / открыто:**
- Mocha (78 тестов) и живой запуск: Meteor 3.5 на этой машине зависает после «Started MongoDB» (rspack не стартует; вероятно кириллица в пути `C:\Users\Георгий`; TEMP на `C:\verger-tmp` не помог). Нужен Linux/WSL/машина автора: `npm test`, `npm run dev`. Meteor стоит в `%LOCALAPPDATA%\.meteor` (ставить из PowerShell — в Git Bash GNU tar ломает установку).
- Первый деплой: миграция индексов заявок на старте (откат на старый образ требует удалить индекс `accessRequests_open_createdAt_ttl`); mongo и caddy пересоздадутся из-за изменений compose (healthcheck, логи) — пользователь спрашивал, я предложил оставить; убрать, если скажет.
- Ждут ответа пользователя: включать ли Auto-fix CI на PR; фолбек OpenAI↔Anthropic (не в P0/P1).
- Не сделано из ревью диффа (low): S-9..S-12, S-15, C-8, C-12, C-15.

**Побочные задачи:**
- Выгрузка OpenStreetMap по всему миру (кофейни, бары, пабы, рестораны, бордели, винное, клубы, пекарни) через Overpass в `C:\verger-data\osm\` (`fetch_osm.py`, `manifest.json`, `fetch.log`, возобновляемая; итог `venues-world.csv.gz` + `summary.md`). На ~09.10 вечер: 229 из 251 заданий, 1 154 769 мест в `venues-world.csv.gz` (38 МБ); не скачаны 18 крупных стран (US, DE, FR, IT, GB, JP, RU, BR, ES, PL, CN, IN, CA, AU, MX, NL, UA, TR) + YT, ZA, ZM, ZW — с этой машины Overpass часами недоступен по 80/443, зеркала kumi/private.coffee отдают старый снимок (не используются). Скрипт крутится в фоне. Команды: статус `py -3.12 -I C:\verger-data\osm\fetch_osm.py status`; перезапуск `... run --passes 1000`; стоп — файл `C:\verger-data\osm\STOP`; пересборка итога `... merge`. Компьютер не должен засыпать.
- Док-предложение команде «Своя база мест для Verger» (OSM → своя база, Google фолбеком): https://claude.ai/code/artifact/5282c077-56fa-4f2a-a40f-195def5299ab (приватный, пока пользователь не расшарит).
- Экономия токенов: сначала выгрузить `Trip.usage` с прода; идеи — не перетегировать места по 30-дневному TTL, пулы по типу, кэширование промптов (сейчас город в начале промпта — кэш не срабатывает), Haiku 5.5 для тегов.
- **MVP без Google (2026-10-16..21) — текущая главная работа:** всё в [[verger-open-places-mvp]] (код, запуск, база, покрытие, цены, что дальше). Старая Overpass-выгрузка OSM выше устарела — OSM перекачан через Geofabrik в `C:\verger-data\top\osm` (не используется в базе).
- Машина 16 ГБ RAM: тяжёлые выгрузки (QuackOSM) роняли её (перезагрузка 21.10 04:12) — DuckDB только с memory_limit, долгие задачи запускать отдельным процессом Windows.

**How to apply:** в новой сессии начинать с [[verger-open-places-mvp]]; прод/стейджинг не трогать; не мержить, не пушить, не деплоить без явного «да». См. [[feedback-harsh-factual-review]], [[feedback-scope-discipline]], [[user-communication]], [[feedback-decide-dont-ask]].
