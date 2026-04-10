## OAuth 2.0 Client Credentials Flow

The agent uses the **Client Credentials Flow**, which is ideal for server-to-server integrations where no human interaction is required.

### 1. Architectural Overview
The flow involves three main entities:
* **The Agent (Client):** The Azure-hosted Python application.
* **Azure Key Vault (Secret Store):** Secure storage for Salesforce credentials.
* **Salesforce (Identity Provider):** The service that issues the access token.



---

### 2. Step-by-Step Execution

| Step | Action | Description |
| :--- | :--- | :--- |
| **1** | **Secret Retrieval** | The Agent uses **Managed Identity** to request the `SF-CLIENT-ID` and `SF-CLIENT-SECRET` from Azure Key Vault. |
| **2** | **Token Request** | The Agent sends an asynchronous `POST` request to the Salesforce OAuth2 token endpoint (`/services/oauth2/token`). |
| **3** | **Validation** | Salesforce validates the client credentials and the user permissions associated with the Connected App. |
| **4** | **Token Issue** | Salesforce returns a JSON payload containing an `access_token` and the `instance_url`. |
| **5** | **API Call** | The Agent includes the token in the `Authorization: Bearer <token>` header for all subsequent REST API calls. |

---

### 3. Error Handling & Persistence

To maintain a "Closed-Loop" operation, the authentication logic includes specific safety measures:

* **Token Expiry:** If a request returns a `401 Unauthorized` error, the `sf_client.py` is designed to catch the exception, clear the cached token, and attempt a re-authentication.
* **Service Unavailability:** If the Salesforce Identity service is down, the orchestrator raises a connection error. This allows the **Azure Service Bus Queue** to hold the message and retry the authentication after a backoff period, ensuring no data loss.
* **Lease Security:** By using short-lived Access Tokens and fetching secrets only when needed, we minimize the attack surface of the integration.

---

### 4. Implementation Snippet
The following logic in `src/sf_client.py` manages this flow:

```python
async def authenticate(self):
    # Fetch secrets from Vault (Managed Identity)
    client_id = await self._get_vault_secret("SF-CLIENT-ID")
    client_secret = await self._get_vault_secret("SF-CLIENT-SECRET")
    
    # Exchange for Bearer Token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.sf_instance_url}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            }
        )
        response.raise_for_status()
        self._access_token = response.json().get("access_token")
```