from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# These assume that you have an .env file in the root of your project
class Configs(BaseSettings):
    pack218_storage_key: str
    postgres_host: Optional[str] = None
    postgres_port: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    pack218_app_url: str
    pack218_use_sqlite: bool = False
    google_oauth_client_id: Optional[str] = None
    google_oauth_client_secret: Optional[str] = None

    local_dev: bool = False
    local_dev_user_id: int = 1

    run_in_editor: bool = False

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    @model_validator(mode='after')
    def validate_postgres_fields(self):
        if not self.pack218_use_sqlite:
            missing = [
                name for name in ('postgres_host', 'postgres_port', 'postgres_user', 'postgres_password')
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    f"When PACK218_USE_SQLITE is not enabled, the following fields are required: {', '.join(missing)}"
                )
        return self

config = Configs()
