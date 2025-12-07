"""
Contract Analysis schemas for structured output
"""

from typing import List
from pydantic import BaseModel, Field


class ClauseAnalysisResponse(BaseModel):
    """Structured response schema for clause analysis using Pydantic for type safety"""
    has_clause: bool = Field(..., description="Whether the contract text contains clauses related to BGB sections")
    explanation: str = Field(..., description="Brief explanation (1-2 sentences) of the analysis")


class FoundClause(BaseModel):
    """A single found clause with contract content and analysis"""
    contract_content: str = Field(..., description="The contract text where the clause was found")
    analysis: str = Field(..., description="Analysis explaining the clause and its relation to BGB sections")


class BatchClauseAnalysisResponse(BaseModel):
    """Structured response schema for batch clause analysis"""
    found_clauses: List[FoundClause] = Field(..., description="List of found clauses with their analysis")

