"""Admin route for editing any user's EventRegistration on their behalf.

Mounted at ``/admin/events/{event_id}/registrations`` from pack218.app. Renders
the event's roster grouped by Family and gives admins an inline edit affordance
per row — opens a modal pre-filled with the registration's current values plus
a required reason field. Save sets ``current_reason`` and calls
``EventRegistration.save()``; the audit hook in U3 records the actor/subject/diff
and enforces the on-behalf-of rules.
"""
import logging
from functools import partial

from nicegui import ui
from sqlmodel import Session
from starlette.requests import Request

from pack218.audit import AuditError, current_reason, set_actor_from_request
from pack218.entities.models import Event, EventRegistration, Family, User
from pack218.pages.ui_components import (
    BUTTON_CLASSES_ACCEPT,
    BUTTON_CLASSES_CANCEL,
    card_title,
    simple_dialog,
)

logger = logging.getLogger(__name__)


_REGISTRATION_FIELDS = [
    ("stay_friday_night", "Stay Friday Night"),
    ("stay_saturday_night", "Stay Saturday Night"),
    ("eat_saturday_breakfast", "Saturday Breakfast"),
    ("eat_saturday_lunch", "Saturday Lunch"),
    ("eat_saturday_dinner", "Saturday Dinner"),
    ("eat_sunday_breakfast", "Sunday Breakfast"),
    ("has_paid", "Has Paid"),
]


def _open_edit_modal(session: Session, request: Request, event: Event, subject: User,
                     registration: EventRegistration, refresh) -> None:
    """Edit-on-behalf modal: reason field + every EventRegistration toggle."""
    with simple_dialog() as dialog, ui.card():
        with ui.card_section():
            card_title(
                f"Edit on behalf of {subject.first_name} {subject.last_name}", level=2
            )
            ui.label(f"Event: {event.date} — {event.location}").classes('text-sm')

        checkboxes = {}
        with ui.card_section():
            for field, label in _REGISTRATION_FIELDS:
                checkboxes[field] = ui.checkbox(
                    label, value=getattr(registration, field)
                )

        with ui.card_section():
            reason_input = ui.textarea(
                "Reason (required)",
                placeholder="e.g., 'Sarah texted at 7pm, dropping Saturday breakfast'",
            ).classes('w-full').props('autofocus')

        def confirm():
            # Re-bind actor for this handler task — ContextVars set by
            # chrome() during the page-render request don't propagate here.
            set_actor_from_request(request=request, session=session)

            reason = (reason_input.value or "").strip()
            if not reason:
                ui.notify("Reason is required", color='negative')
                return

            # Apply field changes to the persistent instance, then save through
            # the audit-hooked save() path. current_reason is read inside save().
            for field, _label in _REGISTRATION_FIELDS:
                setattr(registration, field, checkboxes[field].value)

            token = current_reason.set(reason)
            try:
                registration.save(session=session)
            except AuditError as e:
                ui.notify(str(e), color='negative')
                session.rollback()
                # Discard in-memory dirty state so a re-submit doesn't silently
                # commit the previously-rejected values with an empty diff.
                session.expire(registration)
                return
            except Exception as e:  # pragma: no cover - defensive
                logger.exception(e)
                ui.notify(f"Error: {e}", color='negative')
                session.rollback()
                session.expire(registration)
                return
            finally:
                current_reason.reset(token)

            ui.notify(
                f"Updated {subject.first_name}'s registration", color='positive'
            )
            dialog.close()
            refresh()

        with ui.row().classes('justify-end gap-2'):
            ui.button("Cancel", on_click=dialog.close).classes(BUTTON_CLASSES_CANCEL)
            ui.button("Save", on_click=confirm).classes(BUTTON_CLASSES_ACCEPT)

    dialog.open()


def _confirm_drop(session: Session, request: Request, subject: User,
                  registration: EventRegistration, refresh) -> None:
    """Drop-with-reason: deletes the registration through the audit-hooked path."""
    with simple_dialog() as dialog, ui.card():
        with ui.card_section():
            card_title(
                f"Drop {subject.first_name}'s registration?", level=2
            )
            ui.label(
                "This removes the registration. Capture why so the parent can see it."
            ).classes('text-sm')

        reason_input = ui.textarea("Reason (required)").classes('w-full').props('autofocus')

        def confirm():
            set_actor_from_request(request=request, session=session)

            reason = (reason_input.value or "").strip()
            if not reason:
                ui.notify("Reason is required", color='negative')
                return

            token = current_reason.set(reason)
            try:
                EventRegistration.delete_by_id(registration.id, session=session)
            except AuditError as e:
                ui.notify(str(e), color='negative')
                session.rollback()
                return
            except Exception as e:  # pragma: no cover - defensive
                logger.exception(e)
                ui.notify(f"Error: {e}", color='negative')
                session.rollback()
                return
            finally:
                current_reason.reset(token)

            ui.notify(
                f"Dropped {subject.first_name}'s registration", color='positive'
            )
            dialog.close()
            refresh()

        with ui.row().classes('justify-end gap-2'):
            ui.button("Cancel", on_click=dialog.close).classes(BUTTON_CLASSES_CANCEL)
            ui.button("Drop", on_click=confirm).classes(BUTTON_CLASSES_ACCEPT)

    dialog.open()


def render_admin_event_registrations(session: Session, event_id: int, request: Request) -> None:
    """Roster grouped by Family with an inline edit-on-behalf affordance per row."""
    event = Event.get_by_id(event_id, session=session)
    if event is None:
        ui.label(f"Event {event_id} not found").classes('text-red-500')
        return

    @ui.refreshable
    def render_roster():
        with ui.card().classes('w-full'):
            card_title(f"Registrations for {event.date} — {event.location}")
            ui.label(
                "Edit any family member's registration on their behalf. "
                "A reason is required and is recorded with the change."
            ).classes('text-sm p-2')

            registrations = EventRegistration.select_by_event(
                session=session, event_id=event.id
            )
            if not registrations:
                ui.label("No registrations yet for this event.").classes('p-4 italic')
                return

            # Group by family for readability.
            by_family: dict[int, list[EventRegistration]] = {}
            for r in registrations:
                user = r.user(session=session)
                if user is None:
                    continue
                by_family.setdefault(user.family_id or 0, []).append(r)

            for family_id, regs in by_family.items():
                family = None
                if family_id:
                    family = Family.get_by_id(family_id, session=session)
                family_label = family.family_name if family else "(no family)"

                with ui.card().classes('w-full mb-2'):
                    card_title(f"Family: {family_label}", level=2)
                    for r in regs:
                        subject = r.user(session=session)
                        if subject is None:
                            continue

                        with ui.row().classes('items-center w-full gap-3 p-2'):
                            ui.label(
                                f"{subject.first_name} {subject.last_name} "
                                f"({subject.family_member_type})"
                            ).classes('font-bold')
                            summary = ", ".join(
                                label for field, label in _REGISTRATION_FIELDS
                                if getattr(r, field) and field != "has_paid"
                            ) or "no meals or overnights selected"
                            ui.label(summary).classes('text-sm')
                            paid_label = "✅ paid" if r.has_paid else "💰 unpaid"
                            ui.label(paid_label).classes('text-sm')

                            ui.space()

                            # Admin-on-admin: hide the edit affordance entirely
                            # when the subject is an admin (audit hook still
                            # enforces at the save boundary).
                            if subject.is_admin:
                                ui.label("(admin record — not editable here)")\
                                    .classes('text-xs italic')
                                continue

                            ui.button(
                                "Edit",
                                icon='edit',
                                on_click=partial(
                                    _open_edit_modal,
                                    session,
                                    request,
                                    event,
                                    subject,
                                    r,
                                    render_roster.refresh,
                                ),
                            ).classes(BUTTON_CLASSES_ACCEPT)
                            ui.button(
                                "Drop",
                                icon='delete',
                                on_click=partial(
                                    _confirm_drop,
                                    session,
                                    request,
                                    subject,
                                    r,
                                    render_roster.refresh,
                                ),
                            ).classes(BUTTON_CLASSES_CANCEL)

    render_roster()
