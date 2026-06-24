from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    default_fiscal_year: int = 2026
    log_level: str = "INFO"

    # Security — API key (opzionale: se impostata, ogni richiesta deve includerla)
    api_key: str = ""                    # vuoto = nessuna autenticazione richiesta

    # Rate limiting — richieste per minuto per IP
    rate_limit_per_minute: int = 30

    # CORS — origini ammesse (separata da virgole, "*" = tutte)
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    # Sicurezza — dimensione massima body in bytes (1 MB di default)
    max_body_size_bytes: int = 1_048_576

    # Documentazione API — disabilitare in produzione
    docs_enabled: bool = True

    # Proxy — IP del reverse proxy (separati da virgola, vuoto = connessione diretta)
    trusted_proxies: str = ""


settings = Settings()
