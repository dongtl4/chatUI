from typing import List, Optional, Type, Any
import os
import re
from dotenv import load_dotenv

from agno.knowledge.document import Document
from agno.knowledge.reranker.base import Reranker
from agno.utils.log import logger
from agno.models.ollama import Ollama
from agno.models.message import Message

load_dotenv()

class HeuristicReranker(Reranker):
    """
    Base class for Rerankers that use an LLM to score relevance.
    Handles input validation and the core reranking loop.
    """
    # Common configuration
    model: str
    top_n: Optional[int] = None
    score_threshold: Optional[float] = None
    collected_number: Optional[int] = None
    
    # Internal LLM instance (to be set by child classes)
    _llm: Optional[Any] = None

    def __init__(self, **data):
        super().__init__(**data)
        
        # 1. Centralized Validation Logic
        if self.top_n is not None and self.top_n < 1:
            raise ValueError(f"top_n must be a positive integer, got {self.top_n}")            
        if self.collected_number is not None and self.collected_number < 1:
            raise ValueError(f"collected_number must be a positive integer, got {self.collected_number}")            
        if self.score_threshold is not None and not (0.0 <= self.score_threshold <= 1.0):
            raise ValueError(f"score_threshold must be between 0.0 and 1.0, got {self.score_threshold}")
        if self.collected_number is not None and self.score_threshold is None:
            raise ValueError("score_threshold must be provided when collected_number is set.")

    def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        """
        Core reranking logic shared by all implementations.
        """
        if not documents:
            return []
        
        if self._llm is None:
            logger.error("LLM client is not initialized.")
            return documents

        logger.info(f"Reranking {len(documents)} documents using {self.model}")
        
        scored_docs = []

        for doc in documents:
            try:
                # Construct a strict prompt to get a numerical score
                prompt = (
                    f"Query: {query}\n"
                    f"Document Chunk: {doc.content}\n\n"
                    "Task: Evaluate the relevance of the Document Chunk to the Query.\n"
                    "Output a single float number between 0.01 (completely irrelevant) and 1.00 (highly relevant).\n"
                    "Output ONLY the number, no explanation, no words."
                )

                # Use the pre-initialized client (self._llm)
                response = self._llm.response(messages=[Message(role="user", content=prompt)])
                response_text = response.content if response and response.content else ""
                
                # Extract the first floating point number found in the response
                match = re.search(r"(\d+(\.\d+)?)", response_text)
                if match:
                    score = float(match.group(1))
                    score = max(0.0, min(1.0, score))                    
                    doc.reranking_score = score
                    
                    # Filter doc by score threshold if it is set
                    if self.score_threshold is not None:
                        if doc.reranking_score >= self.score_threshold:
                            scored_docs.append(doc)
                        # Checking for number of collected docs
                        if self.collected_number is not None:
                                if len(scored_docs) >= self.collected_number:
                                    logger.info(f"Collected {len(scored_docs)} documents meeting threshold. Stopping reranking.")
                                    break
                    else:
                        scored_docs.append(doc)
                else:
                    logger.warning(f"Could not parse score from model output: '{response_text}'. Defaulting to 0.0")
                    if self.score_threshold is not None and self.score_threshold > 0:
                        continue
                    doc.reranking_score = 0.0
                    scored_docs.append(doc)

            except Exception as e:
                logger.error(f"Error scoring document: {e}")
                doc.reranking_score = 0.0
                scored_docs.append(doc)

        # Sort documents by score in descending order
        scored_docs.sort(key=lambda x: x.reranking_score if x.reranking_score is not None else 0.0, reverse=True)

        # Return top N documents if limit is set
        if self.top_n is not None:
            return scored_docs[:self.top_n]
        
        return scored_docs


class OllamaHeuristicReranker(HeuristicReranker):
    """
    Reranker implementation specifically for Ollama models.
    """
    model: str = "qwen3:latest"
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize the Ollama client
        self._llm = Ollama(id=self.model, host=self.host)
