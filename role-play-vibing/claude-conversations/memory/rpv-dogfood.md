---
name: rpv-dogfood
description: "С 27.10.2026 плагин развивается своей же командой ролей в этом репо; сессия владельца — CEO; файлы команды вне git плагина"
metadata:
  type: project
---

27.10.2026 владелец: «подключай для разработки плагин», «эта сессия становится сео» (В-1 в `.claude/decisions.md`).
Диспетчер и сторож — из установленной копии (`~/.claude/plugins/cache/role-play-vibing/role-play-vibing/<версия>`), присмотр ОС
поставлен (задача `rpv-supervise-37b6bcc9`). Команда тикетов: `python ~/.claude/plugins/cache/role-play-vibing/role-play-vibing/<последняя версия>/.claude/dispatcher/tickets.py --project "C:\visual projects\role-play-vibing" …`.
`/rpv-init` здесь руками не гонять: он пишет `.claude/dispatcher/` в `.gitignore`, а тут это исходный код. Файлы команды
(`.claude/roles/`, `tickets/TK-*`, `goals/`, `errors/`, `decisions.md`, `CLAUDE.md`) исключены через `.git/info/exclude`,
чтобы не уехать в плагин. Метка CEO: `.claude/roles/.state/session-<id>.role` (CLAUDE_SESSION_ID пуст — id брать из пути scratchpad).
CP1 = TK-001…003 (Инженер), CP2 = TK-004/005 (backlog, после CP1), раунд ревью 1 = TK-006 (Исследователь, снимок origin/main). В-2 (работа в основной копии) заменено В-5: Инженеры параллельно, каждый в `.claude/worktrees/<тикет>`, как в плагине; умолчание плагина — ОДИН запуск на роль, поэтому в `.claude/rpv.json` стоит `role_parallel {"engineer": 3}` (проверка Судьёй TK-012) — владелец: «в твоей зоне сделать всю работу медленнее в три раза?». В `--desc` не ставить обратные кавычки в двойных кавычках bash — выполняются как команда. Правка кода действует на команду только после выпуска и `/rpv-start`.

**Why:** после клира новая сессия должна знать, что она CEO и где лежит команда.
**How to apply:** новая сессия — снова метка CEO, Monitor на `.claude/dispatcher/ceo-wake.log`, `tickets.py status`. Связано: [[v2-progress]], [[plugin-universal]].

В-4 (27.10): владельцу ничего не носить — пороги, правки поведения, слияние и выпуск решает Судья; `ci_repo` в `.claude/rpv.json` включает автовлив после приёмки Судьи и зелёного CI. Удаление веток на удалённом и force-push — по-прежнему нет.

С 2.0.7 (27.10 06:35): команда на 2.0.7; `.claude/rpv.json` и уставы CEO правит только `tickets.py config set … --why` (страж), новые строки уставов из выпуска переносить до перезапуска на новую версию. Выпуск: тикет Инженеру + `allow <ID> publish --ref В-10`, потом `claude plugin marketplace update role-play-vibing`, `claude plugin update role-play-vibing@role-play-vibing`, `start.py` и `supervise.py --install` из новой версии.

- `comment --next <роль>` по закрытому тикету будит роль — так переоткрывают (27.10, TK-026).
- С 2.0.9 уставы переносить `tickets.py charter sync` (сохраняет таблицу зон README, остальное README берёт из шаблона).
