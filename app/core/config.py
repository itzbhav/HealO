from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    app_name: str = "HealO Backend"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    database_url: str = "sqlite:///./healo.db"

    whatsapp_verify_token: str = "your_verify_token_here"
    whatsapp_access_token: str = "your_access_token_here"
    whatsapp_phone_number_id: str = "your_phone_number_id_here"
    whatsapp_api_version: str = "v21.0"
    
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: str = os.getenv("TWILIO_WHATSAPP_FROM")
    twilio_content_sid: str = os.getenv("TWILIO_CONTENT_SID")


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()