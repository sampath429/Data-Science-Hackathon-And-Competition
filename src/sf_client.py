"""
src/sf_client.py
Handles Salesforce authentication, complex data retrieval, and write-backs.
Uses httpx for high-performance async I/O.
"""

import httpx
import logging
from typing import Dict, Any, Optional
from src.config import settings
from schemas.models import SalesforceCase, VehicleHistory

logger = logging.getLogger(__name__)

class SalesforceClient:
    def __init__(self):
        self.api_version = "v59.0"
        self.base_url = f"{settings.sf_instance_url}/services/data/{self.api_version}"
        self._access_token: Optional[str] = None

    async def authenticate(self):
        """
        Authenticates via OAuth 2.0 Client Credentials flow.
        Retrieves secrets via the config singleton (Settings).
        """
        logger.info("Authenticating with Salesforce...")
        token_url = f"{settings.sf_instance_url}/services/oauth2/token"
        
        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.sf_client_id,
            "client_secret": settings.sf_client_secret
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(token_url, data=payload)
                response.raise_for_status()
                data = response.json()
                self._access_token = data.get("access_token")
                logger.info("Salesforce authentication successful.")
            except httpx.HTTPStatusError as e:
                logger.error(f"Auth failed: {e.response.status_code} - {e.response.text}")
                raise

    @property
    def headers(self) -> Dict[str, str]:
        """Helper to generate Auth headers for REST calls."""
        if not self._access_token:
            raise RuntimeError("No access token. Call authenticate() first.")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }

    async def fetch_case_context(self, case_id: str) -> SalesforceCase:
        """
        INGRESS/CONTEXT GATHERING:
        1. Fetches the primary Case record.
        2. Performs 'Data Traversal' to find related Vehicle History.
        """
        async with httpx.AsyncClient() as client:
            # 1. Fetch Primary Case
            case_resp = await client.get(
                f"{self.base_url}/sobjects/Case/{case_id}", 
                headers=self.headers
            )
            case_resp.raise_for_status()
            case_data = case_resp.json()

            # 2. Data Traversal: Find history based on custom VIN field
            vin = case_data.get("Vehicle_VIN__c")
            vehicle_history = None

            if vin:
                logger.info(f"Traversing data for VIN: {vin}")
                # SOQL Query to find custom object records
                query = f"SELECT VIN__c, Last_Service_Date__c, Repair_Notes__c FROM Vehicle__c WHERE VIN__c='{vin}' LIMIT 1"
                query_url = f"{settings.sf_instance_url}/services/data/{self.api_version}/query?q={query}"
                
                veh_resp = await client.get(query_url, headers=self.headers)
                records = veh_resp.json().get("records", [])
                if records:
                    vehicle_history = VehicleHistory(**records[0])

            # 3. Return a validated Pydantic model
            return SalesforceCase(
                case_id=case_id,
                subject=case_data.get("Subject"),
                description=case_data.get("Description"),
                vehicle_history=vehicle_history
            )

    async def write_back(self, case_id: str, summary: str):
        """
        EGRESS: Updates the Case with AI results and creates a human Task.
        This closes the loop.
        """
        async with httpx.AsyncClient() as client:
            # A. Update the Case technical field
            update_payload = {"Technical_Summary__c": summary}
            patch_resp = await client.patch(
                f"{self.base_url}/sobjects/Case/{case_id}",
                headers=self.headers,
                json=update_payload
            )
            patch_resp.raise_for_status()
            logger.info(f"Case {case_id} updated with AI summary.")

            # B. Create a Follow-up Task for the technician
            task_payload = {
                "Subject": "Review AI-Generated Repair Procedure",
                "WhatId": case_id,
                "OwnerId": settings.default_tech_id,
                "Status": "Not Started",
                "Priority": "High"
            }
            task_resp = await client.post(
                f"{self.base_url}/sobjects/Task",
                headers=self.headers,
                json=task_payload
            )
            task_resp.raise_for_status()
            logger.info(f"Technician Task created for Case {case_id}.")