import os
from typing import List, Optional
from google import genai
from google.genai import types
from app.services.vector_store import VectorStoreService
from app.utils.cache import (
    get_cached_value, 
    set_cached_value, 
    generate_query_hash,
    CACHE_PREFIX_CHAT,
    TTL_CHAT
)
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("services.chat")


class ChatService:
    """Service for chat interactions using Gemini and RAG"""
    
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.vector_service = VectorStoreService()
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set - chat functionality will fail")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        logger.info("ChatService initialized")
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the AI assistant"""
        return """You are an expert Video AI Assistant. Your task is to answer questions about video content based on the provided transcript snippets.

Guidelines:
1. Use ONLY the provided transcript snippets to answer questions
2. Always mention specific timestamps in the format [MM:SS] when referencing content
3. Always mention speaker labels (e.g., "Speaker 1", "Speaker 2") when referring to who said something
4. Incorporate emotion/tone context when relevant (e.g., "The speaker sounded frustrated when they mentioned...")
5. If the answer is not in the provided snippets, respond: "I'm sorry, I couldn't find that specific information in this video."
6. Be concise and focused on the question
7. If multiple speakers are discussed, clearly indicate which speaker said what"""
    
    def _build_user_prompt(self, query: str, segments: List[dict]) -> str:
        """Build the user prompt with retrieved segments"""
        prompt = f"""Question: {query}

Relevant transcript snippets:
"""
        
        for i, segment in enumerate(segments, 1):
            payload = segment.get("payload", {})
            text = payload.get("text", "")
            start_time = payload.get("start_time", 0)
            speaker = payload.get("speaker_label", "Unknown")
            emotion = payload.get("audio_emotion")
            tone = payload.get("text_tone")
            
            # Format timestamp
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            
            prompt += f"\n--- Segment {i} ---\n"
            prompt += f"Speaker: {speaker}\n"
            prompt += f"Time: {timestamp}\n"
            prompt += f"Text: {text}\n"
            
            if emotion or tone:
                context_parts = []
                if emotion:
                    context_parts.append(f"emotion: {emotion}")
                if tone:
                    context_parts.append(f"tone: {tone}")
                prompt += f"Context: {', '.join(context_parts)}\n"
        
        prompt += "\nPlease answer the question based on the above information."
        
        return prompt
    
    def chat(
        self, 
        query: str, 
        user_id: str, 
        video_id: Optional[str] = None,
        history: Optional[List[dict]] = None,
        limit: int = 5
    ) -> dict:
        """
        Process a chat query using RAG with conversation memory and LLM response caching
        
        Args:
            query: User's question
            user_id: User's ID (for multi-tenancy)
            video_id: Optional video ID to limit search scope
            history: List of previous messages for context
            limit: Number of segments to retrieve
            
        Returns:
            dict with answer and source_segments
        """
        try:
            # Generate cache key for this query + video combination
            query_hash = generate_query_hash(query.lower().strip())
            cache_key = f"{CACHE_PREFIX_CHAT}{video_id}:{query_hash}"
            
            # Check cache first (only for queries without history to avoid stale context)
            if not history or len(history) == 0:
                from app.core.redis_client import redis_client
                cached_response = redis_client.get(cache_key)
                if cached_response:
                    import json
                    logger.info(f"Cache hit for chat query: {query[:50]}...")
                    return json.loads(cached_response)
            
            # Step 1: Retrieve relevant segments from Qdrant
            segments = self.vector_service.search_segments(
                query=query,
                user_id=user_id,
                video_id=video_id,
                limit=limit
            )
            
            if not segments:
                return {
                    "answer": "I'm sorry, I couldn't find any relevant information in this video.",
                    "source_segments": [],
                    "query": query
                }
            
            # Step 2: Build prompts with conversation history
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt_with_history(query, segments, history)
            
            # Step 3: Generate response with Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt
                )
            )
            
            # Extract answer
            answer = response.text if hasattr(response, 'text') else str(response)
            
            # Step 4: Prepare source segments for UI
            source_segments = []
            for segment in segments:
                payload = segment.get("payload", {})
                source_segments.append({
                    "text": payload.get("text", ""),
                    "timestamp": f"[{int(payload.get('start_time', 0) // 60):02d}:{int(payload.get('start_time', 0) % 60):02d}]",
                    "speaker": payload.get("speaker_label", "Unknown"),
                    "score": segment.get("score", 0),
                    "video_id": payload.get("video_id", "")
                })
            
            result = {
                "answer": answer,
                "source_segments": source_segments,
                "query": query
            }
            
            # Cache the response (only for queries without history)
            if not history or len(history) == 0:
                from app.core.redis_client import redis_client
                import json
                redis_client.setex(cache_key, TTL_CHAT, json.dumps(result))
                logger.info(f"Cached chat response for query: {query[:50]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"Chat failed: {e}", exc_info=True)
            return {
                "answer": "I encountered an error processing your request. Please try again.",
                "source_segments": [],
                "query": query,
                "error": str(e)
            }
    
    def _build_user_prompt_with_history(
        self, 
        query: str, 
        segments: List[dict], 
        history: Optional[List[dict]]
    ) -> str:
        """Build the user prompt with conversation history and retrieved segments"""
        prompt_parts = []
        
        # Add conversation history if available
        if history and len(history) > 0:
            prompt_parts.append("Previous conversation:")
            for msg in history:
                role = msg.get("role", "unknown")
                content = msg.get("parts", [{}])[0].get("text", "")
                prompt_parts.append(f"- {role.capitalize()}: {content}")
            prompt_parts.append("")
        
        # Add retrieved segments
        prompt_parts.append("Relevant transcript snippets:")
        
        for i, segment in enumerate(segments, 1):
            payload = segment.get("payload", {})
            text = payload.get("text", "")
            start_time = payload.get("start_time", 0)
            speaker = payload.get("speaker_label", "Unknown")
            emotion = payload.get("audio_emotion")
            tone = payload.get("text_tone")
            
            # Format timestamp
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            
            prompt_parts.append(f"\n--- Segment {i} ---")
            prompt_parts.append(f"Speaker: {speaker}")
            prompt_parts.append(f"Time: {timestamp}")
            prompt_parts.append(f"Text: {text}")
            
            if emotion or tone:
                context_parts = []
                if emotion:
                    context_parts.append(f"emotion: {emotion}")
                if tone:
                    context_parts.append(f"tone: {tone}")
                prompt_parts.append(f"Context: {', '.join(context_parts)}")
        
        prompt_parts.append(f"\nCurrent question: {query}")
        prompt_parts.append("\nPlease answer the current question using the conversation history and transcript snippets above.")
        
        return "\n".join(prompt_parts)
