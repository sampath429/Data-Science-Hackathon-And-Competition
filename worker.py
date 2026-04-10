"""
worker.py
The background consumer process that executes the 'Closed-Loop' logic.
Handles message retrieval, retries, and final acknowledgment.
"""

 import asyncio
import logging
from azure.servicebus.aio import ServiceBusClient
from src.orchestrator import ServiceAgentOrchestrator
from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - WORKER - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def run_worker():
    """
    Main worker loop. 
    Listens to Service Bus and triggers the orchestrator for each message.
    """
    orchestrator = ServiceAgentOrchestrator()
    
    # Initialize Service Bus Client
    client = ServiceBusClient.from_connection_string(
        settings.sb_conn_str, 
        logging_enable=False
    )

    async with client:
        # 'peek_lock' mode is default: the message is hidden from others 
        # but stays in the queue until we explicitly 'complete' it.
        receiver = client.get_receiver(queue_name="case-inbound-queue")
        
        async with receiver:
            logger.info("Worker started successfully. Listening for Salesforce cases...")
            
            async for msg in receiver:
                case_id = str(msg)
                logger.info(f"Retrieved Case {case_id} from queue. Starting analysis...")
                
                try:
                    # ---------------------------------------------------------
                    # THE CLOSED-LOOP EXECUTION
                    # ---------------------------------------------------------
                    # This calls: Ingress -> RAG -> Egress (Salesforce/Teams)
                    await orchestrator.run_closed_loop(case_id)
                    
                    # If we reach here, everything succeeded.
                    # Remove the message from the queue permanently.
                    await receiver.complete_message(msg)
                    logger.info(f"Successfully completed Closed-Loop for Case {case_id}")

                except Exception as e:
                    # STATE PERSISTENCE LOGIC:
                    # If an error occurs (e.g., Salesforce API is down), we 'abandon'
                    # the message. It will reappear in the queue for a retry.
                    logger.error(f"Execution failed for Case {case_id}: {str(e)}")
                    logger.info(f"Abandoning message {case_id} for automatic retry.")
                    
                    await receiver.abandon_message(msg)

async def main():
    """Entry point for the worker process."""
    try:
        await run_worker()
    except KeyboardInterrupt:
        logger.info("Worker shutting down gracefully...")
    except Exception as e:
        logger.critical(f"Worker crashed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())