"""
config.py — Merkezi ortam değişkenleri yönetimi.
Tüm API anahtarları ve ayarlar buradan okunur.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Uygulama ────────────────────────────────────────────
    app_name: str = "Pazarlama Maratonu Kayıt API"
    app_base_url: str = "http://localhost:8000"   # Prod'da gerçek URL yazılır
    token_ttl_hours: int = 24                      # Onay linkinin geçerlilik süresi

    # ── Notion ──────────────────────────────────────────────
    notion_api_key: str = ""
    notion_database_id: str = ""                  # Kayıtların tutulduğu DB'nin ID'si

    # ── E-posta (SMTP) ──────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""                          # "Marka Mutfağı <noreply@example.com>"

    # ── Slack ───────────────────────────────────────────────
    slack_bot_token: str = ""
    slack_channel_id: str = ""                    # #pazarlama-maratonu kanal ID'si

    # ── SMS (Twilio) ─────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""                  # "+90xxxxxxxxxx"
    sms_enabled: bool = True                      # False yaparak SMS'i tamamen kapat

    # ── Güvenlik ────────────────────────────────────────────
    secret_key: str = "degistir-beni-production-da"  # Token imzalama için

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Settings nesnesini önbelleğe alarak tek instance döner."""
    return Settings()
