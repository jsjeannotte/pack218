# pack218
Simple website for CubScout Pack 218

## Local setup

```shell
$ python3 -m venv .venv
$ source .venv/bin/activate
$ uv pip compile requirements.in -o requirements.txt
$ uv pip install -r requirements.txt
$ pycharm .
```

To just add dependencies and re-sync the venv:

```shell
$ source .venv/bin/activate
$ uv pip compile requirements.in -o requirements.txt
$ uv pip compile tests/requirements.in -o tests/requirements.txt
$ uv pip sync tests/requirements.txt
```
### Environment variables (for development purposes)

```shell
export PACK218_STORAGE_SECRET="<your_secret_key_for_local_storage>"
export POSTGRES_USER="pack218"
export POSTGRES_PASSWORD="<your_password_here>"
``` 

### Starting dependencies (mostly Postgres)

```shell
docker compose up -d 
```

## How Alembic was setup

```shell
alembic init alembic
```

Then I edited the configs in `alembic.ini` and `alembic/env.py`.

Now to add a field:

1) Add the field to the model (make sure it's non-NULL)

Example:
```python
phone_number: str | None = Field(default="", title="Phone Number")
```

2) Run Alembic to generate the migration script:

```shell
alembic revision --autogenerate -m "Add users.phone_number"        
```

3) Run the migration:

```shell
alembic upgrade head 
```
Now we need to read this: https://stackoverflow.com/questions/68932099/how-to-get-alembic-to-recognise-sqlmodel-database-model

## References

- NiceGUI: https://nicegui.io/documentation
  - Wizard design: https://nicegui.io/documentation/section_page_layout#stepper
  - Context Menu: https://nicegui.io/documentation/section_page_layout#context_menu
  - Tooltip: https://nicegui.io/documentation/section_page_layout#tooltip
  - Dialog: https://nicegui.io/documentation/section_page_layout#dialog
  - Date Input: https://nicegui.io/documentation/section_page_layout#dialog
  - Adjusting colors: https://v0-13.quasar-framework.org/api/css-color-palette.html
  - Table with icon: https://github.com/zauberzeug/nicegui/discussions/1641
  - Width (like `w-full` or `w-1/2`): https://tailwindcss.com/docs/width
- NiceCRUD: https://github.com/Dronakurl/nicecrud
