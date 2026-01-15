from typing import List, Optional, Type, Any
import os
import re
from dotenv import load_dotenv

from agno.knowledge.document import Document
from agno.knowledge.reranker.base import Reranker
from agno.utils.log import logger
from agno.models.ollama import Ollama
from agno.models.message import Message
from agno.models.deepseek import DeepSeek
from agno.models.openai import OpenAIChat

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
    reasoning: bool = False
    add_few_shot: bool = False
    few_shot_examples: str = """
        ### Example 1
        Query: "What is the capital of France?"
        Document Chunk: "Paris is the capital and most populous city of France. It is situated on the Seine River."
        Analysis: The chunk explicitly states that Paris is the capital of France, directly answering the query.
        <score>0.98</score>

        ### Example 2
        Query: "How to fix a flat tire?"
        Document Chunk: "A flat tire can be dangerous. Always ensure you have a spare tire, a jack, and a lug wrench in your trunk before driving."
        Analysis: The chunk lists the necessary tools for fixing a flat tire, which is crucial supporting information, but it does not provide the actual steps to perform the repair.
        <score>0.83</score>

        ### Example 3
        Query: "How do I install Python on Mac?"
        Document Chunk: "Python is a high-level, general-purpose programming language. Its design philosophy emphasizes code readability and can be installed easily on all computers."
        Analysis: The chunk defines what Python is but does not provide installation instructions for Mac. It is semantically relevant but functionally incomplete.
        <score>0.57</score>

        ### Example 4
        Query: "Best pizza in New York"
        Document Chunk: "The history of New York dates back to 1624. It was originally founded as a trading post by colonists of the Dutch Republic."
        Analysis: The chunk discusses New York history but makes no mention of food or pizza. The shared keyword is coincidental and provides no useful context for the user's intent.
        <score>0.35</score>
        """
    
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
                if self.reasoning:
                    prompt = (
                        "###Task: Evaluate the relevance of the Document Chunk to the Query.\n\n"

                        "###Instructions:\n"
                        "1. Briefly analyze the relevance (1-2 sentences).\n"
                        "2. Assign a float score based on the rubric.\n"
                        "3. Enclose the score within <score> and </score> tags.\n"
                        "4. Example output format: ... reasoning ... <score>0.8</score>\n\n"

                        "###Scoring Rubric:\n"
                        "- 0.9-1.0 (Highly Relevant): The chunk contains the direct answer to the query.\n"
                        "- 0.7-0.89 (Relevant): The chunk contains supporting information or context relevant to the query.\n"
                        "- 0.4-0.59 (Somewhat Relevant): The chunk mentions the topic but does not answer the query.\n"
                        "- 0.0-0.39 (Irrelevant): The chunk is unrelated.\n\n"

                        f"Examples:\n{self.few_shot_examples if self.add_few_shot else ""}\n\n"

                        "### Input:\n"
                        f"Query: {query}\n"
                        f"Document Chunk: {doc.content}\n\n"
                    )
                else:
                    prompt = (
                        "###Task: Evaluate the relevance of the Document Chunk to the Query.\n"
                        "Output a single float number between 0.01 (completely irrelevant) and 1.00 (highly relevant).\n"
                        "Output ONLY the number within <score> and </score> tags, no explanation, no words.\n"
                        "Example output format: <score>0.8</score>"

                        "###Scoring Rubric:\n"
                        "- 0.9-1.0 (Highly Relevant): The chunk contains the direct answer to the query.\n"
                        "- 0.7-0.89 (Relevant): The chunk contains supporting information or context relevant to the query.\n"
                        "- 0.4-0.59 (Somewhat Relevant): The chunk mentions the topic but does not answer the query.\n"
                        "- 0.0-0.39 (Irrelevant): The chunk is unrelated.\n\n"

                        "### Input:\n"
                        f"Query: {query}\n"
                        f"Document Chunk: {doc.content}\n\n"
                    )

                # Use the pre-initialized client (self._llm)
                response = self._llm.response(messages=[Message(role="user", content=prompt)])
                response_text = response.content if response and response.content else ""
                
                # Extract the first floating point number found in the response
                match = re.search(r"<score>\s*(\d+(\.\d+)?)\s*</score>", response_text)
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

class APIHeuristicReranker(HeuristicReranker):
    """
    Reranker imprelemtation for API models.
    Current available: Deepseek/openAI
    """
    provider: str = "deepseek"
    model: str = 'deepseek-chat'
    api_key: str = os.getenv("DEEPSEEK_API_KEY")

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize the API client
        if self.provider == 'deepseek':
            self._llm = DeepSeek(id=self.model, api_key=self.api_key)
        if self.provider == 'openai':
            self._llm = OpenAIChat(id=self.model, api_key=self.api_key)
