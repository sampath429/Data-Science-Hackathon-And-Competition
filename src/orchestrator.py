"""
src/orchestrator.py
The main workflow controller for the Salesforce Service Agent.
Coordinates the 'Closed-Loop' logic: Ingress Context -> RAG Analysis -> Egress.
"""

import logging
import httpx
from src.config import settings
from src.sf_client import SalesforceClient
from src.rag_engine import RAGEngine
from schemas.models import TechnicalAnalysis

# Configure logging
logger = logging.getLogger(__name__)

class ServiceAgentOrchestrator:
    def __init__(self):
        self.sf_client = SalesforceClient()
        self.rag_engine = RAGEngine()

    async def _alert_critical_sentiment(self, analysis: TechnicalAnalysis):
        """
        EGRESS: External Notification
        Posts a structured alert to Microsoft Teams/Slack if a safety risk is detected.
        """
        logger.warning(f"CRITICAL FAULT DETECTED: Case {analysis.case_id}")
        
        # Formatting the payload for Teams/Slack Webhooks
        payload = {
            "text": (
                f"🚨 *CRITICAL SAFETY ALERT*\n"
                f"**Case ID:** {analysis.case_id}\n"
                f"**Sentiment:** {analysis.sentiment}\n"
                f"**Suggested Action:** {analysis.likely_solution}\n"
                f"**Confidence:** {analysis.confidence_score * 100}%\n"
                f"--- \n"
                f"A high-priority Task has been created for the Lead Technician."
            )
        }

        async with httpx.AsyncClient() as client:
            try:
                # We use the notification URL from our centralized config
                response = await client.post(settings.notif_webhook_url, json=payload)
                response.raise_for_status()
                logger.info("External critical notification sent successfully.")
            except Exception as e:
                # We log this but don't 'raise' it. 
                # We don't want a notification failure to roll back the Salesforce update.
                logger.error(f"External notification failed: {e}")

    async def run_closed_loop(self, case_id: str):
        """
        The Core Loop Execution:
        1. Authenticate with Salesforce.
        2. Gather Context (Data Traversal).
        3. Analyze via RAG (Intelligence).
        4. Write-back to Salesforce (Egress).
        5. Trigger Alert if Critical (Egress).
        """
        try:
            # 1. AUTHENTICATION
            # Ensures we have a valid Bearer token for this execution run
            await self.sf_client.authenticate()

            # 2. INGRESS & CONTEXT GATHERING
            # Traverses Salesforce relationships to get Case + Vehicle History
            case_context = await self.sf_client.fetch_case_context(case_id)

            # 3. ANALYSIS (RAG)
            # Queries Azure Search and GPT-4o for a technical solution
            analysis_result = await self.rag_engine.analyze_case(case_context)
            
            # 4. EGRESS: SALESFORCE WRITE-BACK
            # Updates the Case record and creates a Technician Task
            await self.sf_client.write_back(
                case_id=case_id,
                summary=analysis_result.technical_summary
            )

            # 5. EGRESS: EXTERNAL NOTIFICATION
            # Final check to see if we need to alert the human team immediately
            if analysis_result.sentiment.lower() == "critical":
                await self._alert_critical_sentiment(analysis_result)

            logger.info(f"Successfully closed the loop for Case {case_id}")

        except Exception as e:
            # CRITICAL: We raise the error here so the 'worker.py' knows
            # to keep the message in the Service Bus for a retry.
            logger.error(f"Error in Orchestration Loop for Case {case_id}: {str(e)}")
            raise e