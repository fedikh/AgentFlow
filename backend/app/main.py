from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, test_connection
from app.routes import auth

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
    allow_credentials=True,          # required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")

@app.on_event("startup")
async def startup():
    test_connection()

@app.get("/")
def root():
    return {"message": "AgentFlow API is running"}