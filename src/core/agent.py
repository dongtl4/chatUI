import streamlit as st
from uuid import uuid4
from agno.agent import Agent
from agno.tools.knowledge import KnowledgeTools
from agno.models.openai import OpenAIChat
from agno.models.ollama import Ollama
from agno.models.deepseek import DeepSeek
import src.core.knowledge as kb_module

def create_model(provider, **kwargs):
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

def get_knowledge(kb_type: str, kb_config: dict):
    if kb_type == "PostgreSQL + PGVector":
        try:
            return kb_module.setup_knowledge_base(kb_config)
        except Exception as e:
            # st.error(f"KB Init Error: {e}") # Suppress error on UI if just loading
            return None
    return None

def get_agent(model, instructions, kb_type, kb_config, session_id) -> Agent:
    knowledge = get_knowledge(kb_type, kb_config)
    
    knowledge_tools = None
    if knowledge:
        knowledge_tools = KnowledgeTools(
            knowledge=knowledge,
            enable_think=False,
            enable_search=True,
            enable_analyze=False,
            add_few_shot=False,
        )
    
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