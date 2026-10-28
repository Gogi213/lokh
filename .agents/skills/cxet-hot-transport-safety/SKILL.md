---
name: cxet-hot-transport-safety
description: Audit CXET transport and session safety. Use for WS/FIX/gRPC/hot REST, TLS, framing, partial I/O, heartbeat, reconnect, compression, sockets, or order sessions.
---

# CXET Hot Transport Safety

Use this skill for connection, framing, session, and terminal I/O boundaries;
use the parser skill for payload semantics.

## Workflow

1. Read root and nearest `AGENTS.md`, `docs/Agents/HotPathFastLane.md`, and `docs/Agents/Roles/HotTransportEngineer.md`.
2. Inspect existing caller/surface evidence. For a requested helper run,
   propose this command and wait for user selection:

   ```bash
   python3 tools/Codex/CxetToolbelt.py hotpath --surface transport --format summary
   ```

3. Identify the exact failure/cost stage: DNS, TCP, proxy, TLS, WS/FIX/gRPC/hot REST setup, subscribe/auth ACK, first frame, steady-state read, heartbeat, reconnect, order write, or ACK read.
4. Classify connect/auth/reconnect as C, steady-state receive/send as H0, ACK/user/session handoff as H1, and deep probes/logging as D.
5. Trace real callers through route/session code into `WsClient`/`WsConnection` or the corresponding FIX/gRPC transport.
6. Check CA loading, SNI, hostname verification, fail-closed TLS, nonblocking semantics, bounded timeouts, EINTR/EOF/WANT_READ/WANT_WRITE, partial I/O, frame/control/fragment/compression bounds, state reset, buffer/view lifetime, locks/atomics, pending correlation, and reconnect ownership.
7. Treat the terminal TLS/socket write as necessary. Flag every avoidable lock, wait, syscall, copy, clock capture, allocation, or diagnostic before it.
8. Do not add retry loops or transport fallback to hide a failed stage. Preserve the exact failure reason and repair the owning layer.

## Output

Report the stage, caller chain, H0/H1/C/D class, safety invariant, latency candidate, exact evidence, and narrow verification. Do not describe faster connect/reconnect as a tick-to-trade speedup.
