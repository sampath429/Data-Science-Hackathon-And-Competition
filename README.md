
# Salesforce Service Agent: "Closed-Loop" RAG Automation

This repository contains a production-ready Python implementation of an Agentic workflow designed to automate automotive service cases. The system identifies high-priority technical faults in Salesforce, retrieves technical repair procedures via a RAG (Retrieval-Augmented Generation) pipeline, and executes automated write-backs.

## 🏗️ Architecture Overview

The solution follows a **Cloud-Native, Async-First** architecture optimized for the Azure ecosystem.

## Deployment & Endpoint Hosting
To make this agent "live," it is deployed as a FastAPI web service.

Deployment Path: Azure App Service / Functions
Hosting: The code in app.py is hosted on Azure App Service.

Endpoint: Once deployed, the agent exposes a public URL: https://<your-app-name>.azurewebsites.net/trigger.

Security: The endpoint is secured via Managed Identity, ensuring only authorized triggers (like Salesforce) can initiate the workflow.

### Ingress: Identifying New Cases
The system identifies a new case via two primary architectural patterns. This implementation is optimized for Method A.

Method A: Push (The "Doorbell" Approach)
Mechanism: Salesforce "pushes" the data to the Agent's endpoint in real-time.

Setup: A Salesforce Record-Triggered Flow is configured. When a "Technical Fault" case is created, the Flow fires an HTTP Callout to the /trigger endpoint.

Pros: Real-time processing, zero idle compute costs.

Method B: Pull/Polling (The "Mailbox" Approach)
Mechanism: The Agent "pulls" data by asking Salesforce for new records on a schedule.

Setup: A cron job or Azure Function Timer Trigger runs a SOQL query: SELECT Id FROM Case WHERE Status = 'New' AND Priority = 'High'.

Pros: Easier to manage rate limits; doesn't require a public-facing endpoint for Salesforce to hit.

⚙️ Salesforce Configuration Options
To trigger this agent, you must configure one of the following within your Salesforce Org:

Option 1: Salesforce Flow (Recommended)
Trigger: Record-Triggered Flow on Case.

Condition: Status = 'New' AND Type = 'Technical Fault'.

Action: Create an External Service and use an HTTP Callout to send the CaseId to the Python API.

Option 2: Apex Trigger (Pro-Code)
For complex logic, use an Apex Trigger to invoke an @future or Queueable class that makes an HttpRequest to the Agent's URL.

### The "Closed-Loop" Workflow
1.  **Ingress:** A trigger identifies a new "Technical Fault" Case in Salesforce.
2.  **Context Gathering:** The agent performs **Data Traversal** using the Salesforce REST API to fetch full Case details and associated `Vehicle_History__c`.
3.  **Analysis (RAG):**
    * **Vector Retrieval:** Queries **Azure AI Search** for technical manuals (PDF/Markdown) using semantic embeddings.
    * **Synthesis:** **Azure OpenAI (GPT-4o)** synthesizes a solution based on the specific vehicle history and manual excerpts.
4.  **Egress:**
    * **Salesforce Update:** Updates the Case with a Technical Summary.
    * **Human-in-the-loop:** Creates a Follow-up Task for a human technician.
    * **Critical Alerting:** Posts to Slack/Teams if the sentiment is identified as "Critical."

---

## 📁 Repository Structure

```text
├── schemas/
│   └── models.py          # Pydantic V2 data contracts & validation
├── src/
│   ├── config.py          # Centralized configuration (Pydantic Settings)
│   ├── sf_client.py       # Salesforce REST API & OAuth2 (Key Vault)
│   ├── rag_engine.py      # Azure AI Search & Azure OpenAI integration
│   └── orchestrator.py    # Main workflow controller & error handling
├── .env                   # Local environment variables (not for production)
├── requirements.txt       # Project dependencies
└── README.md              # Technical documentation
```

---

## 🛠️ Technical Decisions & Constraints

### 1. API Authentication & Security
The system utilizes the **OAuth 2.0 Client Credentials Flow**. 
* **Azure Key Vault:** Sensitive credentials (`Client ID` and `Client Secret`) are never hardcoded or stored in environment variables. They are fetched at runtime using `sf_client.py`.
* **Managed Identity:** The implementation uses `DefaultAzureCredential`, allowing the agent to authenticate with Azure services without managing local service principal keys.

### 2. Data Mapping Strategy
We use **Pydantic** to map Salesforce's custom field naming conventions (e.g., `Vehicle_VIN__c`) to clean Pythonic attributes.
* **Validation:** Pydantic ensures that incoming data adheres to expected types before reaching the LLM, preventing "Garbage In, Garbage Out" scenarios.
* **Aliasing:** Using `Field(alias=...)` allows for seamless integration with Salesforce JSON payloads while maintaining PEP8 naming standards in the logic.

### 3. State Persistence & Fault Tolerance
To ensure no data is lost if the Salesforce API is down:
* **Azure Service Bus:** In a production deployment, the `orchestrator.py` should be triggered by an Azure Service Bus Queue.
* **Retry Policy:** If a network error occurs during the "Egress" phase, the orchestrator raises an exception. This triggers the Service Bus **Exponential Backoff** retry mechanism.
* **Idempotency:** The "Write-back" function is designed to update existing records, ensuring that multiple retries do not create duplicate service cases.

---

## 🚀 Deployment Guide

### Prerequisites
* Python 3.10+
* Azure Subscription (Key Vault, AI Search, OpenAI)
* Salesforce Developer Sandbox

### Local Setup
1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure Environment:**
    Create a `.env` file based on the template in `src/config.py`.
3.  **Run the Agent:**
    ```bash
    python src/orchestrator.py
    ```

### Production Deployment (Azure)
1.  **Azure Functions:** Deploy the `src/` directory to an Azure Function App.
2.  **Key Vault:** Grant the Function's **Managed Identity** `Secret User` permissions on the Key Vault.
3.  **Service Bus:** Link a Queue trigger to the `orchestrator.run_closed_loop()` method to ensure state persistence.

---

## ⚖️ Standards Compliance
* **Formatting:** All code follows **PEP8** standards, formatted with **Black** and linted with **Ruff**.
* **Validation:** Strict schema enforcement via **Pydantic V2**.
* **Async I/O:** Fully asynchronous network operations using `httpx` and `azure-identity-aio`.