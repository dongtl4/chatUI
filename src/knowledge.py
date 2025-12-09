from sqlalchemy import create_engine, text
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector
from agno.db.postgres import PostgresDb
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.utils.log import logger

def ensure_database_exists(kb_config: dict):
    """
    Checks if the target database exists. If not, creates it.
    Connects to the default 'postgres' database to perform this check.
    """
    target_db = kb_config['db']
    
    # URL for the default maintenance database 'postgres'
    root_url = f"postgresql+psycopg://{kb_config['user']}:{kb_config['password']}@{kb_config['host']}:{kb_config['port']}/postgres"
    
    engine = create_engine(root_url, isolation_level="AUTOCOMMIT")
    
    try:
        with engine.connect() as conn:
            # Check if DB exists
            check_sql = text(f"SELECT 1 FROM pg_database WHERE datname='{target_db}'")
            exists = conn.execute(check_sql).fetchone()
            
            if not exists:
                logger.info(f"Database '{target_db}' not found. Creating...")
                # Create DB
                create_sql = text(f'CREATE DATABASE "{target_db}"')
                conn.execute(create_sql)
                logger.info(f"Database '{target_db}' created successfully.")
            else:
                logger.info(f"Database '{target_db}' already exists.")
    except Exception as e:
        logger.error(f"Failed to check/create database: {e}")
        raise e
    finally:
        engine.dispose()

def setup_knowledge_base(kb_config: dict) -> Knowledge:
    """
    Initializes the Knowledge Base.
    1. Ensures the PostgreSQL Database exists.
    2. Ensures the Vector extension and Tables exist.
    """
    
    # 1. Ensure the container Database exists
    ensure_database_exists(kb_config)

    # 2. Construct Target Database URL
    db_url = f"postgresql+psycopg://{kb_config['user']}:{kb_config['password']}@{kb_config['host']}:{kb_config['port']}/{kb_config['db']}"

    # 3. Initialize Embedder
    embedder = OllamaEmbedder(
        id="nomic-embed-text", 
        dimensions=768, 
        host="http://10.10.128.140:11434"
    )

    # 4. Define Vector Database (PgVector)
    vector_db = PgVector(
        table_name=kb_config['table_name'],
        db_url=db_url,
        embedder=embedder,
    )

    # 5. Define Content Database (PostgresDb)
    contents_db = PostgresDb(
        db_url=db_url,
        knowledge_table="knowledge_contents"
    )

    # 6. Ensure Tables Exist
    try:
        # PgVector needs explicit creation to install the 'vector' extension
        vector_db.create()
        
    except Exception as e:
        logger.error(f"Vector Table initialization error: {e}")
        raise e

    return Knowledge(
        vector_db=vector_db, 
        contents_db=contents_db, 
        name=kb_config.get('knowledge_name', 'Agno Knowledge Base')
    )