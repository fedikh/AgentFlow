"""Agentic chunking package — a multi-agent pipeline that plans and builds
chunks with an OpenAI model. Entry point: pipeline.chunk(parsed, cfg)."""
from .pipeline import chunk

__all__ = ["chunk"]
