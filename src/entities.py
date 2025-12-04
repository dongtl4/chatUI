import streamlit as st
from uuid import uuid4
from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.tools.knowledge import KnowledgeTools
from agno.db.postgres import PostgresDb
from agno.vectordb.pgvector.pgvector import PgVector

# Models
from agno.models.openai import OpenAIChat
from agno.models.ollama import Ollama
from agno.models.deepseek import DeepSeek

# Embedders
from agno.knowledge.embedder.ollama import OllamaEmbedder

def create_model(provider, **kwargs):
    """Factory for creating models."""
    try:
        if provider == "OpenAI":
            return OpenAIChat(id=kwargs.get("id"), api_key=kwargs.get("api_key"), name=kwargs.get("name"))
        elif provider == "Ollama":
            return Ollama(id=kwargs.get("id"), host=kwargs.get("host"), name=kwargs.get("name"))
        elif provider == "DeepSeek":
            return DeepSeek(id=kwargs.get("id"), api_key=kwargs.get("api_key"), name=kwargs.get("name"))
    except Exception as e:
        st.error(f"Error creating model: {e}")
        return None

@st.cache_resource
def get_knowledge(kb_type: str, kb_config: dict) -> Knowledge:
    """Creates and caches the knowledge base connection."""
    if kb_type == "PostgreSQL + PGVector":
        print(f"Creating new knowledge base: {kb_type}")
        embedder = OllamaEmbedder(id="nomic-embed-text", dimensions=768, host="http://10.10.128.140:11434")
        
        db_url = f"postgresql+psycopg://{kb_config['user']}:{kb_config['password']}@{kb_config['host']}:{kb_config['port']}/{kb_config['db']}"
        
        contents_db = PostgresDb(
            db_url=db_url,
            knowledge_table="knowledge_contents"
        )
        vector_db = PgVector(
            table_name=kb_config['table_name'],
            db_url=db_url,
            embedder=embedder,
        )
        return Knowledge(contents_db=contents_db, vector_db=vector_db, name=kb_config['knowledge_name'])
    return None

def get_agent(model, instructions, kb_type, kb_config, session_id) -> Agent:
    """Creates the Agent instance."""
    
    knowledge = get_knowledge(kb_type, kb_config)
    
    knowledge_tools = None
    if knowledge:
        knowledge_tools = KnowledgeTools(
            knowledge=knowledge,
            enable_think=True,
            enable_search=True,
            enable_analyze=True,
            add_few_shot=False,
        )
    
    # Ensure session ID exists
    if not session_id:
        new_sid = str(uuid4())
        st.session_state['session_id'] = new_sid
        session_id = new_sid

    return Agent(
        model=model,
        tools=[knowledge_tools] if knowledge_tools else [],
        instructions=instructions.splitlines(),
        session_id=session_id,
        markdown=True,
    )