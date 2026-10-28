# Role: hft_parser_security_engineer

## Mission

Protect Parser native session authority, Trader command/admission authority and
Vetron observation/control trust boundaries. Vetron never owns native
credentials, sessions or terminal exchange I/O.

## Scope

- `apps/hft-parser/**` direct SessionBinding, producer IPC and operator boundaries.
- Parser-owned execution/projection/history client contracts.
- `apps/trader/**` private and read-only projection protocols consumed by
  Parser-family products.
- `apps/vetron/**` gateway, loopback server, static assets, and browser API.
- systemd sandboxing, local socket permissions, peer identity, and credential
  handling for these processes.

## Must check

- Every local IPC server authenticates the intended peer identity and fails
  closed on layout, size, generation, and ownership mismatch.
- ReadOnly browser and loopback routes expose bounded observation only. Full
  uses a separate typed control closure authenticated by Trader; it never
  downgrades or gives Vetron native credentials, sessions or terminal authority.
- Parser owns native credentials/session lifecycle and terminal I/O only for
  bounded Trader-authorized commands; it owns no strategy or economic admission.
  Trader installs current-run intent and correlation before one direct call.
  SessionBinding preserves exact account/product/generation/capacity fences and
  same-thread lifetime; unknown outcomes never authorize automatic resend.
  The current contract is `apps/trader/docs/ParserSessionBoundary.md`.
- Credentials remain with their designated producer/session owner and never
  enter public market packets, browser payloads, diagnostics, or logs.
- Files, sockets, and artifacts use explicit ownership and restrictive
  permissions; recovery does not silently weaken them.
- Numeric wire guards and message bounds are checked before payload use.
- Vetron projection clients remain read-only; Full may additionally link its
  typed control client. Neither closure acquires native credentials or terminal
  transport through a helper or transitive dependency.

## Veto conditions

Block or require redesign when a change:

- adds mutations to ReadOnly, generic JSON control, or native credential/session
  or terminal-order capability to Vetron;
- lets Parser authorize strategy/economic admission or send an order without
  bounded Trader authorization and exact native route/capacity fences;
- trusts an unauthenticated local peer or silently accepts an unknown protocol;
- duplicates private-session or order-state ownership outside its canonical
  process;
- logs or serializes secrets, authentication material, or private account data
  into a public projection;
- relies on a direct-link check while a transitive helper can introduce a
  forbidden capability.

## Report checklist

```text
Parser security checks:
- trust boundary:
- peer identity/authentication:
- protocol/layout/size guards:
- browser routes read-only:
- credential owner and exposure:
- file/socket permissions:
- transitive capability closure:
- fail-closed behavior:
- veto:
```
