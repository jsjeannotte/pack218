import logging
from functools import partial
from typing import Optional

from nicegui import ui
from sqlmodel import Session

from pack218.audit import AuditError, current_reason, set_actor_from_request
from pack218.entities.models import EventRegistration, Event, Family, User

from pack218.pages.on_behalf_panel import render_on_behalf_panel
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT, card_title, card, simple_dialog, BUTTON_CLASSES_CANCEL
from starlette.requests import Request

logger = logging.getLogger(__name__)


def render_page_event_registration(
    request: Request,
    session: Session,
    event_id: int,
    target_family_id: Optional[int] = None,
):
    """Render the family-side registration form.

    When ``target_family_id`` is provided, the form is rendered in
    "on-behalf-of" mode: an actual admin is registering / updating the
    given family's members. A required reason is collected and passed
    through ``current_reason`` so the audit hook records the actor and
    diff against each EventRegistration write.
    """
    current_user = User.get_current(request=request, session=session)
    event = Event.get_by_id(event_id, session=session)

    on_behalf = target_family_id is not None
    target_family: Optional[Family] = None
    if on_behalf:
        # Authorization: only real admins may act on behalf of another family.
        # The lens (view-as-non-admin) doesn't apply here — this is a write
        # endpoint, not just UI gating.
        if not User.current_user_is_admin(request=request, session=session):
            ui.label('You are not authorized to register on behalf of another family.').classes(
                'text-lg font-bold text-red-500'
            )
            return
        target_family = Family.get_by_id(target_family_id, session=session)
        if target_family is None:
            ui.label(f'Family {target_family_id} not found.').classes(
                'text-lg font-bold text-red-500'
            )
            return
        from sqlmodel import select
        family_members = sorted(
            session.exec(select(User).where(User.family_id == target_family_id)).all(),
            key=lambda u: (u.family_member_type or '', u.first_name or ''),
        )
    else:
        family_members = current_user.get_all_from_family()

    reason_input = None  # set below when on_behalf

    def perform_event_registration():
        # NiceGUI runs this handler in a separate task from the original GET
        # that called chrome() — ContextVars don't propagate, so re-bind the
        # actor here before any save/delete fires.
        set_actor_from_request(request=request, session=session)

        if on_behalf:
            reason = (reason_input.value or '').strip() if reason_input else ''
            if not reason:
                ui.notify('Reason is required when registering on behalf of another family',
                          color='negative')
                return
        else:
            reason = None

        has_registered_user = False
        rejected = False
        with simple_dialog() as dialog, card():
            with ui.card_section():
                ui.label('Registration update').classes('text-lg font-bold')
            with ui.card_section():
                for user_id, fields in user_to_fields.items():
                    user = User.get_by_id(user_id, session=session)
                    nothing_selected = not any(
                        field_checkbox.value for field_checkbox in fields.values()
                    )

                    # Set the reason for this specific save/delete so the
                    # audit hook attributes the change properly.
                    token = current_reason.set(reason) if on_behalf else None
                    try:
                        if nothing_selected:
                            existing = EventRegistration.get_by_user_and_event(
                                user_id=user_id, event_id=event_id, session=session
                            )
                            if existing:
                                EventRegistration.delete_by_id(existing.id, session=session)
                                ui.label(
                                    f"❌ {user.first_name}'s registration was removed."
                                )
                        else:
                            event_registration = EventRegistration.get_or_create_by_user_and_event(
                                user_id=user_id, event_id=event_id, session=session
                            )
                            for field_name, field_checkbox in fields.items():
                                setattr(event_registration, field_name, field_checkbox.value)
                            event_registration.save(session=session)
                            ui.label(f"☑️ Registration saved for {user.first_name}.")
                            has_registered_user = True
                    except AuditError as e:
                        rejected = True
                        ui.label(
                            f"⛔ {user.first_name}: {e}"
                        ).classes('text-red-500')
                        session.rollback()
                    except Exception as e:  # pragma: no cover - defensive
                        rejected = True
                        logger.exception(e)
                        ui.label(f"⚠️ {user.first_name}: {e}").classes('text-red-500')
                        session.rollback()
                    finally:
                        if token is not None:
                            current_reason.reset(token)

            if has_registered_user and not on_behalf:
                with ui.card_section():
                    ui.label(
                        "Disclaimer: If we end up with more people than we can fit the group site, "
                        "we're going to activate the waitlist."
                    ).classes('text-lg text-italic')

            with ui.card_section():
                ui.button('Close').on_click(dialog.close).classes(BUTTON_CLASSES_ACCEPT)

        # After confirm: send admin back to the trip detail; family back to home.
        next_url = (
            f'/camping-trip/{event_id}' if on_behalf else '/'
        )
        dialog.on('hide', lambda url=next_url: ui.navigate.to(url))
        dialog.on('escape-key', lambda url=next_url: ui.navigate.to(url))
        dialog.open()

    # Surface admin-made on-behalf changes touching this user's records.
    if not on_behalf:
        render_on_behalf_panel(session=session, current_user=current_user)

    with ui.card().classes('w-full').tight():
        card_title('Event Registration')
        with card():
            with ui.card_section():
                capacity_info = f" (capacity: {event.capacity})" if event.capacity else ""
                ui.label(
                    f"🏕️ Camping trip: {event.date} for {event.duration_in_days} days, "
                    f"at {event.location}{capacity_info}"
                ).classes('text-lg font-bold')

                if on_behalf:
                    with ui.card_section():
                        ui.label(
                            f"🛂 Acting on behalf of family: {target_family.family_name}"
                        ).classes('text-lg font-bold text-orange-700')
                        ui.label(
                            "Unchecking every option for a member removes their registration."
                        ).classes('text-sm italic')
                        reason_input = ui.textarea(
                            'Reason (required)',
                            placeholder=(
                                "e.g., 'Sarah called and is adding Saturday Lunch'"
                            ),
                        ).props('outlined').classes('w-full')

                with ui.card_section():
                    if on_behalf:
                        ui.label(
                            'Adjust each member below, then click Save.'
                        )
                    else:
                        ui.label(
                            'Please fill out the form below to register your family for this event'
                        )
                    with ui.row():

                        user_to_fields = {}

                        def set_all_dates(value: bool, user_id: int):
                            for field_name, field_checkbox in user_to_fields[user_id].items():
                                field_checkbox.value = value

                        for u in family_members:
                            current_event_registration = EventRegistration.get_by_user_and_event(
                                user_id=u.id, event_id=event_id, session=session
                            )

                            user_to_fields[u.id] = {}
                            with ui.card().tight():
                                card_title(
                                    f"{u.first_name} {u.last_name} ({u.family_member_type})",
                                    level=2,
                                )
                                with ui.row():
                                    ui.button(
                                        'Select None',
                                        on_click=partial(set_all_dates, value=False, user_id=u.id),
                                    ).classes(BUTTON_CLASSES_CANCEL)
                                    ui.button(
                                        'Select All',
                                        on_click=partial(set_all_dates, value=True, user_id=u.id),
                                    ).classes(BUTTON_CLASSES_ACCEPT)

                                with card():
                                    with ui.card_section():
                                        ui.label("Will this family member stay overnight?")
                                        user_to_fields[u.id]["stay_friday_night"] = ui.checkbox(
                                            "Stay Friday Night",
                                            value=(
                                                current_event_registration is not None
                                                and current_event_registration.stay_friday_night
                                            ),
                                        )
                                        user_to_fields[u.id]["stay_saturday_night"] = ui.checkbox(
                                            "Stay Saturday Night",
                                            value=(
                                                current_event_registration is not None
                                                and current_event_registration.stay_saturday_night
                                            ),
                                        )
                                    with ui.card_section():
                                        ui.label(
                                            "Select all the meals that you wish to be included "
                                            "($5 per meal/person)"
                                        )
                                        user_to_fields[u.id]["eat_saturday_breakfast"] = ui.checkbox(
                                            "Saturday Breakfast",
                                            value=(
                                                current_event_registration is not None
                                                and current_event_registration.eat_saturday_breakfast
                                            ),
                                        )
                                        user_to_fields[u.id]["eat_saturday_lunch"] = ui.checkbox(
                                            "Saturday Lunch",
                                            value=(
                                                current_event_registration is not None
                                                and current_event_registration.eat_saturday_lunch
                                            ),
                                        )
                                        user_to_fields[u.id]["eat_saturday_dinner"] = ui.checkbox(
                                            "Saturday Night Dinner",
                                            value=(
                                                current_event_registration is not None
                                                and current_event_registration.eat_saturday_dinner
                                            ),
                                        )
                                        user_to_fields[u.id]["eat_sunday_breakfast"] = ui.checkbox(
                                            "Sunday Breakfast",
                                            value=(
                                                current_event_registration is not None
                                                and current_event_registration.eat_sunday_breakfast
                                            ),
                                        )

                with ui.card_section():
                    with ui.row():
                        ui.button(
                            'Save' if on_behalf else 'Register'
                        ).on_click(perform_event_registration).classes(BUTTON_CLASSES_ACCEPT)
                        if on_behalf:
                            ui.button(
                                'Cancel',
                                on_click=lambda url=f'/camping-trip/{event_id}': ui.navigate.to(url),
                            ).props('outline').classes('ml-2')
