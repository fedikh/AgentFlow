"""
Role dashboards — each is ONE call returning ONE payload.

    it_dashboard      the builder view: my departments, one card per live
                      space (costs, tokens, requests, API), usage charts
    admin_dashboard   the organization view: users, departments rollup,
                      every space with owner + costs, org-wide charts
                      (including cost per day)

Both share _collect(): the aggregation core (knowledge base counters,
$/query basis, API keys/logs, one 30-day message scan).

Costs are ESTIMATES. $/query comes from the space's latest evaluation
(measured with real context sizes); never-evaluated spaces fall back to
the model's list price at a typical 3k-in/300-out query; local models
cost 0. API usage cost is a SUBSET of a space's cost (its calls create
the same chat messages), never an addition.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.api_key import AgentApiKey, AgentApiLog
from app.models.chat import ChatMessage, ChatSession
from app.models.department import Department
from app.models.document import Document
from app.models.evaluation import EvalRun
from app.models.rag_space import RAGSpace
from app.models.user import User
from app.services.evaluation.scoring.performance import price_for

DAYS = 14                      # chart + sparkline window


def _utcnow() -> datetime:
    """Naive UTC — matches how the chat/eval tables store timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _status(space) -> str:
    s = str(getattr(space, "status", "") or "DRAFT")
    return s.split(".")[-1] if "." in s else s


def _role(user) -> str:
    r = str(getattr(user, "role", "") or "")
    return r.split(".")[-1] if "." in r else r


def _my_spaces(db: Session, user) -> list:
    """Spaces this user builds. For ADMIN _can_build is always true, so the
    admin dashboard naturally covers every space of the organization."""
    from app.services.rag_service import _can_build
    rows = (db.query(RAGSpace)
            .filter(RAGSpace.organization_id == user.organization_id,
                    RAGSpace.system_kind.is_(None))    # hide internal spaces
            .all())
    return [s for s in rows if _can_build(db, s, user)]


def _delta(cur: float, prev: float):
    """% change vs the previous period — None when there is no baseline."""
    if not prev:
        return None
    return round((cur - prev) / prev * 100)


def _cost_per_query(space, metrics: dict) -> float:
    v = (metrics.get("performance") or {}).get("est_cost_per_query")
    if v:
        return float(v)
    in_p, out_p = price_for(getattr(space, "llm_model", "") or "")
    return (3000 * in_p + 300 * out_p) / 1e6


# ══════════════════════════════════════════════════════════════
#  Shared aggregation core
# ══════════════════════════════════════════════════════════════

def _collect(db: Session, spaces: list) -> dict:
    ids = [s.id for s in spaces]
    now = _utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)
    since = now - timedelta(days=DAYS - 1)
    days = [(since + timedelta(days=i)).date() for i in range(DAYS)]

    docs = dict(db.query(Document.rag_space_id, func.count(Document.id))
                .filter(Document.rag_space_id.in_(ids))
                .group_by(Document.rag_space_id).all())
    chunks = dict(db.query(Document.rag_space_id, func.sum(Document.num_chunks))
                  .filter(Document.rag_space_id.in_(ids))
                  .group_by(Document.rag_space_id).all())
    dept_names = {d.id: d.name for d in db.query(Department).filter(
        Department.id.in_([s.department_id for s in spaces if s.department_id])).all()}

    # eval basis: $/query, retrieval latency, test spend per space
    metrics, test_cost = {}, {}
    for run in (db.query(EvalRun).filter(EvalRun.rag_space_id.in_(ids))
                .order_by(EvalRun.created_at.desc()).all()):
        m = json.loads(run.metrics or "{}")
        metrics.setdefault(run.rag_space_id, m)          # newest run wins
        perf = m.get("performance") or {}
        test_cost[run.rag_space_id] = test_cost.get(run.rag_space_id, 0.0) + \
            float(perf.get("est_cost_per_query") or 0) * (run.num_cases or 0)
    cost_q = {s.id: _cost_per_query(s, metrics.get(s.id, {})) for s in spaces}
    retrieval = {sid: m.get("performance", {}).get("avg_retrieval_ms")
                 for sid, m in metrics.items()}

    # API keys + call logs
    keys, key_counts = {}, {}
    for k in (db.query(AgentApiKey).filter(AgentApiKey.rag_space_id.in_(ids),
                                           AgentApiKey.revoked_at.is_(None))
              .order_by(AgentApiKey.created_at.desc()).all()):
        keys.setdefault(k.rag_space_id, k)
        key_counts[k.rag_space_id] = key_counts.get(k.rag_space_id, 0) + 1
    api_today = dict(db.query(AgentApiLog.rag_space_id, func.count(AgentApiLog.id))
                     .filter(AgentApiLog.created_at >= today)
                     .group_by(AgentApiLog.rag_space_id).all())
    api_30d = dict(db.query(AgentApiLog.rag_space_id, func.count(AgentApiLog.id))
                   .filter(AgentApiLog.created_at >= d30, AgentApiLog.status == 200)
                   .group_by(AgentApiLog.rag_space_id).all())

    # ONE 30-day message scan feeds per-space stats and every day series
    rows = (db.query(ChatMessage.created_at, ChatMessage.role,
                     func.length(ChatMessage.content), ChatMessage.latency_ms,
                     ChatMessage.session_id, ChatSession.rag_space_id)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.rag_space_id.in_(ids),
                    ChatMessage.created_at >= d30).all())

    day_conv = {d: set() for d in days}
    day_tokens = {d: 0 for d in days}
    day_lat = {d: [0, 0] for d in days}
    day_cost = {d: 0.0 for d in days}
    d14 = now - timedelta(days=14)
    sp = {sid: {"tokens": 0, "conv": set(), "q_day": 0, "q_week": 0,
                "q_prev_week": 0, "q_month": 0, "lat": [0, 0],
                "spark": {d: 0 for d in days}} for sid in ids}
    for created, role, length, lat_ms, session_id, sid in rows:
        d, x = created.date(), sp[sid]
        x["tokens"] += (length or 0) // 4
        x["conv"].add(session_id)
        if role == "assistant":
            x["q_month"] += 1
            if created >= d7:
                x["q_week"] += 1
            elif created >= d14:
                x["q_prev_week"] += 1
            if created >= today:
                x["q_day"] += 1
            if lat_ms and created >= d7:
                x["lat"][0] += lat_ms
                x["lat"][1] += 1
        if d in day_tokens:
            x["spark"][d] += 1
            day_conv[d].add(session_id)
            day_tokens[d] += (length or 0) // 4
            if role == "assistant":
                day_cost[d] += cost_q[sid]
                if lat_ms:
                    day_lat[d][0] += lat_ms
                    day_lat[d][1] += 1

    return {"ids": ids, "now": now, "d7": d7, "d30": d30, "days": days,
            "docs": docs, "chunks": chunks, "dept_names": dept_names,
            "cost_q": cost_q, "test_cost": test_cost, "retrieval": retrieval,
            "keys": keys, "key_counts": key_counts,
            "api_today": api_today, "api_30d": api_30d, "sp": sp,
            "day_conv": day_conv, "day_tokens": day_tokens,
            "day_lat": day_lat, "day_cost": day_cost}


def _space_card(s, c: dict) -> dict:
    x, cq = c["sp"][s.id], c["cost_q"][s.id]
    k = c["keys"].get(s.id)
    return {
        "id": s.id, "name": s.name, "status": _status(s),
        "department": c["dept_names"].get(s.department_id, "General"),
        "docs": int(c["docs"].get(s.id, 0)),
        "chunks": int(c["chunks"].get(s.id) or 0),
        "cost": {"day": round(cq * x["q_day"], 4),
                 "week": round(cq * x["q_week"], 4),
                 "month": round(cq * x["q_month"], 4),
                 "tests": round(c["test_cost"].get(s.id, 0.0), 4)},
        "tokens_30d": x["tokens"],
        "conversations_30d": len(x["conv"]),
        "queries_month": x["q_month"],
        "latency_ms": round(x["lat"][0] / x["lat"][1]) if x["lat"][1] else None,
        "retrieval_ms": round(c["retrieval"][s.id]) if c["retrieval"].get(s.id) else None,
        "api": {
            "enabled": bool(k),
            "keys": c["key_counts"].get(s.id, 0),
            "key_display": k.key_display if k else None,
            "endpoint": f"/v1/agents/{s.id}/chat",
            "requests_today": int(c["api_today"].get(s.id, 0)),
            "requests_30d": int(c["api_30d"].get(s.id, 0)),
            "cost_30d": round(cq * int(c["api_30d"].get(s.id, 0)), 4),
        },
        "spark": [{"date": str(d), "value": x["spark"][d]} for d in c["days"]],
    }


def _day_charts(c: dict) -> dict:
    days, lat = c["days"], c["day_lat"]
    return {
        "conversations_per_day": [{"date": str(d), "value": len(c["day_conv"][d])} for d in days],
        "tokens_per_day": [{"date": str(d), "value": c["day_tokens"][d]} for d in days],
        "latency_per_day": [{"date": str(d),
                             "value": round(lat[d][0] / lat[d][1]) if lat[d][1] else 0}
                            for d in days],
        "cost_per_day": [{"date": str(d), "value": round(c["day_cost"][d], 4)} for d in days],
    }


def _usage_per_user(db: Session, c: dict, org_id: str, limit: int = 8) -> list:
    users = {u.id: (u.name or u.email) for u in
             db.query(User).filter(User.organization_id == org_id).all()}
    rows = (db.query(ChatSession.user_id, ChatSession.external_user_id,
                     func.count(ChatMessage.id))
            .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.rag_space_id.in_(c["ids"]),
                    ChatMessage.role == "user",
                    ChatMessage.created_at >= c["d30"])
            .group_by(ChatSession.user_id, ChatSession.external_user_id)
            .order_by(func.count(ChatMessage.id).desc()).limit(limit).all())
    return [{"name": users.get(uid) or (f"API · {ext}" if ext else "API"),
             "value": int(n)} for uid, ext, n in rows]


# ══════════════════════════════════════════════════════════════
#  IT dashboard
# ══════════════════════════════════════════════════════════════

def it_dashboard(db: Session, user) -> dict:
    spaces = _my_spaces(db, user)
    if not spaces:
        return {"kpis": {}, "departments": [], "spaces": [], "charts": {}}
    c = _collect(db, spaces)

    by_dept: dict = {}
    for s in spaces:
        by_dept.setdefault(c["dept_names"].get(s.department_id, "General"), []).append({
            "id": s.id, "name": s.name, "status": _status(s),
            "docs": int(c["docs"].get(s.id, 0)),
            "chunks": int(c["chunks"].get(s.id) or 0),
        })
    departments = [{"name": n, "spaces": sp,
                    "docs": sum(x["docs"] for x in sp),
                    "chunks": sum(x["chunks"] for x in sp)}
                   for n, sp in sorted(by_dept.items())]

    live = [_space_card(s, c) for s in spaces if _status(s) in ("ACTIVE", "EDITING")]
    live.sort(key=lambda x: (x["status"] != "ACTIVE", -x["queries_month"]))

    lat = [x["latency_ms"] for x in live if x["latency_ms"]]
    retr = [x["retrieval_ms"] for x in live if x["retrieval_ms"]]
    conv_cur = len({m for d in c["days"] if d >= c["d7"].date()
                    for m in c["day_conv"][d]})
    conv_prev = len({m for d in c["days"] if d < c["d7"].date()
                     for m in c["day_conv"][d]})
    cost_week = round(sum(x["cost"]["week"] for x in live), 4)
    cost_prev_week = sum(c["cost_q"][s.id] * c["sp"][s.id]["q_prev_week"]
                         for s in spaces)
    kpis = {
        "cost_month": round(sum(x["cost"]["month"] for x in live), 4),
        "tokens_30d": sum(x["tokens_30d"] for x in live),
        "conversations_7d": conv_cur,
        "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None,
        "avg_retrieval_ms": round(sum(retr) / len(retr)) if retr else None,
        "api_requests_today": sum(int(v) for v in c["api_today"].values()),
        # % vs the previous 7 days (None = no baseline yet)
        "deltas": {"conversations_7d": _delta(conv_cur, conv_prev),
                   "cost_week": _delta(cost_week, cost_prev_week)},
    }
    charts = {**_day_charts(c),
              "usage_per_user": _usage_per_user(db, c, user.organization_id),
              "cost_by_space": [{"name": x["name"], "value": x["cost"]["month"]}
                                for x in live if x["cost"]["month"] > 0]}
    return {"kpis": kpis, "departments": departments, "spaces": live, "charts": charts}


# ══════════════════════════════════════════════════════════════
#  Admin dashboard — the whole organization
# ══════════════════════════════════════════════════════════════

def admin_dashboard(db: Session, user) -> dict:
    spaces = _my_spaces(db, user)              # admin → every org space
    org_users = db.query(User).filter(
        User.organization_id == user.organization_id).all()
    if not spaces:
        return {"kpis": {}, "users": {}, "departments": [], "spaces": [],
                "charts": {}}
    c = _collect(db, spaces)
    cards = {s.id: _space_card(s, c) for s in spaces}
    all_cards = list(cards.values())

    # ── users block ──
    roles = {"ADMIN": 0, "IT": 0, "USER": 0}
    pending = 0
    for u in org_users:
        roles[_role(u)] = roles.get(_role(u), 0) + 1
        if str(getattr(u, "status", "")).endswith("PENDING"):
            pending += 1
    active_30d = (db.query(func.count(func.distinct(ChatSession.user_id)))
                  .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
                  .filter(ChatSession.rag_space_id.in_(c["ids"]),
                          ChatSession.user_id.isnot(None),
                          ChatMessage.created_at >= c["d30"]).scalar() or 0)
    users_block = {"total": len(org_users), "pending": pending,
                   "active_30d": int(active_30d), **roles}

    # ── departments rollup (members, spaces, knowledge, cost) ──
    depts = db.query(Department).filter(
        Department.organization_id == user.organization_id).all()
    dept_rows = []
    for d in depts:
        own = [x for x in all_cards if x["department"] == d.name]
        dept_rows.append({
            "name": d.name,
            "members": len(getattr(d, "users", []) or []),
            "spaces": len(own),
            "deployed": sum(1 for x in own if x["status"] == "ACTIVE"),
            "docs": sum(x["docs"] for x in own),
            "chunks": sum(x["chunks"] for x in own),
            "cost_month": round(sum(x["cost"]["month"] for x in own), 4),
            "conversations_30d": sum(x["conversations_30d"] for x in own),
        })
    dept_rows.sort(key=lambda x: -x["cost_month"])

    # ── every space, with its owner (the admin table) ──
    owner_names = {u.id: (u.name or u.email) for u in org_users}
    table = []
    for s in spaces:
        x = cards[s.id]
        table.append({**x, "owner": owner_names.get(
            getattr(s, "owner_id", None), "—")})
    table.sort(key=lambda x: (x["status"] != "ACTIVE", -x["cost"]["month"]))

    # ── org KPIs ──
    lat = [x["latency_ms"] for x in all_cards if x["latency_ms"]]
    conv_cur = len({m for d in c["days"] if d >= c["d7"].date()
                    for m in c["day_conv"][d]})
    conv_prev = len({m for d in c["days"] if d < c["d7"].date()
                     for m in c["day_conv"][d]})
    cost_week = round(sum(x["cost"]["week"] for x in all_cards), 4)
    cost_prev_week = sum(c["cost_q"][s.id] * c["sp"][s.id]["q_prev_week"]
                         for s in spaces)
    kpis = {
        "users": len(org_users), "pending_users": pending,
        "departments": len(depts),
        "spaces": len(spaces),
        "deployed": sum(1 for x in all_cards if x["status"] == "ACTIVE"),
        "cost_day": round(sum(x["cost"]["day"] for x in all_cards), 4),
        "cost_week": cost_week,
        "cost_month": round(sum(x["cost"]["month"] for x in all_cards), 4),
        "test_cost": round(sum(x["cost"]["tests"] for x in all_cards), 4),
        "tokens_30d": sum(x["tokens_30d"] for x in all_cards),
        "conversations_7d": conv_cur,
        "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None,
        "api_requests_today": sum(int(v) for v in c["api_today"].values()),
        "deltas": {"conversations_7d": _delta(conv_cur, conv_prev),
                   "cost_week": _delta(cost_week, cost_prev_week)},
    }

    charts = {**_day_charts(c),
              "usage_per_user": _usage_per_user(db, c, user.organization_id),
              "cost_by_department": [{"name": d["name"], "value": d["cost_month"]}
                                     for d in dept_rows if d["cost_month"] > 0],
              "most_used": sorted(
                  [{"name": x["name"], "value": x["conversations_30d"]}
                   for x in all_cards if x["conversations_30d"] > 0],
                  key=lambda e: -e["value"])[:6]}

    return {"kpis": kpis, "users": users_block, "departments": dept_rows,
            "spaces": table, "charts": charts}


# ══════════════════════════════════════════════════════════════
#  End-user dashboard — personal stats, my agents, what's new
# ══════════════════════════════════════════════════════════════

def user_dashboard(db: Session, user) -> dict:
    """The worker view. No costs/tokens — continuity only:
    personal stats · accessible agents (most-used first) · recent deploys."""
    from app.models.rag_space_version import RAGSpaceVersion
    from app.services.rag_service import list_spaces

    agents = list_spaces(db, user.organization_id, user)   # role-filtered
    ids = [a["id"] for a in agents]
    now = _utcnow()
    d7, d14 = now - timedelta(days=7), now - timedelta(days=14)

    # ── my usage, grouped per agent ──
    my_sessions = dict(
        db.query(ChatSession.rag_space_id, func.count(ChatSession.id))
        .filter(ChatSession.user_id == user.id)
        .group_by(ChatSession.rag_space_id).all()) if ids else {}
    questions_7d = (db.query(func.count(ChatMessage.id))
                    .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                    .filter(ChatSession.user_id == user.id,
                            ChatMessage.role == "user",
                            ChatMessage.created_at >= d7).scalar() or 0)
    avg_answer = (db.query(func.avg(ChatMessage.latency_ms))
                  .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                  .filter(ChatSession.user_id == user.id,
                          ChatMessage.latency_ms.isnot(None),
                          ChatMessage.created_at >= d7).scalar())

    # ── my agents, most-used first ──
    rows = [{
        "id": a["id"], "name": a["name"],
        "description": a.get("description") or "",
        "department": a.get("department_name") or "General",
        "status": str(a.get("status") or ""),
        "my_conversations": int(my_sessions.get(a["id"], 0)),
    } for a in agents]
    rows.sort(key=lambda x: (-x["my_conversations"], x["name"].lower()))

    favorite = rows[0]["name"] if rows and rows[0]["my_conversations"] else None
    questions_prev = (db.query(func.count(ChatMessage.id))
                      .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                      .filter(ChatSession.user_id == user.id,
                              ChatMessage.role == "user",
                              ChatMessage.created_at >= d14,
                              ChatMessage.created_at < d7).scalar() or 0)
    stats = {
        "questions_7d": int(questions_7d),
        "questions_delta": _delta(int(questions_7d), int(questions_prev)),
        "conversations": int(sum(my_sessions.values())),
        "avg_answer_ms": round(float(avg_answer)) if avg_answer else None,
        "favorite_agent": favorite,
    }

    # ── my charts: questions per day (14d) + conversations per agent ──
    since = now - timedelta(days=13)
    per_day = dict(db.query(func.date(ChatMessage.created_at),
                            func.count(ChatMessage.id))
                   .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                   .filter(ChatSession.user_id == user.id,
                           ChatMessage.role == "user",
                           ChatMessage.created_at >= since)
                   .group_by(func.date(ChatMessage.created_at)).all())
    activity = [{"date": str((since + timedelta(days=i)).date()),
                 "value": int(per_day.get((since + timedelta(days=i)).date(), 0))}
                for i in range(14)]
    by_agent = [{"name": r["name"], "value": r["my_conversations"]}
                for r in rows if r["my_conversations"] > 0]

    # ── what's new: deploys on my agents in the last 14 days ──
    names = {a["id"]: a["name"] for a in agents}
    deploys = (db.query(RAGSpaceVersion)
               .filter(RAGSpaceVersion.rag_space_id.in_(ids),
                       RAGSpaceVersion.status == "DEPLOYED",
                       RAGSpaceVersion.created_at >= d14)
               .order_by(RAGSpaceVersion.created_at.desc())
               .limit(6).all()) if ids else []
    whats_new = [{"agent_id": v.rag_space_id,
                  "agent": names.get(v.rag_space_id, "?"),
                  "label": v.label, "notes": (v.notes or "")[:140],
                  "date": str(v.created_at)} for v in deploys]

    return {"stats": stats, "agents": rows, "whats_new": whats_new,
            "charts": {"activity": activity, "by_agent": by_agent}}
