"""
app.py
The entry point for the Agent. Acts as the REST endpoint for Salesforce.
Receives triggers and hands them off to the orchestrator.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from src.orchestrator import ServiceAgentOrchestrator
from src.config import settings
import logging

# Initialize FastAPI app and Orchestrator
app = FastAPI(title="Salesforce Service Agent API")
orchestrator = ServiceAgentOrchestrator()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SalesforceTrigger(BaseModel):
    """Schema for the incoming Salesforce webhook."""
    case_id: str
    priority: str = "High"

@app.get("/health")
async def health_check():
    """Endpoint for Azure App Service health monitoring."""
    return {"status": "healthy"}

@app.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def handle_new_case(payload: SalesforceTrigger, background_tasks: BackgroundTasks):
    """
    Ingress Point: Receives Case ID from Salesforce.
    The '202 Accepted' response is sent immediately to Salesforce 
    to prevent timeout while the agent works in the background.
    """
    logger.info(f"Received trigger for Case ID: {payload.case_id}")
    
    if not payload.case_id:
        raise HTTPException(
            status_code=400, 
            detail="Missing case_id in payload"
        )

    # Hand off the heavy lifting to the background worker
    # In a full Azure setup, this task would be pushed to Azure Service Bus here
    background_tasks.add_task(orchestrator.run_closed_loop, payload.case_id)
    
    return {
        "message": "Case received and analysis initiated",
        "case_id": payload.case_id
    }

if __name__ == "__main__":
    import uvicorn
    # Local run command: python app.py
    uvicorn.run(app, host="0.0.0.0", port=8000)