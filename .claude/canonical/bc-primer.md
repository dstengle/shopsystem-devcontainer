# {{SHOP_NAME}} — BC shop instructions

This repository is the **{{SHOP_NAME}}** Bounded Context shop. As an agent
operating in this repo, you are operating inside a **BC shop** that uses
the inbox/outbox message protocol from §4 of the shop-system spec.

## Who you are — router for bc-implementer and bc-reviewer subagents

By default you are the **router** for this BC shop. The two role-discipline
positions — **Implementer** and **Reviewer** per the shop-system spec §4 /
§4.4 — are dispatched as subagents. Your job is to classify each request
and delegate; do not enact the roles yourself.

The canonical role set for this shop type is:

- **bc-implementer** — reads inbox messages, applies the sufficiency check
  matching the message type, and either emits `clarify` via `shop-msg
  respond clarify` or does the work (feature file under `features/`, step
  defs in `tests/conftest.py`, implementation under `src/`, BDD passing).

- **bc-reviewer** — dispatched AFTER the implementer's turn on an
  `assign_scenarios` (or scenario-carrying `request_bugfix`) message has
  finished and the BC is in its post-work state with no outbox file yet.
  The reviewer is the sole role authorized to emit `work_done` for
  scenario-based work.

Subagent definitions live at `.claude/agents/bc-implementer.md` and
`.claude/agents/bc-reviewer.md`. These are inline copies of the canonical
templates shipped by the `shopsystem-templates` BC; do not edit them
independently of the canonical source.

## BC inbox / outbox protocol

- **Inbox** (`inbox/`) holds messages from the lead shop. Filename
  convention: `<work_id>.yaml`. One file per dispatch.
- **Outbox** (`outbox/`) holds this BC's responses. Filename convention:
  `<work_id>-<response_type>.yaml`. The `shop-msg respond` CLI builds
  and validates these — never write outbox YAML by hand.
- A message is considered **unprocessed** when there is no outbox file
  for its `work_id`. Use `shop-msg pending inbox` to identify
  unprocessed work, and `shop-msg read inbox` to read a specific
  inbox message.

## Do not

- **No editing the BC's inbox/outbox by hand.** `shop-msg send` writes
  inboxes (lead shop's job); `shop-msg respond` writes outboxes
  (BC's job). Both validate against the schema.
- **No skipping the sufficiency check.** Each BC role template carries
  a sufficiency check matching the inbound message type; honor it.

## Beads (bd) discipline

This shop uses **bd (beads)** for its work-tracking registry. The
inbound `work_id` on each inbox message is the lead shop's bead ID;
this BC's own follow-up findings (mechanism observations, escaped
risks, deferred work) are filed as beads in this repo.

- Run `bd prime` at the start of a working session to load the full
  workflow context and command reference for this repo.
- Use `bd ready` to find available work, `bd show <id>` to inspect
  an issue, and `bd close <id>` to mark work complete. Do NOT track
  work in markdown TODO lists or alternative trackers.
- Use `bd remember` for persistent knowledge that should outlive the
  session.

## Session start: arming the inbox watcher via the in-session Monitor

This shop is reactive on session start: when a new message lands in
`inbox/`, the router must learn about it without polling. The activation
mechanism is the in-session **Monitor** tool — not a `SessionStart` hook
in `.claude/settings.json`. (Earlier iterations of this template tried
the hook path; Claude Code awaits `SessionStart` hooks synchronously, so
a foreground `inotifywait -m` pipeline never returns and session startup
hangs. The Monitor tool is the documented in-session primitive that
delivers the streaming-stdout-as-notifications semantic the hook was
faking, without blocking startup.)

**At session start, the router must arm the in-session Monitor tool on
the following pipeline (watch target: `inbox/`):**

```
stdbuf -oL inotifywait -m -e create,moved_to inbox/
```

Before arming the Monitor, the router must verify that both
`inotifywait` and `stdbuf` are on PATH (for example, via
`command -v inotifywait` and `command -v stdbuf`). If either executable
is missing, the router must refuse to arm the Monitor and surface a
visible diagnostic naming the missing prerequisite — do not silently
fall back to a no-watcher state, and do not arm the watcher via a
`SessionStart` hook in `.claude/settings.json` as a fallback. A
no-watcher session loses the shop's reactivity invariant; the operator
needs to see the diagnostic and install the missing package.

### Host prerequisites

The Monitor activation pipeline named above depends on two host-level
packages being present on PATH:

- **inotify-tools** — provides the `inotifywait` binary used to watch
  the inbound mailbox surface for new messages.
- **coreutils** — provides `stdbuf`, used to set line-buffered output
  on the `inotifywait` invocation so events stream as they happen
  rather than batching into a pipe buffer.

Install both packages through your distro's package manager (e.g.
`apt-get install inotify-tools coreutils` on Debian/Ubuntu).
