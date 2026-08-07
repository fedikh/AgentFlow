"""Chat package — the enterprise user chat layer for deployed agents.

    service.py   sessions CRUD, message storage, conversation memory
                 (summary + recent window + follow-up condense), background
                 summarization — PostgreSQL is the source of truth
    cache.py     Upstash Redis read-through cache (optional; no-op without
                 UPSTASH_REDIS_REST_URL / _TOKEN in .env)

Models live in app/models/chat.py; routes in app/routes/chat.py.
"""
from . import cache, service  # noqa: F401
