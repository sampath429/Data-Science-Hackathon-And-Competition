"""
src/config.py
Centralized configuration management using Pydantic Settings.
Ensures all required environment variables are present before execution.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Application settings mapped to Environment Variables.
    Values can be provided via a .env file or system env vars.
    """
    
    # --- Salesforce Settings ---
    vault_url: str = Field(description="Azure Key Vault URL")
    sf_instance_url: str = Field(description="Salesforce Instance URL")
    default_tech_id: str = Field(description="Default Salesforce User ID for Task assignment")
    
    # --- Azure AI & Search Settings ---
    azure_search_endpoint: str
    azure_search_index: str
    azure_openai_endpoint: str
    
    # --- Egress / Notification Settings ---
    notif_webhook_url: str = Field(description="Slack or Teams Webhook URL")

    # Configuration for the Settings loader
    model_config = SettingsConfigDict(
        # Looks for a .env file in the project root
        env_file=".env",
        # Ensures variables are case-insensitive (e.g., VAULT_URL or vault_url)
        env_file_encoding="utf-8",
        # Ignores extra environment variables not defined here
        extra="ignore"
    )

# Instantiate as a singleton to be imported across the project
settings = Settings()