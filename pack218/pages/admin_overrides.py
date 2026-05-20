"""``OnBehalfNiceCRUD`` — a thin NiceCRUDWithSQL wrapper that prompts for a
reason when an admin saves another user's (or another family's) record.

The save-boundary check in ``pack218.audit`` is the structural backstop:
without a reason in ``current_reason``, any non-self write raises
``AuditError``. This wrapper just gives the admin a UI path to supply the
reason before that error fires, so the common case "admin edits Sarah's
profile, types why, save succeeds" is a single round-trip.

Blocklisted field hiding is intentionally not done here — niceguicrud's
``additional_exclude`` is a class-level configuration, not a per-target one.
The save-boundary still rejects any blocked-field change on a non-self
edit, and the UI surfaces the rejection via ``ui.notify``. If a friendlier
"the field is greyed out when editing another user" experience is needed
later, it warrants its own brainstorm — see docs/brainstorms/2026-05-11-admin-on-behalf-requirements.md.
"""
import logging
from typing import Optional

from nicegui import ui

from pack218.audit import (
    AuditError,
    current_actor,
    current_reason,
    is_self_edit,
)
from pack218.entities import NiceCRUDWithSQL
from pack218.entities.models import Family, User
from pack218.persistence.engine import engine
from pack218.pages.ui_components import BUTTON_CLASSES_ACCEPT, BUTTON_CLASSES_CANCEL
from sqlmodel import Session

logger = logging.getLogger(__name__)


async def _ask_reason_modal(target_label: str) -> Optional[str]:
    """Open an awaitable reason modal. Returns the typed reason or None on cancel."""
    with ui.dialog() as dialog, ui.card():
        with ui.card_section():
            ui.label(f"Editing on behalf of {target_label}").classes('text-lg font-bold')
            ui.label(
                "A reason is required when editing another user's record. "
                "It is recorded on the change and shown to the affected user."
            ).classes('text-sm')
        reason_input = ui.textarea("Reason").classes('w-full').props('autofocus')
        with ui.row().classes('justify-end gap-2'):
            ui.button("Cancel", on_click=lambda: dialog.submit(None)).classes(BUTTON_CLASSES_CANCEL)
            ui.button(
                "Save",
                on_click=lambda: dialog.submit((reason_input.value or "").strip() or None),
            ).classes(BUTTON_CLASSES_ACCEPT)
    return await dialog


def _label_for_target(item) -> str:
    if isinstance(item, User):
        return f"{item.first_name} {item.last_name}"
    if isinstance(item, Family):
        return f"the {item.family_name} family"
    return type(item).__name__


def _is_on_behalf(actor_id: Optional[int], item) -> bool:
    """True iff this write needs a reason. False for self-edits and no-actor cases.

    Spin up a short-lived session for the lookup — NiceCRUD does not pass its
    session into update/delete overrides, and audit.is_self_edit needs one to
    load the actor User for the cross-family check. This session is read-only;
    the actual write uses NiceCRUD's own session via super().update().
    """
    if actor_id is None:
        return False
    with Session(engine) as session:
        return not is_self_edit(session, item, actor_id)


class OnBehalfNiceCRUD(NiceCRUDWithSQL):
    """Wraps ``NiceCRUDWithSQL`` to ask for a reason on non-self updates and deletes.

    Reads ``current_actor`` from the request context (set by ``chrome()`` in
    ``pack218.app``). For self-edits (same user, or same family for User /
    EventRegistration / Family), forwards directly to ``super()`` with no
    prompt. For on-behalf edits, awaits a reason via the modal, sets
    ``current_reason``, calls ``super()``, and resets the context.
    """

    async def update(self, item):
        actor_id = current_actor.get()
        if not _is_on_behalf(actor_id, item):
            return await super().update(item)

        reason = await _ask_reason_modal(_label_for_target(item))
        if reason is None:
            ui.notify("Update cancelled — no reason provided", color='warning')
            return

        token = current_reason.set(reason)
        try:
            await super().update(item)
        except AuditError as e:
            ui.notify(str(e), color='negative')
        except Exception as e:  # pragma: no cover - defensive
            logger.exception(e)
            ui.notify(f"Error: {e}", color='negative')
        finally:
            current_reason.reset(token)

    async def delete(self, id: int):
        actor_id = current_actor.get()
        # delete uses just the id; load the target to determine self-edit status.
        with Session(engine) as session:
            target = self.basemodeltype.get_by_id(id, session=session)
        if target is None or not _is_on_behalf(actor_id, target):
            return await super().delete(id)

        reason = await _ask_reason_modal(_label_for_target(target))
        if reason is None:
            ui.notify("Delete cancelled — no reason provided", color='warning')
            return

        token = current_reason.set(reason)
        try:
            await super().delete(id)
        except AuditError as e:
            ui.notify(str(e), color='negative')
        except Exception as e:  # pragma: no cover - defensive
            logger.exception(e)
            ui.notify(f"Error: {e}", color='negative')
        finally:
            current_reason.reset(token)


__all__ = ["OnBehalfNiceCRUD"]
