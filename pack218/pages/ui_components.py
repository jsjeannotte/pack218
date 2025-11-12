from nicegui import ui
import io
import csv
from uuid import uuid4
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


def table_export_buttons(columns: list[dict], rows: list[dict], filename: str) -> None:
    """Render 'Download CSV' and 'Copy table as Markdown to clipboard' buttons for a NiceGUI table."""
    # Build CSV text
    header_labels = [c.get('label', c.get('name', '')) for c in columns]
    fields = [c.get('field', c.get('name', '')) for c in columns]

    def to_row_values(row: dict) -> list[str]:
        return [str(row.get(field, "")) for field in fields]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header_labels)
    for r in rows:
        writer.writerow(to_row_values(r))

    # Build Markdown text
    def esc(v: str) -> str:
        return v.replace("|", "\\|")

    md_lines = [
        "| " + " | ".join(header_labels) + " |",
        "|" + "|".join(["---"] * len(header_labels)) + "|",
    ]
    for r in rows:
        md_lines.append("| " + " | ".join(esc(str(v)) for v in to_row_values(r)) + " |")
    md_text = "\n".join(md_lines)

    hidden_id = f"md_{uuid4().hex}"
    ui.textarea(value=md_text).props(f'id="{hidden_id}" readonly').classes('hidden')

    def copy_to_clipboard():
        js = f'''
        const el = document.getElementById("{hidden_id}");
        if (el) {{
          el.select();
          el.setSelectionRange(0, 999999);
          navigator.clipboard.writeText(el.value);
        }}
        '''
        ui.run_javascript(js)
        ui.notify('Copied table (Markdown) to clipboard')

    # Buttons side-by-side
    with ui.row().classes('gap-2 items-center'):
        ui.button('Download CSV', icon='file_download').on_click(
            lambda: ui.download(buffer.getvalue().encode('utf-8'), f'{filename}.csv')
        )
        ui.button('Copy table as Markdown to clipboard', icon='content_copy').on_click(copy_to_clipboard)
