---
title: "feat: admin on-behalf-of edits + universal action log"
type: feat
status: completed
date: 2026-05-11
origin: docs/brainstorms/2026-05-11-admin-on-behalf-requirements.md
---

# feat: admin on-behalf-of edits + universal action log

## Summary

Add an append-only `ActionLog` table, hook it into `SQLModelWithSave.save()` and `.delete_by_id()` via request-scoped `contextvars`, build a new admin route for editing any user's `EventRegistration` with a required reason, wrap the existing `/admin/users` and `/admin/families` `NiceCRUDWithSQL` pages to enforce the same reason prompt + blocklist + admin-on-admin rule, and surface admin-on-behalf changes back to the affected parent on their profile and registration pages — all in one PR.

---

## Problem Frame

Pack 218's admins regularly need to update a parent's record on their behalf (last-minute camping trip drops, meal switches from a text, phone-number corrections), but the existing admin paths produce silent unattributed writes and the canonical `EventRegistration` case has no admin UI at all (see origin: `docs/brainstorms/2026-05-11-admin-on-behalf-requirements.md` Problem Frame for the full pain narrative).

---

## Requirements

- R1. Append-only `ActionLog` table with `actor_user_id`, `subject_user_id`, `entity_name`, `entity_id`, `action`, `field_changes` (JSON), `created_at`, nullable `reason`.
- R2. Every `SQLModelWithSave.save()` and `.delete_by_id()` insert exactly one `ActionLog` row in the same transaction. Self-edits (`actor == subject`) get `reason = NULL` and are logged but filtered from parent panel.
- R3. New admin entry point for editing any user's `EventRegistration`.
- R4. Admin can edit a permitted subset of fields on any other user's `User` profile through `/admin/users`: `first_name`, `last_name`, `phone_number`, `family_member_type`, `has_food_allergies`, `food_allergies_detail`, `has_food_intolerances`, `food_intolerances`.
- R5. Required free-text reason when `actor ≠ subject`; empty reason rejects save.
- R6. Blocklist for on-behalf edits: `email`, `username`, `hashed_password`, `is_admin`, `can_login`, `email_confirmed`, `email_confirmation_code`. Enforced both in UI (hidden/disabled) and at save() (rejected).
- R7. Admin cannot use on-behalf flow against another admin's record.
- R8. Parent-visible panel on profile and event-registration pages listing `ActionLog` entries where `subject_user_id = current_user.id` (or Family-scoped) and `actor_user_id ≠ current_user.id`.
- R9. Parent panel ships in the same PR.
- R10. One new Alembic migration adds `action_log` table.
- R11. Reason prompt is shared between the new EventRegistration admin route and the `NiceCRUDWithSQL` admin wrappers.

**Origin actors:** A1 Admin, A2 Parent (subject), A3 System (save hook).
**Origin flows:** F1 Admin edits EventRegistration on-behalf, F2 Admin edits User profile on-behalf, F3 Parent views on-behalf changes, F4 Admin attempts blocked-field edit.
**Origin acceptance examples:** AE1 (covers R2/R5), AE2 (covers R2 self-edit), AE3 (covers R6 blocklist), AE4 (covers R7 admin-on-admin), AE5 (covers R8 panel).

---

## Scope Boundaries

- No session-swap / impersonation mode — admins always remain themselves in their own session.
- No bulk operations, CSV import, or batch waitlist promotion in this plan (they will use the same audit substrate when added).
- No "view as parent" read-only debugging affordance.
- No `@side_effect(suppress_when_on_behalf=True)` decorator — defer to the first non-email side-effect.
- No multi-admin race protection (last-write-wins is acceptable at single-admin reality).
- No reason picklist / category curation.
- No backfill of pre-existing writes into `ActionLog`.
- No co-parent invite, magic-link self-service, or `Delegation` standing-proxy table.
- No standalone "Phone Intake" page — entry points reuse the existing admin pages plus the one new event-roster route.

### Deferred to Follow-Up Work

- Side-effect suppression decorator: separate PR when waitlist-promotion emails or any non-email side-effect is added.
- Co-parent invite (origin S4), magic-link self-service (origin S5), `Delegation` standing proxy (origin S7): independent brainstorms/plans.

---

## Context & Research

### Relevant Code and Patterns

- `pack218/entities/__init__.py:14-33` — `SQLModelWithSave.save()` is the universal write path. `NiceCRUDWithSQL.update()` and `.create()` at lines 101–118 both call `item.save()`. Hook here to capture every write through one seam.
- `pack218/entities/__init__.py:66-75` — `SQLModelWithSave.delete_by_id()` is the universal delete path. `EventRegistration` deletion in `pack218/pages/event_registration.py:41` goes through it. Hook here for delete actions.
- `pack218/entities/models.py:232-413` — `User` model carries the blocklisted fields (`is_admin`, `hashed_password`, `username`, `email`, `can_login`, `email_confirmed`, `email_confirmation_code`) and the session resolver `User.get_current(request)` at line 402.
- `pack218/entities/models.py:24-117` — `EventRegistration` carries the on-behalf-editable fields (`stay_friday_night`, `stay_saturday_night`, `eat_*`, `has_paid`). `subject_user_id` derives from `self.user_id` here.
- `pack218/app.py:266-340` — existing `/admin/families`, `/admin/events`, `/admin/users` route shape using `NiceCRUDWithSQL`. New `/admin/events/{event_id}/registrations` route fits this shape.
- `pack218/pages/utils.py:24-30` — `assert_is_admin()` is the centralized admin gate; `SessionDep` is the DB session dependency.
- `pack218/pages/event_registration.py:24-121` — the user-facing event registration form pattern (per-family-member checkbox grid) that the new admin route mirrors at single-family scope.
- `alembic/versions/efdb27d61ada_add_capacity_to_event.py` — convention for an Alembic migration in this repo (`op.batch_alter_table`, `sqlalchemy as sa`, `sqlmodel.sql.sqltypes`).
- `tests/test_models.py` — current test convention: plain pytest fixtures, no DB session today. `tests/conftest.py` is essentially empty.

### Institutional Learnings

- None — `docs/solutions/` does not exist yet. The audit pattern from this plan is a candidate for a first entry after the work lands.

### External References

- Not used. The pattern (universal save-hook + actor/subject + reason) is established SQLAlchemy / SQLModel practice; the origin doc captured the relevant external grounding (RFC 8693 `act` claim, django-hijack, healthcare proxy, sudo `-u`).

---

## Key Technical Decisions

- **Request-scoped `contextvars` for actor and reason** (resolves origin "Affects R2 [Technical] actor resolution"). `pack218.audit.current_actor: ContextVar[Optional[int]]` and `current_reason: ContextVar[Optional[str]]` are set in the request boundary and read inside `SQLModelWithSave.save()`. This avoids touching every call site's signature and matches NiceGUI's per-request model. Test-time injection is one `ContextVar.set()` call per test.
- **Audit insert in the SAME transaction as the data write** (resolves origin "Affects R2 [Needs research] transaction boundary"). At pack scale, contention is non-issue; same-tx eliminates the orphan-log failure mode. Implementation hooks between `session.flush()` and `session.commit()` inside `save()`.
- **Subject derivation by entity type**: `User` → `self.id`; `EventRegistration` → `self.user_id`; `Family` → `subject_id = NULL`, `entity_name='Family'`, `entity_id=family.id`. Parent panel surfaces Family-scoped rows by joining the viewer's `family_id` with `ActionLog.entity_id` where `entity_name='Family'`. No write-time fan-out.
- **Diff capture via SQLAlchemy attribute history** — read `sqlalchemy.inspect(instance).attrs.<field>.history` between flush and commit; gives `(before, after)` per dirty field without a pre-read query. For create, `before` is `null`.
- **`field_changes` stored as a JSON column**, not a normalized per-field row. Pack scale makes the simpler shape strictly better.
- **New admin route `/admin/events/{event_id}/registrations`** (resolves origin "Affects R3 [Technical] admin entry point"). Cleaner separation than mingling admin-on-behalf into the user-facing `/event-registration/<id>` handler. Renders a family-grouped roster with an inline "Edit on behalf of …" affordance per row.
- **`OnBehalfNiceCRUD` subclass wraps the existing `NiceCRUDWithSQL`** (resolves R11). Intercepts `update()` to prompt for reason in a modal when `actor.id ≠ subject.id`, sets `current_reason`, then calls super. Field-hiding for the blocklist uses Pydantic's per-call `exclude` so the admin form simply does not render those fields when the target is not the current user.
- **Reason modal helper** (`pack218/pages/ui_components.request_reason_then(callback)`) — single reusable modal, used by both the new admin route and the `OnBehalfNiceCRUD` wrapper, so R11 ("one rule, one validation") is a code reuse fact.
- **Block-list approach for User fields** — explicit and short; new User fields default to editable unless added to the list. An allow-list would require touching this rule every time a User field is added.
- **Self-edits are also logged** — uniform substrate; the parent panel filters them out at read time.
- **No new dependencies** — SQLModel, SQLAlchemy, NiceGUI, Pydantic, Alembic, pytest are all already present.

---

## Open Questions

### Resolved During Planning

- *Actor resolution inside `save()`* (origin R2 Technical): use request-scoped `contextvars` set in the request chrome and read inside save.
- *Transaction boundary for audit insert* (origin R2 Needs research): same transaction as the data write.
- *Admin entry point for EventRegistration* (origin R3 Technical): new dedicated `/admin/events/{event_id}/registrations` route.
- *Reason prompt UX* (origin R5 Technical): modal-before-save via a shared helper, used by both new admin route and `OnBehalfNiceCRUD`.
- *Parent panel placement* (origin R8 Technical): top of profile page and inline above the user's own EventRegistration view, collapsible, last 30 days.

### Deferred to Implementation

- Exact `field_changes` JSON shape for `delete` actions — likely `{"_action": "delete", "snapshot": {…}}` capturing the full row at delete time, but the precise schema can be finalized when writing U3.
- Whether the audit hook needs to handle `pre_save()` validation failures specially. Likely fine: `pre_save` raises before flush, so no audit row is written — but verify in U3 tests.
- Whether `NiceCRUDWithSQL.create` needs a reason prompt for "create-on-behalf" (admin creates a new family member for someone else). MVP can require admin to set `family_id` to their own first or treat all admin creates as actor=admin/subject=admin until a clear use case emerges.

---

## Output Structure

```
pack218/
├── audit/                              # NEW
│   ├── __init__.py                     # NEW — exports current_actor, current_reason, record_change, AuditError
│   └── hooks.py                        # NEW — diff helpers, save/delete hook bodies
├── entities/
│   ├── __init__.py                     # MODIFY — wire save/delete into audit hooks
│   └── models.py                       # MODIFY — add ActionLog model
├── pages/
│   ├── admin_event_registration.py     # NEW — admin roster + edit-on-behalf form
│   ├── admin_overrides.py              # NEW — OnBehalfNiceCRUD subclass + blocklist
│   ├── ui_components.py                # MODIFY — add request_reason_then() modal helper
│   ├── profile.py                      # MODIFY — mount on-behalf-changes panel
│   ├── event_registration.py           # MODIFY — mount on-behalf-changes panel for this user's row
│   └── on_behalf_panel.py              # NEW — the parent-visible panel component
└── app.py                              # MODIFY — set current_actor in chrome(), add /admin/events/{id}/registrations route, switch /admin/users + /admin/families to OnBehalfNiceCRUD
alembic/versions/
└── <hash>_add_action_log.py            # NEW — migration creating action_log table
tests/
├── conftest.py                         # MODIFY — add in-memory SQLite session fixture, actor-context fixture
├── test_audit_log.py                   # NEW — model + hook unit tests
└── test_on_behalf.py                   # NEW — blocklist, admin-on-admin, reason-required, panel filter
AGENTS.md                                # NEW or MODIFY — write-path convention note
```

---

## Implementation Units

### U1. ActionLog model + Alembic migration

**Goal:** Add the append-only audit table and a thin model class.

**Requirements:** R1, R10.

**Dependencies:** None.

**Files:**
- Modify: `pack218/entities/models.py` (add `ActionLog` class)
- Create: `alembic/versions/<hash>_add_action_log.py` (autogenerated then reviewed)
- Test: `tests/test_audit_log.py` (new)
- Modify: `tests/conftest.py` (add `db_session` fixture using `sqlite:///:memory:`)

**Approach:**
- `ActionLog(SQLModelWithSave, table=True)` with fields: `id` (PK), `actor_user_id` (int, FK to `user.id`, nullable for system actions), `subject_user_id` (int, FK to `user.id`, nullable for Family-scoped writes), `entity_name` (str), `entity_id` (int), `action` (str enum-like: `"create" | "update" | "delete"`), `field_changes` (JSON column, SQLAlchemy `JSON` type), `reason` (str, nullable), `created_at` (datetime, default_factory `datetime.now`).
- Index on `(subject_user_id, created_at)` for the parent panel query; index on `(entity_name, entity_id)` for Family-scoped lookups.
- Generate migration via `alembic revision --autogenerate -m "add action log"` then manually verify the indexes and JSON column type follow the convention from `alembic/versions/efdb27d61ada_add_capacity_to_event.py`.
- Test fixture `db_session` in `conftest.py` uses `create_engine("sqlite:///:memory:")` and `SQLModel.metadata.create_all(engine)` per test.

**Patterns to follow:**
- Field shape and Alembic migration style: `pack218/entities/models.py:24-46` (`EventRegistration`) and `alembic/versions/efdb27d61ada_add_capacity_to_event.py`.

**Test scenarios:**
- Happy path: Construct an `ActionLog` with all fields populated, save through the in-memory session, query by `subject_user_id` and `actor_user_id`, assert both indexes return the row.
- Happy path: Construct an `ActionLog` with `subject_user_id=None` (Family-scoped), `entity_name='Family'`, `entity_id=42`; assert it persists and a join query returning rows for `entity_name='Family' AND entity_id=42` returns it.
- Edge case: `field_changes={}` (no diff) — row still inserts. Edge case: `reason=None` — row still inserts.
- Edge case: Migration apply + downgrade round-trip leaves no residual table (verify with `alembic upgrade head` then `alembic downgrade -1` in a tmp DB).

**Verification:**
- `pytest tests/test_audit_log.py` green.
- Migration applies cleanly against a fresh DB and round-trips down.

---

### U2. Audit module (contextvars, diff helpers, record() function)

**Goal:** Implement the request-scoped actor and reason primitives plus a `record_change(session, instance, action)` helper that captures the diff and inserts an `ActionLog` row.

**Requirements:** R2, R5 (substrate only — enforcement is U3).

**Dependencies:** U1.

**Files:**
- Create: `pack218/audit/__init__.py` — exports `current_actor`, `current_reason`, `record_change`, `AuditError`.
- Create: `pack218/audit/hooks.py` — diff helpers, `record_change` body.
- Test: `tests/test_audit_log.py` (extend)

**Approach:**
- `current_actor: ContextVar[Optional[int]] = ContextVar("current_actor", default=None)` holds the user id of whoever initiated the request.
- `current_reason: ContextVar[Optional[str]] = ContextVar("current_reason", default=None)` is set by the UI before calling `save()` when the admin is acting on behalf of someone else.
- `subject_for(instance)` returns `(entity_name, entity_id, subject_user_id)` keyed by class: `User` → `(self.id)`, `EventRegistration` → `(self.user_id)`, `Family` → `(None)`.
- `diff_for(instance, action)` uses `sqlalchemy.inspect(instance).attrs.<field>.history` to produce `{field: [before, after]}` between flush and commit. For `create`, `before` is null. For `delete`, capture a full snapshot via `instance.dict()` (or model_dump for Pydantic v2) under `{"_action": "delete", "snapshot": {…}}`.
- `record_change(session, instance, action)` composes the above, reads `current_actor` / `current_reason`, inserts a row via `session.add(ActionLog(...))`. Does NOT commit — caller (`save()` in U3) commits the surrounding transaction.

**Patterns to follow:**
- `pack218/entities/__init__.py:20-33` for the session-handling shape (caller may pass a session or it creates one).

**Test scenarios:**
- Happy path: `current_actor.set(1)`, build and persist a `User` with new fields, `record_change` produces `{first_name: [None, "Sarah"], …}` for create.
- Happy path: Load a User, change `phone_number`, call `record_change(action="update")`, diff is `{phone_number: ["555-old", "555-new"]}`.
- Happy path: `current_actor.set(None)` produces an `ActionLog` row with `actor_user_id=NULL` (system writes are allowed but discouraged; never raise here).
- Edge case: No dirty attributes on update → `field_changes={}` row still written (uniform substrate).
- Edge case: `EventRegistration` instance → subject_user_id resolves to `self.user_id`. `Family` instance → subject_user_id is NULL; entity_id resolved.
- Edge case: Delete action serializes a snapshot, not a diff.
- Integration: Two distinct test workers via `ContextVar.run()` see independent actor values (verifies no global leakage).

**Verification:**
- All test scenarios green.
- `record_change` does no I/O of its own beyond `session.add` (no flush, no commit).

---

### U3. Audit hooks in `SQLModelWithSave.save()` and `.delete_by_id()` + on-behalf authorization rules

**Goal:** Wire `record_change` into the universal write path, and enforce the on-behalf rules (required reason, blocklist, admin-on-admin block) at the save boundary so they cannot be bypassed by any UI path.

**Requirements:** R2, R5, R6, R7.

**Dependencies:** U2.

**Files:**
- Modify: `pack218/entities/__init__.py` (`SQLModelWithSave.save` and `SQLModelWithSave.delete_by_id`)
- Modify: `pack218/audit/__init__.py` (add `BLOCKLISTED_USER_FIELDS` constant, `enforce_on_behalf_rules` helper)
- Test: `tests/test_on_behalf.py` (new)

**Approach:**
- `save()` becomes: `self.pre_save(); session.add(self); session.flush(); enforce_on_behalf_rules(session, self, action); record_change(session, self, action); session.commit(); session.refresh(self)`. Two new lines, same control flow, same exception semantics.
- `delete_by_id()` becomes: load → `enforce_on_behalf_rules(session, instance, "delete")` → `record_change(session, instance, "delete")` → `session.delete(instance)` → `session.commit()`.
- `enforce_on_behalf_rules(session, instance, action)` reads `current_actor`. Compute `subject_user_id` via `audit.subject_for(instance)`. When `current_actor != subject_user_id` AND `subject_user_id is not None` (self-edit shortcut; Family writes count as on-behalf when actor isn't a family member, see below):
  1. Reason check: `current_reason.get()` must be non-empty; else raise `AuditError("Reason is required when editing another user's record")` (covers AE1).
  2. Blocklist check: if `instance` is a `User`, compute the dirty fields from `inspect(instance).attrs`; if any dirty field name is in `BLOCKLISTED_USER_FIELDS` (`{"email", "username", "hashed_password", "is_admin", "can_login", "email_confirmed", "email_confirmation_code"}`), raise `AuditError("These fields can only be changed by the user themselves: …")` (covers AE3).
  3. Admin-on-admin check: if `instance` is a `User` and `instance.is_admin is True` and current_actor's `is_admin is True`, raise `AuditError("On-behalf-of edits cannot target another admin's record")` (covers AE4).
- For Family writes: `subject_user_id` is None, but on-behalf still applies when `current_actor` is not a member of `instance` (looked up via `User.family_id` for actor). When actor is a family member, treat as self-edit. When actor is not, require reason. Blocklist for Family: empty for MVP (all Family fields are editable).
- `AuditError` extends `Exception`; UI catches it via the existing notify-on-error pattern.

**Execution note:** Test-first for the enforcement rules — write the failing on-behalf and blocklist tests in `tests/test_on_behalf.py` before modifying `save()` and `delete_by_id()`. The hook changes are simple enough that risk is concentrated in the rule logic, where each AE maps to a test.

**Patterns to follow:**
- The existing `save()` already wraps `make_the_save()` in a `with Session(engine) as session` block; preserve that exactly.

**Test scenarios:**
- **Covers AE1.** Happy path: `current_actor.set(admin_id); current_reason.set("Sarah texted")` then mutate Sarah's EventRegistration and `.save()` → succeeds; `ActionLog` row has `actor=admin, subject=sarah, reason="Sarah texted"`.
- **Covers AE1.** Error path: same setup but `current_reason.set(None)` → `AuditError` raised; assert no `ActionLog` row exists for that subject post-rollback.
- **Covers AE1.** Error path: `current_reason.set("")` (empty string) → `AuditError` raised; same assertion.
- **Covers AE2.** Happy path: `current_actor.set(sarah_id); current_reason.set(None)`, Sarah edits her own profile, `.save()` succeeds, `ActionLog` row has `actor=sarah, subject=sarah, reason=NULL`.
- **Covers AE3.** Error path: admin tries to dirty `Sarah.email` with reason set; `AuditError` raised; assert `Sarah.email` in DB is unchanged.
- **Covers AE3.** Error path: admin tries to dirty `Sarah.is_admin` with reason set; `AuditError`.
- **Covers AE4.** Error path: admin Dave tries to edit admin Lisa's profile with reason set → `AuditError`.
- Happy path: admin edits a Family the admin is not a member of, with reason → succeeds; `ActionLog` row has `subject_user_id=NULL, entity='Family', entity_id=family.id`.
- Edge case: admin edits their OWN family (same `family_id`) with no reason → succeeds as self-edit.
- Edge case: `delete_by_id` for someone else's EventRegistration with reason set → succeeds; `ActionLog` action='delete', snapshot present.
- Edge case: `delete_by_id` with no reason while `current_actor != subject` → `AuditError`.
- Integration: Use the in-memory session fixture and exercise the full `save()` path; confirm flush+enforce+record+commit ordering by introspecting `inspect()` history during the hook (not just before save).

**Verification:**
- All test scenarios green.
- `assert_is_admin` paths in `pack218/app.py` are not touched — admin gating still happens per page; this unit adds an additional, save-boundary safety net.

---

### U4. Admin route: `/admin/events/{event_id}/registrations` + edit-on-behalf form

**Goal:** Build the new admin entry point for editing any user's `EventRegistration`. Roster view with family grouping; inline edit affordance opens a modal pre-filled with current values + required reason field.

**Requirements:** R3, R5, R7, R11.

**Dependencies:** U3 (so the save path enforces rules even if the UI is misused).

**Files:**
- Create: `pack218/pages/admin_event_registration.py`
- Modify: `pack218/app.py` (register the new route)
- Modify: `pack218/pages/ui_components.py` (add `request_reason_then(on_confirm)` shared modal helper)
- Test: `tests/test_on_behalf.py` (extend)

**Approach:**
- Route signature: `@ui.page('/admin/events/{event_id}/registrations') def admin_event_registrations_page(request: Request, session: SessionDep, event_id: int)`.
- Calls `assert_is_admin(request, session)` first.
- Renders the event's roster grouped by `Family`, mirroring the visual shape of `pack218/pages/event_registration.py:78-117` but read-only by default. Each row has an "Edit on behalf of …" button.
- Clicking the button opens a modal with the same checkbox grid (`stay_*`, `eat_*`, `has_paid`) pre-filled from the current `EventRegistration`, plus a required `Reason` text input below the grid.
- Modal "Save" button:
  1. Validates reason is non-empty (inline error if not — matches R5 origin AE1 first half).
  2. Sets `current_reason.set(reason_value)` via a `with` block (use `contextvars.copy_context()` to ensure the value is bound for the duration of the save).
  3. Sets the new field values on the `EventRegistration` instance.
  4. Calls `event_registration.save(session=session)` — the audit hook records actor=current admin, subject=row's user, reason=typed text.
  5. On `AuditError` from U3, displays the error via `ui.notify(color='negative')` without closing the modal.
  6. On success, closes the modal and refreshes the roster.
- A "Drop registration" affordance calls `EventRegistration.delete_by_id` after the same reason modal flow.
- `request_reason_then(on_confirm)` is the shared modal helper: opens a small dialog with a single textarea, validates non-empty, then calls `on_confirm(reason)`. Used by U5 too.
- Admin-on-admin gating: filter out admin users from the roster display (`User.is_admin == True` rows are still shown for completeness but the Edit button is hidden); the audit hook (U3) is the backstop if the UI is bypassed.

**Patterns to follow:**
- `pack218/app.py:266-282` for the admin page route shape with `assert_is_admin` and `chrome()`.
- `pack218/pages/event_registration.py:62-121` for the checkbox grid UI.
- `pack218/pages/profile.py:67-110` for the modal dialog shape (`simple_dialog`, `BUTTON_CLASSES_ACCEPT`/`CANCEL`).

**Test scenarios:**
- **Covers F1 / AE1.** Happy path: admin loads `/admin/events/1/registrations`, opens edit modal for Sarah's row, sets `eat_saturday_breakfast=False`, types reason "Sarah texted", clicks save → DB shows updated registration AND `ActionLog` row with full diff and reason. *(Test the underlying handler function, not the NiceGUI rendering loop — see Integration note in U3.)*
- Happy path: admin drops Sarah's registration via the same flow with reason "Family pulled out".
- Error path: admin opens modal, leaves reason blank, clicks save → inline error message; no DB change; modal stays open.
- Error path: admin attempts to edit another admin's row via constructed payload (skip the disabled button) → `AuditError` from U3; UI shows the error.
- Edge case: non-admin user requesting `/admin/events/1/registrations` → 403 (existing `assert_is_admin` behavior).
- Edge case: event has zero registrations → empty roster state; no buttons.

**Verification:**
- Manual: as admin, drop a test parent's registration and verify it appears in `ActionLog` and on the parent's profile panel after U6.
- Automated: handler-level tests green.

---

### U5. `OnBehalfNiceCRUD` subclass + admin pages migration

**Goal:** Wrap the existing `NiceCRUDWithSQL` so `/admin/users` and `/admin/families` enforce the reason prompt, hide blocklisted fields, and let the audit hook do its job. R4 (User profile editable fields) is enforced here primarily via field-hiding.

**Requirements:** R4, R5, R6, R7, R11.

**Dependencies:** U3, U4 (reuses `request_reason_then` from U4).

**Files:**
- Create: `pack218/pages/admin_overrides.py` (`OnBehalfNiceCRUD` class)
- Modify: `pack218/app.py` (swap `NiceCRUDWithSQL(basemodeltype=User, …)` → `OnBehalfNiceCRUD(basemodeltype=User, …)` at lines 273, 282, 340 — re-evaluate exact lines on the implementation pass)
- Test: `tests/test_on_behalf.py` (extend)

**Approach:**
- `OnBehalfNiceCRUD(NiceCRUDWithSQL)` overrides `async def update(self, item)`:
  1. Resolve current actor from `current_actor.get()`.
  2. If `item` is a `User` and `item.id != current_actor`, configure NiceCRUDConfig to exclude `BLOCKLISTED_USER_FIELDS` from the rendered form fields before super's update logic runs.
  3. If subject ≠ actor, call `request_reason_then(lambda reason: super().update(item))`. Set `current_reason.set(reason)` inside the callback before calling super.
  4. If actor == subject, call super directly — no reason needed.
- `OnBehalfNiceCRUD.create()` requires admin to be in the same Family as `item.family_id` for User creates (matches today's profile flow); otherwise treats as on-behalf-create and prompts for reason.
- Blocklist field-hiding uses NiceCRUDConfig's `additional_exclude` parameter; the field is removed from the form before render, so the admin literally cannot edit it. The U3 save-boundary check is the backstop.
- Admin-on-admin: if `item.is_admin is True` and `item.id != current_actor`, the update button is disabled and a tooltip explains why. U3 is the backstop.

**Execution note:** Test-first for the wrapper's update flow — write a failing test that calls `OnBehalfNiceCRUD.update()` with a blocked-field diff before implementing the override.

**Patterns to follow:**
- `pack218/entities/__init__.py:78-121` for the NiceCRUDWithSQL shape.
- `pack218/app.py:273, 282, 340` for the call sites to swap.

**Test scenarios:**
- **Covers F2 / AE1.** Happy path: admin opens `/admin/users`, edits Sarah's `phone_number`, modal prompts for reason, admin types reason, save → DB updated + ActionLog row.
- **Covers AE3.** Error path: admin opens `/admin/users` editing Sarah → `email` field is not present in the rendered form (exclude list). If a crafted PUT smuggles `email`, U3 rejects with `AuditError`.
- **Covers AE4.** Error path: admin opens `/admin/users` to edit admin Lisa → update button disabled or tooltip shown; bypass attempt rejected by U3.
- Happy path: admin edits their OWN profile through `/admin/users` → no reason modal, all User fields editable.
- Happy path: admin edits another family's `Family.emergency_contact_phone_number_1` via `/admin/families` → reason modal prompts; save records `ActionLog` with `entity='Family'`.
- Edge case: admin edits their own family → no reason modal.

**Verification:**
- Automated: handler-level tests green.
- Manual: as admin, edit another parent's phone and confirm the reason modal appears, then verify the ActionLog row.

---

### U6. Parent-visible "Changes made on my behalf" panel + AGENTS.md convention

**Goal:** Render a collapsible panel on the parent's profile page and on their own `event-registration/<id>` view, listing `ActionLog` entries where `actor ≠ subject` and the subject is the current user (or `entity='Family' AND entity_id = current_user.family_id`). Add a one-paragraph convention note to AGENTS.md.

**Requirements:** R8, R9.

**Dependencies:** U1 (data), U3 (rows actually written).

**Files:**
- Create: `pack218/pages/on_behalf_panel.py` (`render_on_behalf_panel(user, entity_name=None, entity_id=None)`)
- Modify: `pack218/pages/profile.py` (mount panel at top of profile view, no entity filter — shows everything on-behalf for this user)
- Modify: `pack218/pages/event_registration.py` (mount panel scoped to `entity='EventRegistration', entity_id=this_registration.id`)
- Create or modify: `AGENTS.md` — short convention note: "All persistent writes go through `SQLModelWithSave.save()` and `.delete_by_id()` so the audit log captures them. Raw `session.add(); session.commit()` bypasses the log and is disallowed without an explicit exemption comment."
- Test: `tests/test_on_behalf.py` (extend)

**Approach:**
- `render_on_behalf_panel(user, entity_name=None, entity_id=None)` queries `ActionLog` with:
  - `subject_user_id == user.id AND actor_user_id != user.id`, OR
  - `entity_name == 'Family' AND entity_id == user.family_id AND actor_user_id != user.id`
- When `entity_name` and `entity_id` are passed, additionally filter `(ActionLog.entity_name == entity_name AND ActionLog.entity_id == entity_id)` — the event-registration page wants only that registration's changes.
- Order by `created_at DESC`, limit to last 30 days OR last 20 rows (whichever is larger), default-collapsed if more than 3 entries.
- Each entry renders: admin display name (`actor.first_name actor.last_name`), date, a human-readable summary of fields changed (e.g., "changed Saturday breakfast (yes → no), overnight Saturday (yes → no)"), and the `reason` in quotes.
- For `entity='Family'` rows, label as "changed family info" with field names.
- For `action='delete'` rows on EventRegistration, label as "removed your registration".

**Patterns to follow:**
- `pack218/pages/profile.py:147-261` for the `@ui.refreshable` page structure and `card()` / `card_title()` shape.
- `pack218/pages/event_registration.py:24-69` for the section structure.

**Test scenarios:**
- **Covers AE5.** Happy path: setup — admin edited Sarah's `eat_saturday_breakfast` yesterday with reason "Phone call 7pm". Sarah loads her profile → panel renders one entry with admin name, yesterday's date, "changed Saturday breakfast (yes → no)", and the reason in quotes.
- Edge case: Sarah has zero on-behalf changes → panel renders an empty state ("No changes have been made on your behalf.") OR is hidden (pick one in implementation; test expectation matches).
- Edge case: Sarah has a self-edit yesterday → panel does NOT show it (filter `actor_user_id != user.id`).
- Edge case: Admin edited Sarah's `Family.emergency_contact_phone_number_1` — Sarah AND every other member of Sarah's family see it on their own profile panels.
- Edge case: Panel on `/event-registration/<id>` only shows entries scoped to that specific registration's id.
- Edge case: A registration that was deleted on-behalf yesterday — the parent visiting `/event-registration/<id>` sees a "removed your registration" row (the registration page should still render this even though the EventRegistration row no longer exists; handler must tolerate missing row by reading from ActionLog directly).

**Verification:**
- Automated: query-layer tests green; render-layer tests covered by handler-level invocation (skip pixel-level NiceGUI assertions).
- Manual: as a non-admin parent, log in after an admin-on-behalf edit and confirm the panel shows the expected entry.

---

## System-Wide Impact

- **Interaction graph:** Every `.save()` call site now also touches `ActionLog`. Audit lives downstream of every page's mutation path. `chrome()` in `pack218/app.py` becomes the actor-context entry point.
- **Error propagation:** New `AuditError` exception class. Existing `try/except` blocks in `pack218/pages/profile.py:62-63` and elsewhere catch generic `Exception` and `ui.notify` — they will handle `AuditError` naturally. New admin and override pages need explicit handling.
- **State lifecycle risks:** Audit insert in same transaction means a failed audit insert rolls back the data write. This is the desired semantic (no orphan log rows; no silent unaudited writes). Worth a one-line note in AGENTS.md.
- **API surface parity:** No external APIs. Internal API: every model save behavior gains a side-effect (one `ActionLog` row). Existing tests that count rows or compare DB state must be aware.
- **Integration coverage:** Cross-layer scenarios in U3 and U4 exercise the full save path with the in-memory session fixture.
- **Unchanged invariants:** `assert_is_admin()` still gates admin pages. `User.get_current()` and the Google-OAuth-style session resolution unchanged. The existing user-facing `/event-registration/<id>` route is unchanged.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Code path that bypasses `SQLModelWithSave.save()` silently bypasses audit | AGENTS.md convention in U6; grep for `session.add` + `session.commit` outside `SQLModelWithSave` during U3 implementation; flag any callers with a one-line comment |
| `ContextVar` not propagated across async boundaries (NiceGUI's task scheduler) | Use `contextvars.copy_context()` at the request boundary; verify in U3 tests that a save invoked from a NiceGUI button callback sees the actor that was set in `chrome()` |
| SQLAlchemy `inspect().attrs.history` returns empty for attributes not loaded into the session | The save() flow always has the instance loaded (it's the one being saved); document this assumption in `audit/hooks.py`. For deletes, the snapshot uses `instance.dict()` which doesn't depend on history. |
| Same-transaction audit insert causes a deadlock or long-running tx | At pack scale (<50 families, sequential admin actions), contention is negligible. If it ever surfaces, switch to deferred insert via `after_commit` event with the row buffered in session state. Documented in `Open Questions → Deferred to Implementation`. |
| The `OnBehalfNiceCRUD` field-hiding via `additional_exclude` may not be a supported public API on NiceCRUDConfig | Verify by reading the `niceguicrud` source at implementation time; fall back to a thin custom form if `additional_exclude` doesn't behave as needed. |
| Parent panel showing 18 months of stale changes is noisy | Limit to 30-day window or last 20 rows by default; explicit collapse toggle. Implementation detail in U6. |

---

## Documentation / Operational Notes

- AGENTS.md gets a short "audit log convention" paragraph (U6 covers).
- README.md update is optional — the admin-on-behalf workflow is a feature, not a setup change.
- Migration is additive and reversible; deploy is a straight `alembic upgrade head`. Backups (per `scripts/`) should be taken before deploy as standard practice.
- After this lands, seed `docs/solutions/architecture-patterns/admin-on-behalf-audit-log.md` to capture the design decisions (per origin doc's institutional-knowledge note).

---

## Sources & References

- **Origin document:** `docs/brainstorms/2026-05-11-admin-on-behalf-requirements.md`
- **Ideation:** `docs/ideation/2026-05-11-admin-impersonation-ideation.md` (S1 + S2 starter pair)
- Universal write path: `pack218/entities/__init__.py:14-33`
- Existing admin pages: `pack218/app.py:266-340`
- Centralized admin gate: `pack218/pages/utils.py:24-30`
- User-facing event registration form (visual reference for U4): `pack218/pages/event_registration.py:24-121`
- Profile page (mount point for U6): `pack218/pages/profile.py:147-261`
- Test convention: `tests/test_models.py`
