# pack218
Simple website for CubScout Pack 218

## Local setup

```shell
./deps_create.sh
./deps_sync.sh
./run.sh
```

To just add dependencies and re-sync the venv:

```shell
source .venv/bin/activate
uv pip compile requirements.in -o requirements.txt
uv pip compile tests/requirements.in -o tests/requirements.txt
./deps_sync.sh
```
### Environment variables (for development purposes)

```shell
cat << EOF > .env
PACK218_STORAGE_KEY="<...>"
PACK218_APP_URL="http://0.0.0.0:8001"
PACK218_USE_SQLITE=1
GOOGLE_OAUTH_CLIENT_ID="<...>"
GOOGLE_OAUTH_CLIENT_SECRET="<...>"
``` 

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