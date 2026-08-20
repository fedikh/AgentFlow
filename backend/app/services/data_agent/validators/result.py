"""Shared validation types — one failure shape for the whole chain.

The message of a ValidationFailed is fed VERBATIM into the correction node,
so it is written for the LLM as much as for the human: it names what is
wrong and, where possible, what the valid options are.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckResult:
    check: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"check": self.check, "ok": self.ok, "detail": self.detail}


class ValidationFailed(Exception):
    def __init__(self, check: str, message: str):
        super().__init__(message)
        self.check = check
        self.message = message

    def as_check(self) -> CheckResult:
        return CheckResult(self.check, False, self.message)
