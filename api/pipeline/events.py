"""Structured run events.

Every stage of a render emits RunEvents carrying a real offset from the start of
the run, measured on a monotonic clock. The collected events are both the live
NDJSON progress stream and the persisted `run.json` a demo page replays, so the
timings must never be synthesised.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List
import time

# Closed sets: a consumer colours and groups by these, so a typo must fail loudly
# rather than silently introduce a new category.
STAGES = ("code_generation", "sanitize", "validate", "render", "done")
LEVELS = ("info", "warn", "error")


@dataclass(frozen=True)
class RunEvent:
    t_ms: int
    stage: str
    level: str
    msg: str

    def to_dict(self) -> Dict:
        return {
            "t_ms": self.t_ms,
            "stage": self.stage,
            "level": self.level,
            "msg": self.msg,
        }


class RunRecorder:
    """Collects RunEvents for a single run.

    `clock` is injectable so tests can assert on timings without sleeping.
    """

    def __init__(self, slug: str, clock: Callable[[], float] = time.monotonic):
        self.slug = slug
        self._clock = clock
        self._start = clock()
        self.started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.events: List[RunEvent] = []

    def elapsed_ms(self) -> int:
        # round, not int: truncation biases every offset downward by up to 1ms
        # and float subtraction makes 3.82s land at 3819.999...
        return round((self._clock() - self._start) * 1000)

    def emit(self, stage: str, msg: str, level: str = "info") -> RunEvent:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
        if level not in LEVELS:
            raise ValueError(f"unknown level {level!r}; expected one of {LEVELS}")
        event = RunEvent(t_ms=self.elapsed_ms(), stage=stage, level=level, msg=msg)
        self.events.append(event)
        return event

    def to_run_json(self) -> Dict:
        return {
            "slug": self.slug,
            "started_at": self.started_at,
            "total_ms": self.events[-1].t_ms if self.events else self.elapsed_ms(),
            "events": [e.to_dict() for e in self.events],
        }
