"""
app.py
The Ingress point for the Salesforce Service Agent.
Responsible for receiving webhooks, validating data, and persisting state.
"""

import logging
from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from src.config import settings

# Initialize FastAPI
app = FastAPI(
    title="Salesforce Service Agent - Ingress API",
    description="REST endpoint for Salesforce Record-Triggered Flows"
)

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SalesforceTrigger(BaseModel):
    """
    Schema for the incoming Salesforce webhook payload.
    Ensures Case ID is present before we even attempt to queue it.
    """
    case_id: str
    priority: str = "High"

async def get_sb_client():
    """Dependency to provide a Service Bus Client."""
    client = ServiceBusClient.from_connection_string(
        settings.sb_conn_str, 
        logging_enable=False
    )
    try:
        yield client
    finally:
        await client.close()

@app.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def handle_salesforce_webhook(
    payload: SalesforceTrigger, 
    sb_client: ServiceBusClient = Depends(get_sb_client)
):
    """
    Ingress Point: Receives Case ID from Salesforce.
    
    Persistence Logic:
    1. Validates the Case ID.
    2. Pushes Case ID to Azure Service Bus (The 'Persistence Layer').
    3. Returns 202 Accepted immediately to Salesforce.
    """
    logger.info(f"Incoming request from Salesforce for Case: {payload.case_id}")
    
    if not payload.case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Missing required Case ID."
        )

    try:
        # Step 1: Push to Queue
        # This ensures the 'state' of the work is saved in Azure cloud
        sender = sb_client.get_queue_sender(queue_name="case-inbound-queue")
        async with sender:
            message = ServiceBusMessage(payload.case_id)
            await sender.send_messages(message)
            logger.info(f"Case {payload.case_id} successfully persisted to Service Bus.")
        
        # Step 2: Immediate Acknowledgment
        # Salesforce receives this and closes the connection, satisfied the task is 'Handed Off'
        return {
            "status": "accepted",
            "message": "Case queued for background analysis",
            "case_id": payload.case_id
        }
        
    except Exception as e:
        logger.error(f"Persistence Failure for Case {payload.case_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System failed to persist case data. Logic loop interrupted."
        )

@app.get("/health")
async def health():
    """Health check endpoint for Azure App Service monitoring."""
    return {"status": "up", "persistence": "active"}

if __name__ == "__main__":
    import uvicorn
    # Local run command: python app.py
    uvicorn.run(app, host="0.0.0.0", port=8000)