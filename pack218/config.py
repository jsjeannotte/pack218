from pydantic_settings import BaseSettings, SettingsConfigDict


# These assume that you have an .env file in the root of your project
class Configs(BaseSettings):
    pack218_storage_key: str
    postgres_host: str
    postgres_port: str
    postgres_user: str
    postgres_password: str
    pack218_app_url: str
    pack218_use_sqlite: bool


    run_in_editor: bool = False

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

config = Configs()
