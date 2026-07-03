from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import time


@dataclass
class StableResult:
    label: str = "UNKNOWN"
    confidence: float = 0.0
    stable_seconds: float = 0.0
    triggered: bool = False


class TemporalStabilizer:
    """Suppress one-frame noise and repeated triggers."""

    def __init__(
        self,
        window_size: int = 12,
        required_ratio: float = 0.75,
        hold_seconds: float = 0.55,
        release_seconds: float = 0.35,
    ) -> None:
        self.samples: deque[tuple[str, float]] = deque(maxlen=window_size)
        self.required_ratio = required_ratio
        self.hold_seconds = hold_seconds
        self.release_seconds = release_seconds
        self._candidate = "UNKNOWN"
        self._candidate_since = time.monotonic()
        self._latched = "UNKNOWN"
        self._unknown_since = time.monotonic()

    def update(self, label: str, confidence: float) -> StableResult:
        now = time.monotonic()
        self.samples.append((label, confidence))
        counts = Counter(item[0] for item in self.samples)
        dominant, count = counts.most_common(1)[0]
        ratio = count / len(self.samples)
        accepted = (
            dominant
            if dominant != "UNKNOWN" and ratio >= self.required_ratio
            else "UNKNOWN"
        )

        if accepted != self._candidate:
            self._candidate = accepted
            self._candidate_since = now

        stable_seconds = now - self._candidate_since
        triggered = False
        if accepted == "UNKNOWN":
            if now - self._unknown_since >= self.release_seconds:
                self._latched = "UNKNOWN"
        else:
            self._unknown_since = now
            if (
                stable_seconds >= self.hold_seconds
                and accepted != self._latched
            ):
                self._latched = accepted
                triggered = True

        matching = [
            item_confidence
            for item_label, item_confidence in self.samples
            if item_label == accepted
        ]
        mean_confidence = (
            sum(matching) / len(matching) if matching else 0.0
        )
        return StableResult(
            accepted,
            mean_confidence,
            stable_seconds,
            triggered,
        )
