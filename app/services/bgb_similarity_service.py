"""
BGB Similarity Search Service
Searches for similar BGB sections using vector similarity.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func
import numpy as np

from app.db.models.bgb_embedding import BGBEmbedding

logger = logging.getLogger(__name__)


class BGBSimilarityService:
    """
    Service for similarity searching BGB embeddings.
    """
    
    def __init__(self, top_k: int = 5, similarity_threshold: float = 0.5):
        """
        Initialize similarity service.
        
        Args:
            top_k: Number of top similar sections to return
            similarity_threshold: Minimum cosine similarity (0-1, default 0.5 for moderate similarity)
        """
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
    
    async def search_similar(
        self,
        db: AsyncSession,
        query_embedding: List[float],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar BGB sections using cosine similarity.
        
        Args:
            db: Database session
            query_embedding: Query embedding vector (1536 dimensions)
            top_k: Number of results to return (defaults to self.top_k)
            
        Returns:
            List of similar BGB sections with metadata
        """
        if top_k is None:
            top_k = self.top_k
        
        # Convert to numpy array for cosine similarity calculation
        query_vector = np.array(query_embedding, dtype=np.float32)
        
        # Normalize query vector for cosine similarity
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []
        query_vector = query_vector / query_norm
        
        # Build query with cosine distance (pgvector uses <-> for cosine distance)
        # Order by cosine distance (ascending = most similar)
        # Use a larger limit to account for threshold filtering, but not too large
        limit = max(top_k * 2, 20)  # Get enough candidates for threshold filtering
        query = (
            select(BGBEmbedding)
            .order_by(BGBEmbedding.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        
        result = await db.execute(query)
        bgb_embeddings = result.scalars().all()
        
        # Calculate similarity scores and filter
        similar_sections = []
        all_similarities = []  # Track all similarities for logging
        
        for bgb_embedding in bgb_embeddings:
            # Get embedding vector
            embedding_vector = np.array(bgb_embedding.embedding, dtype=np.float32)
            embedding_norm = np.linalg.norm(embedding_vector)
            
            if embedding_norm == 0:
                continue
            
            # Calculate cosine similarity
            embedding_vector = embedding_vector / embedding_norm
            similarity = float(np.dot(query_vector, embedding_vector))
            all_similarities.append(similarity)
            
            # Filter by threshold
            if similarity < self.similarity_threshold:
                continue
            
            similar_sections.append({
                'section_number': bgb_embedding.section_number,
                'book': bgb_embedding.book,
                'book_title': bgb_embedding.book_title,
                'division': bgb_embedding.division,
                'division_title': bgb_embedding.division_title,
                'title': bgb_embedding.title,
                'content': bgb_embedding.content,
                'contextual_text': bgb_embedding.contextual_text,
                'similarity': similarity
            })
            
            # Stop if we have enough results
            if len(similar_sections) >= top_k:
                break
        
        # Log statistics
        if all_similarities:
            max_sim = max(all_similarities)
            min_sim = min(all_similarities)
            avg_sim = sum(all_similarities) / len(all_similarities)
            logger.info(
                f"Similarity search: found {len(similar_sections)}/{len(bgb_embeddings)} sections "
                f"above threshold {self.similarity_threshold:.2f} "
                f"(max: {max_sim:.3f}, min: {min_sim:.3f}, avg: {avg_sim:.3f})"
            )
        else:
            logger.warning(f"No BGB embeddings found in database")
        
        return similar_sections
    
    async def search_batch(
        self,
        db: AsyncSession,
        query_embeddings: List[List[float]],
        top_k: Optional[int] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Search for similar BGB sections for multiple query embeddings.
        
        Args:
            db: Database session
            query_embeddings: List of query embedding vectors
            top_k: Number of results per query
            
        Returns:
            List of lists of similar sections (one list per query)
        """
        results = []
        for embedding in query_embeddings:
            similar = await self.search_similar(db, embedding, top_k)
            results.append(similar)
        
        return results

