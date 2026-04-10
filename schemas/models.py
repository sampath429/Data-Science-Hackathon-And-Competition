"""
schemas/models.py
Defines the data contract for the Salesforce Service Agent.
Uses Pydantic for validation and alias mapping.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class SalesforceBaseModel(BaseModel):
    """Base config to allow population by field name or alias."""
    model_config = ConfigDict(populate_by_name=True)


class SalesforceCustomer(SalesforceBaseModel):
    """Represents the associated Customer/Contact details."""
    contact_id: str = Field(alias="Id")
    full_name: str = Field(alias="Name")
    email: Optional[str] = Field(None, alias="Email")


class VehicleHistory(SalesforceBaseModel):
    """Represents the vehicle history linked to the case."""
    vin: str = Field(alias="VIN__c")
    last_service_date: Optional[datetime] = Field(None, alias="Last_Service_Date__c")
    mileage: int = Field(0, alias="Current_Mileage__c")
    previous_repairs: List[str] = Field(default_factory=list, alias="Repair_Notes__c")


class SalesforceCase(SalesforceBaseModel):
    """The core Case object retrieved from Salesforce REST API."""
    case_id: str = Field(alias="Id")
    case_number: str = Field(alias="CaseNumber")
    subject: str = Field(alias="Subject")
    description: Optional[str] = Field(None, alias="Description")
    priority: str = Field(alias="Priority")
    status: str = Field(alias="Status")
    # Nested context gathered via API traversal
    customer: Optional[SalesforceCustomer] = None
    vehicle_history: Optional[VehicleHistory] = None


class TechnicalAnalysis(BaseModel):
    """Output of the RAG-based analysis phase."""
    case_id: str
    likely_solution: str
    technical_summary: str
    confidence_score: float
    sentiment: str = "Normal"  # Normal, Critical, etc.
    suggested_parts: List[str] = Field(default_factory=list)


# class SalesforceTask(SalesforceBaseModel):
#     """Schema for creating a follow-up Task in Salesforce Egress."""
#     subject: str = "Follow-up: Technical Fault Repair"
#     priority: str = "High"
#     status: str = "Not Started"
#     owner_id: str = Field(description="ID of the human technician")
#     what_id: str = Field(description="The Case ID this task is linked to")
#     description: str