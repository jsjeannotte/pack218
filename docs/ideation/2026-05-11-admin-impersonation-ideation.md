---
date: 2026-05-11
topic: admin-impersonation
focus: Admin needs to take action on behalf of a parent (e.g., update a camping trip registration when the parent can't make changes themselves)
mode: repo-grounded
---

# Ideation: admin "act on behalf of" in pack218

## Grounding Context

### Codebase context
- **Stack:** Python + NiceGUI (FastAPI + SQLModel + SQLAlchemy + Alembic). SQLite local dev. Google OAuth2 + email-based auth, local dev fallback to hardcoded user.
- **Layout:** `pack218/app.py` (main routing), `pages/` (UI), `entities/` (models), `persistence/` (DB layer), `email/`, `images/`.
- **Auth model:** `request.session["user"]` holds Google OAuth user info. Single boolean `User.is_admin`. `assert_is_admin()` is the only authorization gate, called per-page. No middleware enforcement. No JWT — session is mutable.
- **Key entities:** `User`, `Family` (group container with parents/members), `Event` (camping trips, capacity, waitlisting), `EventRegistration` (signup + meals + overnight).
- **Audit trail:** ZERO. No `modified_by`, no `action_ts`, no activity log.
- **Convention:** `SQLModelWithSave` base class with `.save()`, `.get_by_id()`, `.get_all()` helpers — universal write path.
- **Strategy:** No STRATEGY.md. Hobby/volunteer Cub Scout pack. Recent commits: waitlisting, event capacity. Bias: keep simple, ship value to volunteer admins, avoid enterprise creep.

### External context (prior art, distilled)
- Production-grade library patterns (django-hijack, devise-masquerade, laravel-impersonate) all share the same shape: store original admin in separate session slot, swap identity, persistent banner, explicit exit.
- RFC 8693 distinguishes impersonation (only `sub` claim survives — admin disappears) from delegation (`act` claim preserves admin alongside subject). Delegation is the cleaner audit pattern.
- Pigment (2026): separate JWT with `act` claim + admin identity, 30-min expiry, read-only flag enforced at middleware, build-time static analyzer, dark-border viewport.
- Healthcare proxy (HIPAA "personal representative"): caregiver gets their OWN credentials linked to patient — acts *on behalf of*, not *as*. Tiered scopes. Consent-first.
- sudo vs su: `sudo -u <user> <action>` (scoped, action-level) vs `su` (full swap, riskier).
- Salesforce "Log In As" requires target consent; Varonis breach showed undetectable admin actions when no anomaly monitoring on impersonation.
- Facebook "View As" (2018): read-only preview loaded a write-capable component that generated a real auth token — 50M accounts. Any "act as" mode must explicitly suppress side-effects.
- PowerSchool admin-creates-parent-account: data-entry-on-behalf pattern, lower-risk than impersonation when user hasn't onboarded.
- Authress position: prefer narrow scoped grants over impersonation — "admin updated X for parent" is more honest than "parent X updated their record."
- Universal audit schema: `actor_id`, `subject_id`, `action`, `timestamp`, optional `reason`.

### Past learnings
None — `docs/solutions/` does not yet exist. Greenfield from learnings standpoint.

## Ranked Ideas

### 1. Phone Intake form — admin acts as themselves, scoped sudo-action, reason required
**Description:** Admin stays signed in as themselves and opens a single page that picks a subject family + event (or profile section). The form pre-fills with the subject's current values; admin edits and submits. Server writes the change with `actor_id = admin, subject_id = parent` plus a one-line reason ("Sarah called, dropping Friday overnight"). No session swap; no banner-and-forget; no "I'm Sarah right now" cognitive trap. Names the feature honestly for the actual workflow (capturing a phone/text request) rather than the mechanism (impersonation).
**Warrant:** `direct:` `SQLModelWithSave.save()` is the universal write path and `assert_is_admin()` is the only auth gate — adding one form + one write hook is a small delta. `external:` sudo `-u` (scoped action) > `su` (full swap); Authress's "narrow scoped grants over impersonation"; PowerSchool data-entry-on-behalf.
**Rationale:** Solves the canonical Friday-night-10pm case in one click without inheriting any of the impersonation failure modes catalogued in the grounding (Facebook 2018 side-effects, Pigment forgot-I-was-in-it, Salesforce/Varonis undetectable admin actions, GDPR right-to-know failures).
**Downsides:** Cannot debug "what does Sarah see when she logs in?" — needs a separate read-only view (worth its own brainstorm). Multi-admin concurrent edits still race (single-admin reality today; revisit later).
**Confidence:** 85%
**Complexity:** Low
**Status:** Explored

### 2. Universal `ActionLog(actor, subject, entity, before, after, ts, reason)` hooked into `SQLModelWithSave.save()`
**Description:** One append-only table, one save-hook. Today actor and subject are identical for every write; once #1 ships they diverge. Schema unchanged between the two states. Indexable by `subject_id` (parent asks "what changed on my account?") and `actor_id` (volunteer asks "what did I do last Saturday?").
**Warrant:** `direct:` Grounding flagged "Audit trail: ZERO. No `modified_by`, no `action_ts`, no activity log" and named `SQLModelWithSave.save()` as the universal write path. `external:` audit schema is universal across django-hijack, devise-masquerade, Pigment, RFC 8693 (`act` claim), AWS CloudTrail.
**Rationale:** Highest-leverage move in the set. Every future feature that mutates data gets free auditability — waitlist promotions, capacity overrides, the roadmap'd password-reset emails, GDPR/parental-disclosure requests, debugging "why did this registration disappear?" Impersonation just becomes the special case where `actor ≠ subject`. Pays off whether or not #1 ever ships.
**Downsides:** Adds rows on every write — negligible at pack scale (<50 families). Requires a small read path for the parent-visible view in #3.
**Confidence:** 90%
**Complexity:** Low
**Status:** Explored

### 3. Parent-visible "changes made on my behalf" panel
**Description:** On the parent's own profile and registration pages, show a small panel listing recent changes made by anyone other than themselves: *"Apr 14 — Cubmaster Dave changed your Saturday breakfast to vegetarian (reason: 'text from Sarah')."* Drawn directly from #2. Optionally email a digest after every admin-on-behalf write.
**Warrant:** `external:` Real-estate buyer's-agent law — *fiduciary visibility runs toward the principal*; the principal sees the agent's name on every document. Inverts the common engineering pattern of hiding the actor from the subject. Aligns with the volunteer-trust culture of a pack and forecloses the Salesforce/Varonis undetectable-admin-action class entirely.
**Rationale:** Million-eyeball audit at near-zero implementation cost. Parents will immediately notice if a change appears that they didn't request — the social mechanism a volunteer-run pack actually relies on.
**Downsides:** Slight UI clutter (collapsible, last-N-days). Requires #2.
**Confidence:** 80%
**Complexity:** Low
**Status:** Unexplored

### 4. Co-parent invite — provision the second User on the same Family
**Description:** The `Family` model already supports multiple parents. Most "parent can't update" cases are not impersonation problems — they are "only one parent in the household ever signed in with Google." Add a one-click "Invite co-parent" button on every family page that sends a Google OAuth invite to the second adult, landing as a regular `User` linked to the same `Family` with equal edit rights.
**Warrant:** `direct:` Grounding confirms `Family` is the existing group container with parent membership; only the invite UX is missing. Reuses the email primitive already on the roadmap for password reset.
**Rationale:** Solves the *root cause* of a large fraction of impersonation requests instead of building a workaround. Zero new authorization surface; reuses existing Google OAuth flow.
**Downsides:** Some households deliberately keep one logged-in account; need an off-ramp. Doesn't help single-parent families or grandparent pickups (#1 and #5 cover those).
**Confidence:** 80%
**Complexity:** Low
**Status:** Unexplored

### 5. Magic-link "Cancel / Update meals / Update overnight" in every event email
**Description:** Every confirmation and reminder email already gets sent. Append signed magic links — valid until the event starts, scoped to that one registration, single-use — for the most common parent self-service actions. No login required.
**Warrant:** `direct:` `pack218/email/` and confirmation-email infrastructure already exist; recent commits "Implement Waitlisting" + "Add support for Event capacity" show active work in this area. `reasoned:` The cheapest impersonation is the one no one ever needs.
**Rationale:** ~80% of the "act on behalf of a parent" cases the user named are last-minute changes a parent could do themselves if the friction were low enough. Magic links route the action through the parent's own identity — clean audit trail by default.
**Downsides:** Token security needs care (sign, expire, single-use, scoped). Doesn't help when contact info is wrong (loops back to #1).
**Confidence:** 75%
**Complexity:** Low-Medium
**Status:** Unexplored

### 6. Side-effect suppression decorator for `actor ≠ subject` writes
**Description:** Once any "on behalf of" write path exists (#1, #5 fallback, future CSV import, future bulk waitlist promotion), guard against the Facebook-2018 failure mode: a read-only-looking action that fires real notifications, capacity recalculations, or payment side-effects on the subject's behalf. Add a `@side_effect(suppress_when_on_behalf=True)` decorator on every function in `pack218/email/` and future integrations. Default new side-effects to opt-in-suppression-fail-closed.
**Warrant:** `external:` Facebook 2018 breach affected 50M accounts because "View As" loaded a write-capable video uploader that generated a real auth token. Grounding: "any 'act as' mode must explicitly suppress side-effects." Pigment's middleware-layer read-only enforcement.
**Rationale:** Cheap to bake in NOW while there's only the email subsystem to instrument. Expensive to retrofit after the first surprise email goes out.
**Downsides:** Adds one decorator per side-effecting function. Requires a team convention every new email/notification PR must follow.
**Confidence:** 70%
**Complexity:** Low
**Status:** Unexplored

### 7. Standing proxy — parent declares `Delegation(grantor, grantee, scope, expires_at)`
**Description:** The other direction of #1: instead of admin claiming authority each time, the parent grants standing permission from their settings ("Allow Cubmaster Dave to manage my family's registrations until May 31"). One small table generalizes admin-on-behalf, grandparent help, divorced-parent shared custody, and future Den-Leader scoped roles. Admin's "act on behalf" menu only lists users who have granted them a proxy.
**Warrant:** `external:` USPS Form 3575 — the recipient declares forwarding, with start, end, and forwarder identity. HIPAA "personal representative" model. Salesforce's "Log In As" requires target consent. Structural property: *agency originates from the principal.*
**Rationale:** Lower priority than #1 + #4 because it adds a UX step parents must initiate, but a stronger consent posture if/when the pack grows past one admin. The `Delegation` table is also the right primitive for a future "Den Leader manages only their den" feature.
**Downsides:** Probably overkill for a single-admin volunteer pack today. Worth schema-defining; UX can wait.
**Confidence:** 55%
**Complexity:** Medium
**Status:** Unexplored

## Cross-Cutting Note

The strongest cross-frame convergence was on **"don't build session-swap impersonation at all."** Five of six frames independently arrived at sudo-action / scoped-write / phone-intake variants rather than the full identity-swap pattern the user's prompt implies. The web research grounding amplified this: every documented breach (Facebook 2018, Salesforce/Varonis) and every modern best-practice writeup (Authress, RFC 8693 delegation > impersonation) points the same direction.

If pack218 genuinely needs the literal session-swap experience (e.g., for debugging "what does Sarah see"), that's a separate, smaller idea worth a standalone brainstorm — most likely as a read-only "view-as" with explicit side-effect suppression (#6 applied) rather than a writable impersonation mode.

## Recommended Starting Pair

**#1 + #2 ship together.** #1 is the user-facing primitive that solves the Friday-night-10pm case. #2 is the audit substrate that makes #1 trustworthy and seeds every future feature. **#3** is the natural follow-up sprint. **#4** and **#5** are independent and can ship in any order to reduce #1's load. **#6** ships alongside #1 as a guard. **#7** is schema-worthy but not build-worthy yet.

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Annotate every form `self-only` vs `assistable` whitelist | Too much ceremony for <50 families; subsumed by #1 + #6 |
| 2 | $0 hidden `on_behalf_of_email` form field | Fragile; relies on admin remembering a hidden field; creates two-tier UX |
| 3 | 10-second chip-grid admin dashboard | Strong UX idea but a refinement of #1, not a separate primitive — fold into #1 brainstorm |
| 4 | Read-only stand-in view + structured write | Subsumed by #1; standalone read-only view is a separate brainstorm |
| 5 | Reason field as standalone idea | Subsumed by #2 (ActionLog has `reason` column) |
| 6 | Reason-required banner for actor≠subject | Subsumed by #1 + #2 (form already collects reason) |
| 7 | Buyer's-agent disclosure footer (standalone) | Subsumed by #3 (parent-visible panel) |
| 8 | Notary "with parent present" witness toggle | Folds into #2's `reason` field; not a separate primitive |
| 9 | Admin-proposes-parent-confirms link | Adds latency to the Friday-night case (parent unreachable); use #5 for cases where parent CAN respond |
| 10 | Inbound SMS/email parser | Too much infra and security surface for hobby-scale; out of scope |
| 11 | Proposal queue / expediter tickets | Subsumed by item 9 critique |
| 12 | Two-key launch (every action awaits parent confirm) | Breaks the canonical use case (parent unreachable); too strict |
| 13 | Family-scoped delegate tokens | Subsumed by #7 (`Delegation` table) |
| 14 | Admin as temp "guest parent" on Family | Clever but couples admin assistance to family membership; #1 is cleaner |
| 15 | Zero-admin peer-rubber-stamp pack | Throws away legitimate convenience of having a Cubmaster; thought-experiment value only |
| 16 | `get_acting_context()` helper | Premature abstraction; emerges naturally from #1 implementation |
| 17 | `assert_can(actor, action, subject)` capability service | YAGNI at single-admin scale; revisit if multiple roles emerge |
| 18 | `EventCoordinator` / `DenLeader` scoped role tables | Premature for one admin; meeting-test fails at current scale |
| 19 | `Event.coordinator_user_id` ownership | Useful direction if multi-admin emerges; not needed now |
| 20 | Backstage-badge event-scoped + 60min impersonation | Mitigation for session-swap risk; #1 (no session swap) makes it unnecessary |
| 21 | Sharded admins by den + quorum | Premature for <50 families |
| 22 | Acting banner + dark viewport border | Vestigial under #1 (no session-swap mode to flag) |
| 23 | ATC handoff call-and-response | Only relevant under session-swap; #1 has no handoff |
| 24 | Substitute-teacher role intersection | Only relevant under session-swap; #1 sidesteps |
| 25 | Three tiers (View / Suggest / Act as) | Worth a brainstorm if read-only view returns as a separate need |
| 26 | Impersonation-by-default UI | High cognitive cost; gimmicky for volunteer admin |
| 27 | SOC2-grade unlimited-budget thought experiment | Carry-back items absorbed into #2 + #3; rest is enterprise creep |
| 28 | Multi-admin race lock / advisory | Premature at single-admin reality; revisit if a second admin joins |
| 29 | Append-only `RegistrationCorrection` stack | Elegant but a much bigger schema overhaul than the value justifies; #2 captures the audit benefit at lower cost |
| 30 | Ownership transfer of `EventRegistration` | Subsumed by #1's actor/subject model |
| 31 | "Invite to claim" pattern for password reset / new parents | Useful but a different feature (onboarding), not impersonation; track separately |
