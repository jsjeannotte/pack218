---
date: 2026-05-11
topic: admin-on-behalf
---

# Admin "On-Behalf-Of" Edits + Universal Action Log

## Summary

Add a primitive that lets an admin update another user's `EventRegistration` or profile basics on their behalf — without session-swap impersonation — while a new `ActionLog` table captures every model write with `actor`, `subject`, before/after values, timestamp, and (when `actor ≠ subject`) a required reason. The same log powers a parent-visible panel showing changes made on the parent's behalf, shipping in the same PR.

---

## Problem Frame

Pack 218's admins (the Cubmaster and a small number of committee members) regularly need to update a parent's record on their behalf: dropping a kid from a camping trip the day before, switching a meal selection from a text message, fixing a phone number after a parent calls. Today the only ways to do this are (1) admin CRUD pages that let an admin edit any user or family record but record no actor information — the change shows up as if the parent did it themselves — or (2) direct SQLite edits for `EventRegistration`, which is not in the admin CRUD UI. Both paths produce silent, unattributed mutations. There is no audit trail of any kind (`pack218/entities/__init__.py:14`), so if a change is disputed ("I didn't pick vegetarian"), there is no way to know who, when, or why. The first time a kid arrives at camp expecting one meal and gets another because of a misheard phone call, the volunteer-trust culture that the app relies on takes a real hit.

---

## Actors

- A1. **Admin**: a `User.is_admin = True` user (Cubmaster, committee member). Acts in their own session at all times — never session-swaps to another user.
- A2. **Parent (subject)**: a `User.is_admin = False` user whose `EventRegistration` or profile is being modified by the admin on their behalf. Sees the changes on their own view of the affected records.
- A3. **System**: the `SQLModelWithSave.save()` hook that records every write to `ActionLog`, plus the read path that surfaces on-behalf-of changes to the parent.

---

## Key Flows

- F1. **Admin edits an EventRegistration on behalf of a parent**
  - **Trigger:** A1 is looking at an event roster and sees a row for A2 that needs a change (e.g., "Sarah called, dropping Saturday breakfast").
  - **Actors:** A1, A2 (passive), A3.
  - **Steps:**
    1. A1 navigates to the event's admin roster view, clicks an edit affordance on A2's row.
    2. A form opens pre-loaded with A2's current EventRegistration values.
    3. A1 changes the relevant fields.
    4. Because `actor (A1.id) ≠ subject (A2.id)`, the save prompts for a required reason ("Sarah texted at 7pm").
    5. On submit, the record is updated AND a row is inserted into `ActionLog` with both ids, the diff, the timestamp, and the reason.
  - **Outcome:** A2's registration reflects the change; A2's profile/event-registration view now shows a parent-visible entry: "On-behalf-of: Cubmaster Dave changed your Saturday breakfast on May 11 (reason: 'Sarah texted at 7pm')."
  - **Covered by:** R1, R2, R3, R5, R7, R9.

- F2. **Admin edits a User profile basic on behalf of a parent**
  - **Trigger:** A1 is in the existing `/admin/users` NiceCRUD page and updates A2's phone number, allergies, or food prefs.
  - **Actors:** A1, A2 (passive), A3.
  - **Steps:**
    1. A1 opens A2's row in the existing admin user CRUD.
    2. A1 edits a permitted field.
    3. On save, the reason prompt fires (because `actor ≠ subject`).
    4. The save and the `ActionLog` insert happen atomically.
  - **Outcome:** Same as F1, surfaced on A2's profile page.
  - **Covered by:** R1, R2, R4, R5, R7, R9.

- F3. **Parent views on-behalf-of changes**
  - **Trigger:** A2 logs in and visits their profile or any of their event-registration views.
  - **Actors:** A2, A3.
  - **Steps:**
    1. The page queries `ActionLog` for rows where `subject_id = A2.id AND actor_id ≠ A2.id`, scoped to the entity being viewed (profile or this event's registration).
    2. A panel renders the recent entries with admin name, date, fields changed, and reason.
  - **Outcome:** A2 can see every change made on their behalf without consulting an admin.
  - **Covered by:** R8, R9.

- F4. **Admin attempts a blocked-field edit**
  - **Trigger:** A1 tries to change A2's email, username, password, `is_admin`, `can_login`, or `email_confirmed` flag from any admin flow.
  - **Actors:** A1, A3.
  - **Steps:**
    1. The form either hides the field or rejects the save with a clear message ("This field can only be changed by the user themselves").
    2. No `ActionLog` row is written for the blocked write.
  - **Outcome:** Blocked fields remain authoritative to the parent.
  - **Covered by:** R6.

---

## Requirements

**Action log substrate**
- R1. Introduce a new append-only `ActionLog` table with: `id`, `actor_user_id`, `subject_user_id`, `entity_name`, `entity_id`, `action` (create / update / delete), `field_changes` (JSON of `{field: [before, after]}`), `created_at` timestamp, and `reason` (nullable text).
- R2. Every save through `SQLModelWithSave.save()` (and therefore every save through `NiceCRUDWithSQL.create` / `.update`) inserts exactly one corresponding `ActionLog` row before the surrounding transaction commits. Self-edits (`actor == subject`) are also logged, with `reason = NULL`; they exist so the substrate is uniform and so future general activity views are possible — they are not shown in the parent-visible panel.

**On-behalf-of editing primitive**
- R3. Admins can edit any other user's `EventRegistration` from a new admin entry point on the event roster. The form is pre-populated with the current values and writes back through the same `EventRegistration.save()` path used today.
- R4. Admins can edit a permitted set of fields on any other user's `User` profile through the existing `/admin/users` admin CRUD page: `first_name`, `last_name`, `phone_number`, `family_member_type`, `has_food_allergies`, `food_allergies_detail`, `has_food_intolerances`, `food_intolerances`.
- R5. When `actor_user_id ≠ subject_user_id` for any write, the UI prompts for a required free-text reason before the save commits. An empty reason rejects the save with an inline validation error.
- R6. The following User fields are blocklisted from on-behalf-of edits regardless of admin status: `email`, `username`, `hashed_password`, `is_admin`, `can_login`, `email_confirmed`, `email_confirmation_code`. The blocklist is enforced both in the UI (fields disabled or hidden when admin is editing someone else's record) and in the save path (rejection if a blocked field appears in the diff with `actor ≠ subject`).
- R7. Admins cannot use the on-behalf-of flow against another admin's record (`subject_user_id` resolves to a user where `is_admin = True`). The entry point is hidden and the save path rejects such attempts.

**Parent-visible transparency**
- R8. On every page where a parent views their own profile or one of their own `EventRegistration`s, a panel lists `ActionLog` entries where `subject_user_id = current_user.id` and `actor_user_id ≠ current_user.id`, scoped to the entity in view. Each entry shows the admin's display name, the date, a human-readable description of fields changed, and the reason.
- R9. The parent-visible panel ships in the same pull request as R1–R7. It is not a follow-up.

**Migration and surface area**
- R10. One new Alembic migration adds the `action_log` table. No changes to existing tables are required.
- R11. The reason-prompt mechanism is shared between the new EventRegistration admin entry point (R3) and the existing `/admin/users` and `/admin/families` NiceCRUD admin pages. Implementations may differ in form (modal vs inline) but the validation rule is one rule.

---

## Acceptance Examples

- AE1. **Covers R2, R5.** Given Cubmaster Dave is signed in and updates Sarah Chen's `EventRegistration` for the Spring Camporee to set `eat_saturday_breakfast = False`, when he submits the form without a reason, the save is rejected with "Reason is required when editing another user's record"; when he types "Sarah texted, dropping breakfast" and submits, the registration is updated and one `ActionLog` row is written with `actor=Dave, subject=Sarah, entity=EventRegistration, field_changes={eat_saturday_breakfast: [True, False]}, reason="Sarah texted, dropping breakfast"`.
- AE2. **Covers R2.** Given Sarah Chen is signed in and updates her own `food_intolerances` on her profile, when she saves, the update succeeds without a reason prompt and one `ActionLog` row is written with `actor=Sarah, subject=Sarah, reason=NULL`.
- AE3. **Covers R6.** Given an admin opens Sarah Chen's row in `/admin/users`, when the admin tries to change `Sarah.email` or `Sarah.is_admin`, the fields are disabled (or hidden) and any attempt to submit a payload that includes them is rejected with "These fields can only be changed by the user themselves"; no `ActionLog` row is written.
- AE4. **Covers R7.** Given there are two admins, Dave and Lisa, when Dave attempts to open the on-behalf-of edit affordance for Lisa's EventRegistration, the affordance is not visible; if he constructs the request directly it is rejected with "On-behalf-of edits cannot target another admin's record."
- AE5. **Covers R8.** Given Sarah Chen's `EventRegistration` was edited yesterday by Cubmaster Dave with reason "Phone call 7pm", when Sarah next visits that event's registration page, she sees a panel reading "Cubmaster Dave changed your Saturday breakfast and overnight on May 10 (reason: 'Phone call 7pm')."

---

## Success Criteria

- A Cubmaster handling a Friday-night last-minute change for a parent who can't log in can complete the action — including typing the reason — in well under a minute, without leaving the existing admin UI mental model.
- After this ships, every mutation in the application carries a verifiable answer to "who did this and when?", including normal self-edits.
- A parent visiting the app the next day after an admin-on-behalf edit can see what was changed, by whom, and why, on the same page where the affected data lives — without asking an admin.
- The data model gives the next adjacent feature (co-parent invite, magic-link self-service, standing proxy, password reset audit, future role tables) the audit substrate it needs without further schema changes.

---

## Scope Boundaries

- **No session-swap / impersonation mode.** Admins never act under another user's session. The grounding work explicitly rejected this and the design here makes it structurally impossible to forget which identity is acting.
- **No bulk operations.** One-at-a-time edits only. CSV import and bulk waitlist promotion are real future features but out of scope here; when they ship, they will use the same `ActionLog` substrate with the importing admin as `actor` and the affected user as `subject`.
- **No "view as parent" read-only debugging affordance.** Useful but a different feature; separate brainstorm.
- **No side-effect suppression decorator.** The MVP's blocklist and the fact that we are not touching email/login fields means no surprise emails are triggered by an on-behalf-of edit. Revisit when the first non-email side-effect (Stripe receipt, waitlist promotion email, SMS reminder) is added; a `suppress_when_on_behalf` decorator should land at the same time.
- **No multi-admin race protection.** At single-admin reality today, last-write-wins is acceptable. Revisit if a second admin joins and concurrent-edit incidents emerge.
- **No reason picklist or category curation.** Free text only. Categorization, reporting, or analytics over reasons are out of scope.
- **No backfill of historical writes into `ActionLog`.** The log starts empty at migration time and accumulates from the first write forward. Pre-existing data is not retroactively attributed.
- **No co-parent invite, no magic-link self-service, no `Delegation` standing proxy.** Each is a complement, not a blocker — tracked separately in the ideation document (ideas S4, S5, S7).
- **No standalone "Phone Intake" page.** The admin entry points reuse the existing event roster view and the existing `/admin/users` and `/admin/families` CRUD pages. A standalone phone-intake screen is a future polish if it earns its keep.

---

## Key Decisions

- **Scoped-action over session swap.** Admin stays signed in as themselves throughout. The five independent ideation frames that converged on this were reinforced by the documented failure modes of session swap (Facebook 2018 "View As" side-effect leak, Salesforce/Varonis undetectable admin actions, Pigment "forgot I was impersonating" class of bugs). At pack scale this is also the cheapest path.
- **Hook the audit log at `SQLModelWithSave.save()`, not at the per-page or per-route layer.** The base class is the only universal write path (`pack218/entities/__init__.py:20`); `NiceCRUDWithSQL.update` and `.create` both call `item.save()` (`pack218/entities/__init__.py:101-118`). One hook captures everything; per-page hooks would miss any future write path.
- **`field_changes` stored as a JSON column, not a normalized per-field row.** Pack scale (<50 families, dozens of writes/month) makes the simpler shape strictly better; querying for "what changed" is a `JSON_EXTRACT` away if it ever matters.
- **Required free-text reason, no picklist.** Picklist curation has nonzero ongoing cost and the volunteer reasons are inherently messy ("Sarah texted at 7pm because the kid is sick"). Free text captures intent in the user's own words. If reporting needs categories later, we can mine the text or add a picklist then.
- **Block-list approach to dangerous fields, not allow-list per record type.** Block-list is explicit and short; new fields default to editable unless flagged. An allow-list would require adding every new safe field forever.
- **Self-edits also produce `ActionLog` rows (with `reason = NULL`).** Costs nothing extra at this scale and gives us a uniform substrate for general activity log views in the future. The parent-visible panel filters them out.
- **Admin-on-admin blocked.** Matches the universal industry pattern (ZITADEL, RFC 8693 nuances, Salesforce). No legitimate use case in a volunteer pack.
- **Parent-visible panel ships in the same PR.** Trust signal must land at the same moment as the new admin power.

---

## Dependencies / Assumptions

- The existing `SQLModelWithSave.save()` flow at `pack218/entities/__init__.py:14-33` is the universal write path; verified during the brainstorm. `NiceCRUDWithSQL.update` and `.create` both delegate to it. Any future code that bypasses this base class (e.g., a raw SQLAlchemy session.add followed by commit) will silently bypass the audit log and is therefore disallowed by convention. A short note in `AGENTS.md` (or `CLAUDE.md`) capturing this convention is a small cost worth paying as part of this PR.
- `User.email` is the login identity (`User.get_current` resolves the session via email lookup at `pack218/entities/models.py:402-406`). This is why `email` is in the blocklist alongside `hashed_password`/`username`. A future "let admin update a parent's email" feature would need an explicit email-verification flow and is out of scope.
- Alembic is the migration tool of record (`alembic/versions/`); one new migration adds the table.
- Admin identity in the session is via `User.get_current(request)` → `request.session["user"]["email"]` → DB lookup. The action log records `actor_user_id` from `User.get_current()` at save time; no new session machinery needed.

---

## Outstanding Questions

### Resolve Before Planning

(None — all product decisions resolved during brainstorm.)

### Deferred to Planning

- [Affects R3][Technical] Exact admin entry point for `EventRegistration` editing — most natural place is the existing event detail/roster view, but its current shape and whether to add a per-row inline form vs a modal vs a redirect to a new page is a planning decision.
- [Affects R5][Technical] Reason prompt UX — modal before save vs inline required field in the form. Both satisfy R5; pick based on what feels native in NiceGUI.
- [Affects R8][Technical] Parent-visible panel placement — top of profile/registration view, collapsible, last 30 days? Pick what works visually given NiceGUI's components.
- [Affects R2][Technical] How the actor is resolved inside `SQLModelWithSave.save()` — passing `actor_id` through the call site vs reading it from a request-scoped context. Planning should consider whether `nicegui` or starlette gives a clean way to access the current request from within a model method, and what the test-time injection story looks like.
- [Affects R2][Needs research] Whether the audit insert should happen in the same transaction as the save (atomic; the log is never out of sync with the data) or a separate one (lower contention; small risk of orphan log rows on failure). At pack scale either is fine; planning should pick and document.
