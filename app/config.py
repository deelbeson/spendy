from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    plaid_client_id: str
    plaid_secret: str
    plaid_env: str = "sandbox"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
