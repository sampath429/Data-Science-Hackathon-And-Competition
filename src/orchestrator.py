"""
src/orchestrator.py
The main orchestration logic for the Salesforce Service Agent.
Coordinates Ingress, Context Gathering, Analysis, and Egress.
"""

import asyncio
import logging
import httpx
from config import settings
from sf_client import SalesforceClient
from rag_engine import RAGEngine
from schemas.models import TechnicalAnalysis

# Initialize structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ServiceAgentOrchestrator:
    def __init__(self):
        self.sf_client = SalesforceClient()
        self.rag_engine = RAGEngine()

    async def _alert_critical_sentiment(self, analysis: TechnicalAnalysis):
        """
        Egress: Posts a notification to Slack/Teams if sentiment is 'Critical'.
        """
        logger.warning(f"CRITICAL SENTIMENT DETECTED for Case {analysis.case_id}")
        
        payload = {
            "text": (
                f"🚨 *Critical Technical Fault Identified*\n"
                f"*Case ID:* {analysis.case_id}\n"
                f"*Likely Solution:* {analysis.likely_solution}\n"
                f"*Confidence:* {analysis.confidence_score * 100}%\n"
                f"Please review the Salesforce Task assigned to the technician."
            )
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(settings.notif_webhook_url, json=payload)
                response.raise_for_status()
                logger.info("Notification successfully sent to external channel.")
            except Exception as e:
                logger.error(f"Failed to send critical notification: {e}")

    async def run_closed_loop(self, case_id: str):
        """
        Executes the full automated workflow.
        Ensures state persistence via exception raising (for Queue retries).
        """
        try:
            # 1. AUTHENTICATION
            # In production, this would use Cached tokens from Redis/CosmosDB
            await self.sf_client.authenticate()

            # 2. INGRESS & CONTEXT GATHERING
            logger.info(f"Gathering context for Case: {case_id}")
            case_context = await self.sf_client.fetch_case_context(case_id)

            # 3. ANALYSIS (RAG)
            logger.info("Starting RAG-based analysis phase...")
            analysis_result = await self.rag_engine.analyze_case(case_context)
            
            # 4. EGRESS: SALESFORCE WRITE-BACK
            logger.info("Performing Salesforce write-back...")
            await self.sf_client.write_back(
                case_id=case_id,
                summary=analysis_result.technical_summary
            )

            # 5. EGRESS: EXTERNAL NOTIFICATION
            if analysis_result.sentiment.lower() == "critical":
                await self._alert_critical_sentiment(analysis_result)

            logger.info(f"Closed-loop operation completed successfully for Case {case_id}.")

        except httpx.HTTPStatusError as e:
            # STATE PERSISTENCE LOGIC:
            # If Salesforce (or any API) is down, we log and raise the error.
            # When deployed as an Azure Function with a Service Bus trigger, 
            # raising this exception causes the message to be retried automatically.
            logger.error(f"Network error during execution: {e.response.status_code} - {e.response.text}")
            raise 
        except Exception as e:
            logger.critical(f"Unrecoverable error in orchestrator: {str(e)}")
            raise

async def main():
    """
    Entry point for manual testing.
    In production, this would be replaced by an Azure Function trigger.
    """
    # Replace with a valid Salesforce Case ID for integration testing
    test_case_id = "500xx00000xxxx" 
    
    orchestrator = ServiceAgentOrchestrator()
    await orchestrator.run_closed_loop(test_case_id)

if __name__ == "__main__":
    asyncio.run(main())