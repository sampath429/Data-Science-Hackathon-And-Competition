"""
src/rag_engine.py
Core RAG Analysis Engine.
Retrieves technical context from Azure AI Search and reasons via Azure OpenAI.
"""

import json
import logging
from typing import List
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI
from src.config import settings
from schemas.models import SalesforceCase, TechnicalAnalysis

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        # Using DefaultAzureCredential for Managed Identity support in Production
        self.credential = DefaultAzureCredential()
        
        # Azure AI Search - Knowledge Base
        self.search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            credential=self.credential
        )
        
        # Azure OpenAI - Synthesis and Reasoning
        self.llm_client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version="2024-02-15-preview",
            credential=self.credential
        )

    async def _get_embeddings(self, text: str) -> List[float]:
        """Converts query text into a vector for semantic search."""
        response = await self.llm_client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    async def _retrieve_context(self, query: str) -> str:
        """
        Performs Hybrid Search (Vector + Keyword) in Azure AI Search.
        """
        vector_query = VectorizedQuery(
            vector=await self._get_embeddings(query), 
            k_nearest_neighbors=3, 
            fields="content_vector"
        )
        
        async with self.search_client:
            results = await self.search_client.search(
                search_text=query, # Hybrid: Keyword part
                vector_queries=[vector_query], # Hybrid: Vector part
                select=["title", "content"],
                top=3
            )
            
            docs = []
            async for result in results:
                docs.append(f"Source: {result['title']}\nContent: {result['content']}")
            
            return "\n\n".join(docs) if docs else "No technical manual entry found."

    async def analyze_case(self, case: SalesforceCase) -> TechnicalAnalysis:
        """
        The RAG Logic:
        1. Formulate search query.
        2. Retrieve context from manuals.
        3. Synthesize structured TechnicalAnalysis.
        """
        logger.info(f"RAG Analysis started for Case {case.case_id}")

        # 1. Hybrid Search in Vector DB
        search_query = f"{case.subject} {case.description}"
        technical_context = await self._retrieve_context(search_query)

        # 2. LLM Reasoning with System Instruction
        system_prompt = (
            "You are a Senior Automotive Diagnostic AI. "
            "Analyze the case and technical context to provide a solution. "
            "IMPORTANT: If the fault involves brakes, steering, or fire risk, "
            "set 'sentiment' to 'Critical'. Otherwise, set it to 'Normal'. "
            "Return ONLY a JSON object matching the requested schema."
        )

        user_prompt = f"""
        CASE DATA:
        Subject: {case.subject}
        Description: {case.description}
        Vehicle History: {case.vehicle_history.repair_notes if case.vehicle_history else 'No history'}

        TECHNICAL MANUALS:
        {technical_context}
        """

        response = await self.llm_client.chat.completions.create(
            model="gpt-4o", # Azure Deployment Name
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )

        # 3. Validation & Parsing
        raw_json = json.loads(response.choices[0].message.content)
        
        # Map to Pydantic for strict validation
        return TechnicalAnalysis(
            case_id=case.case_id,
            technical_summary=raw_json.get("technical_summary", ""),
            likely_solution=raw_json.get("likely_solution", ""),
            sentiment=raw_json.get("sentiment", "Normal"),
            confidence_score=raw_json.get("confidence_score", 0.0)
        )