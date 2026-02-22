import os
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, 
    Distance, 
    PointStruct, 
    Filter, 
    FieldCondition, 
    MatchValue
)
from fastembed import TextEmbedding
from app.models.database import TranscriptSegment
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("services.vector_store")


class VectorStoreService:
    """Service for managing vector embeddings in Qdrant"""
    
    def __init__(self):
        self.qdrant_url = settings.qdrant_url
        self.collection_name = "transcriptions"
        self.vector_size = 384  # all-MiniLM-L6-v2 dimension
        self.model_cache_dir = os.getenv("QDRANT_MODEL_CACHE", "/app/models/qdrant")
        
        # Initialize Qdrant client
        self.client = QdrantClient(url=self.qdrant_url)
        
        # Initialize FastEmbed model
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        self.embedding_model = TextEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            cache_dir=self.model_cache_dir
        )
        
        logger.info("VectorStoreService initialized")
    
    def init_collection(self) -> bool:
        """Initialize Qdrant collection with correct configuration on startup"""
        try:
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            
            # Create payload index on user_id for multi-tenancy filtering
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="user_id",
                    field_schema="uuid"
                )
                logger.info("Created payload index on user_id")
            except Exception as e:
                # Index may already exist
                logger.debug(f"Payload index on user_id may already exist: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize collection: {e}")
            return False
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        try:
            embeddings = list(self.embedding_model.embed(texts))
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def _segment_to_point(self, segment: TranscriptSegment, embedding: List[float]) -> PointStruct:
        """Convert TranscriptSegment to Qdrant PointStruct"""
        return PointStruct(
            id=segment.id,
            vector=embedding,
            payload={
                "user_id": str(segment.user_id),
                "video_id": str(segment.video_id),
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "speaker_label": segment.speaker_label,
                "audio_emotion": segment.audio_emotion,
                "text_tone": segment.text_tone
            }
        )
    
    def upsert_segments(self, segments: List[TranscriptSegment]) -> bool:
        """Upsert transcript segments as vectors into Qdrant"""
        if not segments:
            logger.warning("No segments to upsert")
            return False
        
        try:
            # Get texts for embedding
            texts = [seg.text for seg in segments]
            
            # Generate embeddings
            embeddings = self._get_embeddings(texts)
            
            # Convert to Qdrant points
            points = [
                self._segment_to_point(segment, embedding)
                for segment, embedding in zip(segments, embeddings)
            ]
            
            # Upsert in batch
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"Upserted {len(segments)} segments to Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upsert segments: {e}")
            return False
    
    def search_segments(
        self, 
        query: str, 
        user_id: str,
        video_id: Optional[str] = None,
        limit: int = 5
    ) -> List[dict]:
        """Search segments with user_id and optional video_id filter for multi-tenancy"""
        try:
            # Generate query embedding
            query_embedding = self._get_embeddings([query])[0]
            
            # Create filter conditions
            filter_conditions = [
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            ]
            
            # Add video_id filter if provided
            if video_id:
                filter_conditions.append(
                    FieldCondition(
                        key="video_id",
                        match=MatchValue(value=video_id)
                    )
                )
            
            # Create filter
            search_filter = Filter(must=filter_conditions)
            
            # Search with filter using query_points for compatibility
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=search_filter,
                limit=limit
            )
            
            # Convert results to list of dicts
            results = []
            for hit in search_results.points:
                results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                })
            
            logger.info(f"Found {len(results)} segments for user {user_id}" + (f" and video {video_id}" if video_id else ""))
            return results
            
        except Exception as e:
            logger.error(f"Failed to search segments: {e}")
            return []
