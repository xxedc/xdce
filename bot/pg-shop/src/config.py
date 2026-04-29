from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    BOT_TOKEN: SecretStr
    DB_URL: str
    ADMIN_IDS: list[int]
    MARZBAN_HOST: str
    MARZBAN_USERNAME: str
    MARZBAN_PASSWORD: str
    CRYPTOMUS_MERCHANT_ID: str = ""
    CRYPTOMUS_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()