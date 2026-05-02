from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

        print("✅ PostgreSQL connected successfully")
        print("✅ pgvector extension enabled")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        raise