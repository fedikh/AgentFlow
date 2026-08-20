"""Background jobs — the evaluation-runner pattern (daemon thread + in-memory
registry polled by the UI). There is no Celery; this is the seam where a
broker would plug in later."""
from __future__ import annotations

import threading
import uuid

_JOBS: dict = {}
_LOCK = threading.Lock()


def start_job(kind: str, target, *args) -> dict:
    """Run target(job_id, *args) in a daemon thread; the target updates the
    job via update_job(). Returns {job_id}."""
    job_id = str(uuid.uuid4())
    with _LOCK:
        finished = [k for k, v in _JOBS.items() if v["status"] != "running"]
        for k in finished[:-10]:                      # keep the last few
            _JOBS.pop(k, None)
        _JOBS[job_id] = {"kind": kind, "status": "running", "done": 0,
                         "total": 0, "step": "", "error": None, "result": None}
    threading.Thread(target=_wrap, args=(job_id, target, args),
                     daemon=True).start()
    return {"job_id": job_id}


def _wrap(job_id, target, args):
    try:
        result = target(job_id, *args)
        update_job(job_id, status="done", result=result)
    except Exception as e:
        update_job(job_id, status="error", error=str(e)[:300])


def update_job(job_id: str, **fields) -> None:
    j = _JOBS.get(job_id)
    if j:
        j.update(fields)


def job_status(job_id: str) -> dict:
    j = _JOBS.get(job_id)
    if not j:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    return j
