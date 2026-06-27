"""
Routes — Model Registry.

Endpoints pour que le front remplisse les listes déroulantes de modèles.

    GET /api/models/all              → tout (LLM providers + embeddings)
    GET /api/models/embeddings       → liste des modèles d'embedding
    GET /api/models/llm/{provider}   → modèles d'un provider LLM (GROQ/OLLAMA/OPENAI)

À brancher dans main.py :
    from app.routes import models as models_routes
    app.include_router(models_routes.router)
"""
from fastapi import APIRouter
from app.services import model_registry

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/all")
def get_all_models():
    """Vue d'ensemble : état de chaque provider LLM + embeddings."""
    return model_registry.list_all_providers()


@router.get("/embeddings")
def get_embedding_models():
    """Liste curatée des modèles d'embedding (avec dimensions)."""
    return {"models": model_registry.list_embedding_models()}


@router.get("/llm/{provider}")
def get_llm_models(provider: str):
    """Modèles d'un provider LLM, récupérés en direct."""
    return model_registry.list_llm_models(provider)