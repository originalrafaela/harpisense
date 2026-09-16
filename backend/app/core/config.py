from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HarpiSense Backend"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://harpisense:harpisense@localhost:5432/harpisense"
    admin_username: str = "admin"
    admin_password: str | None = None
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_telemetry_topic: str = "harpisense/v1/telemetry/+/+"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_prefix="HARPI_",
        extra="ignore",
    )


settings = Settings()
