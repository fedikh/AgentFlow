from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, test_connection
from app.routes import auth, users

# Import rag — show error if it fails
try:
    from app.routes import rag
    has_rag = True
except Exception as e:
    has_rag = False
    print(f"⚠️  RAG module not loaded: {e}")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AgentFlow API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,  prefix="/api")
app.include_router(users.router, prefix="/api")
if has_rag:
    app.include_router(rag.router, prefix="/api")
    print("✅ RAG module loaded")
else:
    print("❌ RAG module NOT loaded — check the error above")

@app.on_event("startup")
async def startup():
    test_connection()

@app.get("/")
def root():
    return {"message": "AgentFlow API is running"}