from sqlalchemy import create_engine, text
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector
from agno.db.postgres import PostgresDb
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.vectordb.search import SearchType
# from agno.utils.log import logger
import streamlit as st
import os
from dotenv import load_dotenv
# for debugging
import time
# reranker
from src.utils.heuristic_reranker import OllamaHeuristicReranker

load_dotenv()

@st.cache_resource
def ensure_database_exists(kb_config: dict):
    target_db = kb_config['db']
    # Connect to 'postgres' db to check/create target db
    root_url = f"postgresql+psycopg://{kb_config['user']}:{kb_config['password']}@{kb_config['host']}:{kb_config['port']}/postgres"
    engine = create_engine(root_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            check_sql = text(f"SELECT 1 FROM pg_database WHERE datname='{target_db}'")
            exists = conn.execute(check_sql).fetchone()
            if not exists:
                create_sql = text(f'CREATE DATABASE "{target_db}"')
                conn.execute(create_sql)
        return True
    except Exception as e:
        # It's possible the DB already exists or connection failed; just proceed/raise
        raise e
    finally:
        engine.dispose()

@st.cache_resource
def setup_knowledge_base(kb_config: dict) -> Knowledge:
    ensure_database_exists(kb_config)
    db_url = f"postgresql+psycopg://{kb_config['user']}:{kb_config['password']}@{kb_config['host']}:{kb_config['port']}/{kb_config['db']}"

    embedder = OllamaEmbedder(
        id="embeddinggemma:latest", 
        dimensions=768, 
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )

    if kb_config['reranker_type'] == "Heuristic":
        reranker = OllamaHeuristicReranker(
            top_n = kb_config['top_n'],
            score_threshold = kb_config['score_threshold'],
            collected_number = kb_config['collected_number']
        )

    vector_db = PgVector(
        table_name=kb_config['table_name'],
        db_url=db_url,
        search_type=SearchType.hybrid,
        embedder=embedder,
        reranker = reranker if kb_config['reranker_type'] != 'None' else None
    )

    contents_db = PostgresDb(
        db_url=db_url,
        knowledge_table="knowledge_contents"
    )

    knowledge = Knowledge(
        vector_db=vector_db, 
        contents_db=contents_db,
        max_results=kb_config.get('max_results', 10),
        name=kb_config.get('knowledge_name', 'Agno Knowledge Base')
    )

    return knowledge