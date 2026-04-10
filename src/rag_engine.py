"""
src/rag_engine.py
RAG-based analysis engine using Azure AI Search and Azure OpenAI.
Processes case context to identify solutions from technical documentation.
"""

import json
import logging
from typing import List
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI
from config import settings
from schemas.models import SalesforceCase, TechnicalAnalysis

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        self.credential = DefaultAzureCredential()
        
        # Azure AI Search Client - For retrieving technical manual chunks
        self.search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            credential=self.credential
        )
        
        # Azure OpenAI Client - For reasoning and synthesis
        self.llm_client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version="2024-02-15-preview",
            credential=self.credential
        )

    async def _get_embeddings(self, text: str) -> List[float]:
        """Generates vector embeddings for semantic search queries."""
        response = await self.llm_client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    async def _retrieve_technical_context(self, query: str) -> str:
        """
        Performs a hybrid search (semantic + keyword) in Azure AI Search.
        Focuses on 'Technical Manuals' and 'Repair Procedures'.
        """
        vector_query = VectorizedQuery(
            vector=await self._get_embeddings(query), 
            k_nearest_neighbors=3, 
            fields="content_vector"
        )
        
        # Querying the vector store
        results = await self.search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["title", "content", "procedure_id"],
            top=3
        )
        
        docs = []
        async for result in results:
            docs.append(f"Manual: {result['title']}\nProcedure: {result['content']}")
        
        return "\n\n".join(docs) if docs else "No specific repair procedure found in database."

    async def analyze_case(self, case: SalesforceCase) -> TechnicalAnalysis:
        """
        The core RAG loop:
        1. Query Formulation
        2. Context Retrieval
        3. LLM Synthesis (JSON Mode)
        """
        logger.info(f"Analyzing case {case.case_id} using RAG...")

        # 1. Formulate a search query using Case context
        search_query = f"Technical fault: {case.subject}. Symptoms: {case.description}"
        
        # 2. Retrieve technical manual excerpts
        technical_context = await self._retrieve_technical_context(search_query)

        # 3. Generate structured analysis using LLM
        system_prompt = """
        You are a Senior Automotive Technical Lead. 
        Analyze the customer case using the provided technical manual context.
        Return a JSON object matching the TechnicalAnalysis schema.
        
        Determine 'sentiment' as 'Critical' only if the fault poses a safety risk (e.g., brakes, steering, fuel leak).
        """

        user_content = f"""
        CASE DATA:
        Subject: {case.subject}
        Description: {case.description}
        Vehicle History: {case.vehicle_history.previous_repairs if case.vehicle_history else 'No prior history.'}

        TECHNICAL MANUAL CONTEXT:
        {technical_context}
        """

        response = await self.llm_client.chat.completions.create(
            model="gpt-4o", # Azure OpenAI Deployment Name
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )

        # Parse and validate the response against our Pydantic schema
        llm_json = json.loads(response.choices[0].message.content)
        
        return TechnicalAnalysis(
            case_id=case.case_id,
            **llm_json
        )