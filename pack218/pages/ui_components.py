from nicegui import ui
from nicegui.elements.card import Card
from nicegui.elements.grid import Grid


def grid() -> Grid:
    return ui.grid().classes('w-full sm:w-fall')

def card() -> Card:
    return ui.card().tight()

def card_title(title: str, level: int = 1) -> None:
    if level == 1:
        classes = 'bg-blue-6 text-white p-3 text-h5 w-full'
    elif level == 2:
        classes = 'bg-green-6 text-white p-3 text-h6 w-full'
    elif level == 3:
        classes = 'bg-purple-6 text-white p-3 text-subtitle1 w-full'
    else:
        classes = 'bg-grey-6 text-white p-3 text-subtitle2 w-full'
    ui.label(title).classes(classes)


def simple_dialog() -> ui.dialog:
    return ui.dialog().props('backdrop-filter="blur(8px) brightness(40%)"')


BUTTON_CLASSES_ACCEPT = 'bg-secondary glossy'
BUTTON_CLASSES_CANCEL = 'bg-purple glossy'
