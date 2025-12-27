from sqlalchemy import create_engine, text
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector
from agno.db.postgres import PostgresDb
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.vectordb.search import SearchType
# from agno.utils.log import logger
import streamlit as st

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

def setup_knowledge_base(kb_config: dict) -> Knowledge:
    ensure_database_exists(kb_config)
    db_url = f"postgresql+psycopg://{kb_config['user']}:{kb_config['password']}@{kb_config['host']}:{kb_config['port']}/{kb_config['db']}"

    embedder = OllamaEmbedder(
        id="nomic-embed-text", 
        dimensions=768, 
        host="http://10.10.128.140:11434"
    )

    vector_db = PgVector(
        table_name=kb_config['table_name'],
        db_url=db_url,
        search_type=SearchType.hybrid,
        embedder=embedder,
    )

    contents_db = PostgresDb(
        db_url=db_url,
        knowledge_table="knowledge_contents"
    )

    return Knowledge(
        vector_db=vector_db, 
        contents_db=contents_db,
        max_results=kb_config.get('max_results', 10),
        name=kb_config.get('knowledge_name', 'Agno Knowledge Base')
    )