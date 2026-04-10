This file is a crucial piece of documentation for your submission. It demonstrates to the interviewer that you have a deep understanding of the **Schema Alignment** between the Salesforce object model and the AI's internal data structures.

### `docs/data_mapping.md`

# Data Mapping & Schema Alignment Strategy

This document outlines how data is transformed as it moves through the **Closed-Loop** system, from the initial Salesforce trigger to the RAG analysis and final write-back.

---

## 1. Field Mapping Table

The following table maps Salesforce API names to the internal Pydantic models used by the Agent.

| Salesforce Field (Source) | Internal Model Field | Data Type | Purpose |
| :--- | :--- | :--- | :--- |
| `Id` | `case_id` | String | Unique identifier for the loop |
| `Subject` | `subject` | String | Primary input for AI Search |
| `Description` | `description` | String | Technical detail for RAG context |
| `Vehicle_VIN__c` | `vin` | String | Key used for Data Traversal |
| `Vehicle__c.Repair_Notes__c` | `vehicle_history` | String | Historical context for diagnostic reasoning |

---

## 2. Ingress Data Traversal

To provide high-quality "Closed-Loop" feedback, the agent doesn't just look at the `Case` object. It performs a **Relational Traversal** to gather a 360-degree view of the vehicle's health.



### The Traversal Logic:
1. **Case Object:** Identifies the symptom (e.g., "Brakes squeaking").
2. **VIN Lookup:** Uses the `Vehicle_VIN__c` field to query the `Vehicle__c` custom object.
3. **History Extraction:** Pulls the last 3 repair notes to see if this is a recurring issue (e.g., "Pads replaced 2 weeks ago").

---

## 3. RAG Output Schema (The "Intelligence" Layer)

The RAG engine is forced to return a strictly structured JSON object. This ensures the `worker.py` can parse the data without errors.

**Model Name:** `TechnicalAnalysis`
```json
{
  "case_id": "500xx00000xxxx",
  "technical_summary": "Analysis of the brake system based on manual v4.2...",
  "likely_solution": "Replace rotors and recalibrate ABS sensor.",
  "sentiment": "Critical",
  "confidence_score": 0.94
}
```

---

## 4. Egress Write-Back Mapping

When the analysis is complete, the agent "closes the loop" by mapping the AI's findings back to Salesforce fields.

| AI Output Field | Salesforce Target Field | Action |
| :--- | :--- | :--- |
| `technical_summary` | `Technical_Summary__c` | **PATCH** Case Record |
| `likely_solution` | `Task.Description` | **POST** New Task |
| `sentiment` | `Notification` | **POST** Teams Webhook (if 'Critical') |

---

## 5. State Persistence & Data Integrity

* **Validation:** All incoming data is validated using **Pydantic**. If Salesforce sends a malformed `CaseId`, the `app.py` rejects it before it reaches the Service Bus.
* **Idempotency:** The mapping uses the `CaseId` as the primary key for all write-backs. If the agent runs twice for the same case, the `Technical_Summary__c` field is simply updated/overwritten, preventing duplicate data entry.



---

### Why this matters for the Assessment:
This mapping proves that the system is **Context-Aware**. By linking Case symptoms to Vehicle History, the AI provides a much more accurate "Likely Solution" than a simple chatbot would. It transforms the AI from a general tool into a specialized **Automotive Diagnostic Agent**.