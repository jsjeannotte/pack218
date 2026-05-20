# Pack 218 — Agent conventions

This file captures conventions any agent (human or otherwise) should follow when
working in this repository. Read before editing.

## Audit log convention (load-bearing)

Every persistent write to a model that inherits `SQLModelWithSave` (`User`,
`Family`, `Event`, `EventRegistration`) **must** go through
`SQLModelWithSave.save()` or `SQLModelWithSave.delete_by_id()`. Both methods
write one row to `ActionLog` in the same transaction, attributing the change
to the request's current actor with an optional reason.

Raw `session.add(instance)` followed by `session.commit()` **bypasses the
audit log** and is disallowed in production code without an explicit
`# audit: bypassed because <reason>` comment on the line. The audit log is
the only record of who did what; bypasses leave permanent gaps.

When the actor is acting on behalf of another user (the request's current
actor differs from the row's subject — see `pack218.audit.is_self_edit` for
the exact rule, which counts same-family edits as self-edits), the save path
requires a non-empty `current_reason` and rejects writes to blocklisted
fields (`email`, `username`, `hashed_password`, `is_admin`, `can_login`,
`email_confirmed`, `email_confirmation_code`) and admin-on-admin edits
(both User records and EventRegistrations whose owner is an admin).

**Exemption (the only one):** `ActionLog` itself is the universal-write-path
recursion bypass. Its `save()` skips enforcement and self-recording (otherwise
recording would recurse forever), and `delete_by_id()` raises — audit rows are
append-only. The bypass is annotated in `pack218/entities/__init__.py` with an
`audit:` comment. Do not add other exemptions without changing this contract.

**Test code is exempt** from the bypass-comment rule. Test fixtures and DB
setup helpers commonly need to seed rows directly via `session.add` /
`session.commit` to construct preconditions; the in-memory SQLite fixture has
no request context and no audit-log requirement. The rule above applies to
production paths only.

## Querying the audit log

The parent-visible "Changes made on my behalf" panel is the canonical read
pattern. See `pack218/pages/on_behalf_panel.py::_fetch_rows` for the
reference query, which:

1. Filters by `subject_user_id == current_user.id` OR
   `(entity_name == 'Family' AND entity_id == current_user.family_id)` —
   the latter surfaces Family-scoped writes to every family member without
   per-write fan-out.
2. Excludes `actor_user_id == current_user.id` to hide self-edits from the
   parent's view.
3. Orders by `created_at DESC`, capped to last 20 rows.

For agent-driven reads (e.g., "show me everything Cubmaster Dave did last
week"), filter by `actor_user_id` and `created_at`. The `(actor_user_id)`
and `(subject_user_id, created_at)` indexes cover both shapes.

`ActionLog.field_changes` is a JSON object. For updates: `{field: [before,
after]}`. For deletes: `{"_action": "delete", "snapshot": {column: value, ...}}`.
For creates: `{field: [None, value]}` per column. Sensitive User columns
(`hashed_password`, `email_confirmation_code`, `email`) are stored as
`"<redacted>"` instead of the raw value — the audit log records that they
changed without retaining the values themselves.

## Request actor / reason context

`pack218.audit.current_actor` and `pack218.audit.current_reason` are
`contextvars` set by the request boundary in `pack218.app.chrome()`. Page
handlers and UI components do not need to read them directly. To temporarily
set a reason before a save (e.g., from a "reason" modal), use the standard
pattern:

```python
from pack218.audit import AuditError, current_reason

token = current_reason.set(reason_text)
try:
    instance.save(session=session)
except AuditError as e:
    ui.notify(str(e), color='negative')
finally:
    current_reason.reset(token)
```

The `finally` block is mandatory — without it, the reason can leak into
later saves in the same Python execution context (especially in tests and
scripts where there is no request boundary to scope the contextvar).

## Test data

Tests that touch the DB use the `db_session` fixture in `tests/conftest.py`
(in-memory SQLite, fresh per test). Tests that exercise on-behalf rules
should also use the `isolated_audit_context` fixture (also in
`tests/conftest.py`) to keep `current_actor` / `current_reason` from leaking
between tests.

## Origin documents

- Plan: `docs/plans/2026-05-11-001-feat-admin-on-behalf-and-audit-log-plan.md`
- Brainstorm: `docs/brainstorms/2026-05-11-admin-on-behalf-requirements.md`
- Ideation: `docs/ideation/2026-05-11-admin-impersonation-ideation.md`
