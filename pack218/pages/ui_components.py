from nicegui import ui
from nicegui.elements.card import Card
from nicegui.elements.grid import Grid


def grid() -> Grid:
    return ui.grid().classes('w-full sm:w-fall')

def card() -> Card:
    return ui.card().tight()

def card_title(title: str) -> None:
    ui.label(title).classes('bg-primary text-white p-3 text-h6 w-full')

BUTTON_CLASSES_ACCEPT = 'bg-secondary glossy'
BUTTON_CLASSES_CANCEL = 'bg-purple glossy'
