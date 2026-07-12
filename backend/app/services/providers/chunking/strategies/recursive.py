"""Recursive chunking — split hierarchically (paragraph → line → sentence →
word), preserving structure. Backed by RecursiveCharacterTextSplitter, same
engine as `fixed` but conceptually the structure-preserving variant.
"""
from . import fixed


def chunk(blocks, opts):
    return fixed.chunk(blocks, opts)
