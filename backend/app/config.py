from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://ops:ops@localhost:5432/ops_esports"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_MINUTES: int = 60 * 12
    UPLOAD_DIR: str = "uploads"
    CORS_ORIGINS: str = "http://localhost:5173"

    # ---- Email (optional announcement emails) ---------------------------
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "OPS Esports <no-reply@example.com>"

    # ---- Payments -------------------------------------------------------
    # Live money movement is OFF unless BOTH flags are explicitly enabled.
    # Flip them only after legal review and provider compliance sign-off.
    LIVE_PAYMENTS_ENABLED: bool = False
    COMPLIANCE_SIGNOFF_REF: str = ""  # reference of the written sign-off
    DARAJA_ENV: str = "sandbox"  # sandbox | production
    DARAJA_CONSUMER_KEY: str = ""
    DARAJA_CONSUMER_SECRET: str = ""
    DARAJA_SHORTCODE: str = "174379"
    DARAJA_PASSKEY: str = ""
    DARAJA_INITIATOR_NAME: str = ""
    DARAJA_SECURITY_CREDENTIAL: str = ""
    PUBLIC_BASE_URL: str = "https://example.com"
    CALLBACK_SECRET: str = "change-me-callback"  # path secret on callback URLs

    # Provider transaction fee disclosed to members; never deducted from payout.
    PROVIDER_FEE_NOTE: str = "M-Pesa/provider charges are shown separately and are never deducted from the KSh 7,000 payout."

    @property
    def live_money_allowed(self) -> bool:
        return self.LIVE_PAYMENTS_ENABLED and bool(self.COMPLIANCE_SIGNOFF_REF) and self.DARAJA_ENV == "production"


settings = Settings()
