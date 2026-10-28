---
name: claude-subscription
description: "Владелец пользуется Claude по подписке, ключа API нет — не предлагать ANTHROPIC_API_KEY; для CI — CLAUDE_CODE_OAUTH_TOKEN"
metadata:
  type: user
---

Claude у владельца — по подписке, не по ключу API (14.10.2026: «апи ключ не нужен клод подключается подпиской»).

**Why:** предложение завести ANTHROPIC_API_KEY для CI он отверг — лишняя сущность и платёж.
**How to apply:** локальные прогоны (`claude -p`, e2e) идут подпиской; для машин без входа (GitHub Actions) единственный
путь — `claude setup-token` → секрет `CLAUDE_CODE_OAUTH_TOKEN` (в `ci.yml` задача `e2e` уже на него переведена).
Связано: [[v2-progress]].
