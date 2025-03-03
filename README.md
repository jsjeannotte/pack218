# pack218
Simple website for CubScout Pack 218

## Local setup

```shell
$ uv python install 3.11
$ uv venv --python 3.11
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
### Environment variables (for development purposes and production)

```shell
export PACK218_STORAGE_SECRET="<your_secret_key_for_local_storage>"
export POSTGRES_USER="pack218"
export POSTGRES_PASSWORD="<your_password_here>"
``` 

### Starting dependencies (Postgres)

```shell
docker compose up -d pack218_db 
```
## Production

```shell
docker compose up -d

# Service now listen on 0.0.0.0:8001 
```

## Alembic (schema evolution)

### How to setup Alembic (mostly for my own reference)

```shell
alembic init alembic
```

Then I edited the configs in `alembic.ini` and `alembic/env.py`.

### Example: Now to add a field

1) Add the field to the model (make sure it's non-NULL)

Example:
```python
phone_number: PhoneNumber | None = Field(default="", title="Phone Number")
```

2) Run Alembic to generate the migration script:

```shell
alembic revision --autogenerate -m "Add users.phone_number"        
```

3) Run the migration:

```shell
alembic upgrade head
```

## First deployment

1) Checkout the code on the server
2) Run `docker compose -d up`
3) Run `alembic upgrade head` from within the web app container

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

## TODO

- Password reset emails
- 