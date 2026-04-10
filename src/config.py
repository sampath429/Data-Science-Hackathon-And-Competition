"""
src/config.py
Centralized configuration management using Pydantic Settings.
Loads variables from .env and validates presence of critical keys.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    """
    Application settings and environment variables.
    Pydantic automatically maps uppercase ENV variables to these attributes.
    """
    
    # --- Salesforce Configuration ---
    sf_instance_url: str = Field(..., alias="SF_INSTANCE_URL")
    # Using SecretStr prevents accidental logging of sensitive keys
    sf_client_id: str = Field(..., alias="SF_CLIENT_ID")
    sf_client_secret: str = Field(..., alias="SF_CLIENT_SECRET")
    default_tech_id: str = Field("005xxxxxxxxx", alias="DEFAULT_TECH_ID")

    # --- Azure AI & OpenAI Configuration ---
    azure_openai_endpoint: str = Field(..., alias="AZURE_OPENAI_ENDPOINT")
    azure_search_endpoint: str = Field(..., alias="AZURE_SEARCH_ENDPOINT")
    azure_search_index: str = Field("tech-manuals-index", alias="AZURE_SEARCH_INDEX")
    vault_url: str = Field(..., alias="VAULT_URL")

    # --- Persistence & Notifications (The "Closed-Loop" logic) ---
    # Connection string for Azure Service Bus Queue
    sb_conn_str: str = Field(..., alias="SB_CONN_STR")
    
    # Webhook for Teams/Slack alerts
    notif_webhook_url: str = Field(..., alias="NOTIF_WEBHOOK_URL")

    # Configuration for Pydantic to read from a .env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env vars not defined here
    )

# Create a singleton instance to be used across the app
settings = Settings()