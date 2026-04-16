from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# ── Engine ────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,           # set True to see SQL queries in terminal
    pool_pre_ping=True,   # check connection before using it
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Base class for all models ─────────────────────────
class Base(DeclarativeBase):
    pass

# ── Dependency — inject DB session into routes ────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Test connection ───────────────────────────────────
def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ PostgreSQL connected successfully")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        raise