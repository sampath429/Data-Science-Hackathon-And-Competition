"""
src/sf_client.py
Handles Salesforce authentication and REST API operations.
Integrates with Azure Key Vault for secret management.
"""

import httpx
import logging
from typing import Dict, Any
from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient
from config import settings
from schemas.models import SalesforceCase, SalesforceCustomer, VehicleHistory

logger = logging.getLogger(__name__)

class SalesforceClient:
    def __init__(self):
        self.api_version = "v59.0"
        self.base_url = f"{settings.sf_instance_url}/services/data/{self.api_version}"
        self._access_token: str | None = None

    async def _get_vault_secret(self, secret_name: str) -> str:
        """Fetches Client ID/Secret from Azure Key Vault."""
        async with DefaultAzureCredential() as credential:
            client = SecretClient(vault_url=settings.vault_url, credential=credential)
            secret = await client.get_secret(secret_name)
            return secret.value

    async def authenticate(self):
        """
        Authenticates via OAuth2 Client Credentials flow.
        Secrets are pulled dynamically from Azure Key Vault.
        """
        logger.info("Authenticating with Salesforce via Azure Key Vault secrets...")
        client_id = await self._get_vault_secret("SF-CLIENT-ID")
        client_secret = await self._get_vault_secret("SF-CLIENT-SECRET")
        
        token_url = f"{settings.sf_instance_url}/services/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            self._access_token = response.json().get("access_token")
            logger.info("Salesforce authentication successful.")

    @property
    def headers(self) -> Dict[str, str]:
        if not self._access_token:
            raise RuntimeError("Access token missing. Call authenticate() first.")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }

    async def fetch_case_context(self, case_id: str) -> SalesforceCase:
        """
        Context Gathering: Fetches Case and performs 'Data Traversal' 
        to find related Vehicle History.
        """
        async with httpx.AsyncClient() as client:
            # 1. Fetch Primary Case Data
            case_resp = await client.get(
                f"{self.base_url}/sobjects/Case/{case_id}", 
                headers=self.headers
            )
            case_resp.raise_for_status()
            case_raw = case_resp.json()

            # 2. Data Traversal: Fetch Vehicle History using Custom Field
            # This demonstrates handling custom Salesforce objects (__c)
            vehicle_history = None
            vin = case_raw.get("Vehicle_VIN__c")
            
            if vin:
                query = f"SELECT VIN__c, Last_Service_Date__c, Repair_Notes__c FROM Vehicle__c WHERE VIN__c='{vin}' LIMIT 1"
                veh_resp = await client.get(
                    f"{self.base_url}/query?q={query}", 
                    headers=self.headers
                )
                records = veh_resp.json().get("records", [])
                if records:
                    vehicle_history = VehicleHistory(**records[0])

            # 3. Assemble the full Pydantic Context
            return SalesforceCase(
                **case_raw,
                vehicle_history=vehicle_history
            )

    async def write_back(self, case_id: str, summary: str):
        """
        Egress: Updates the Salesforce Case and creates a Task.
        """
        async with httpx.AsyncClient() as client:
            # Update Case Technical Summary field
            logger.info(f"Updating Case {case_id} with technical summary...")
            await client.patch(
                f"{self.base_url}/sobjects/Case/{case_id}",
                headers=self.headers,
                json={"Technical_Summary__c": summary}
            )

            # Create Follow-up Task for a human technician
            logger.info("Creating follow-up task in Salesforce...")
            task_payload = {
                "Subject": "Review AI-Generated Repair Procedure",
                "WhatId": case_id,
                "OwnerId": settings.default_tech_id,
                "Status": "Not Started",
                "Priority": "High"
            }
            await client.post(
                f"{self.base_url}/sobjects/Task",
                headers=self.headers,
                json=task_payload
            )