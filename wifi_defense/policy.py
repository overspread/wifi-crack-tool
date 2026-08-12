"""Offline authentication-attempt simulation with rate limiting and lockouts.

The simulator has no networking code. It accepts only user-triggered, synthetic events
for training, audit demonstrations, and policy review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Callable

from .audit import AuditLogger


class SimulationStatus(StrEnum):
    ALLOWED = "allowed"
    LOCKED = "locked"
    SUCCESS = "success"


@dataclass(frozen=True)
class SimulationResult:
    """Outcome of one synthetic, offline training event."""

    status: SimulationStatus
    profile: str
    attempts_in_window: int
    locked_until: datetime | None
    message: str


class OfflineAuthSimulator:
    """Apply a local rate-limit policy to synthetic authentication events only."""

    def __init__(
        self,
        audit_logger: AuditLogger,
        max_failures: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 900,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_failures < 1 or window_seconds < 1 or lockout_seconds < 1:
            raise ValueError("所有策略参数必须为正整数")
        self.audit_logger = audit_logger
        self.max_failures = max_failures
        self.window = timedelta(seconds=window_seconds)
        self.lockout = timedelta(seconds=lockout_seconds)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._failed_attempts: dict[str, list[datetime]] = {}
        self._locked_until: dict[str, datetime] = {}

    def simulate(self, profile: str, outcome: str) -> SimulationResult:
        """Record a simulated success or failure without contacting any network."""
        normalized_profile = profile.strip()[:64] or "未命名演示配置"
        normalized_outcome = outcome.strip().lower()
        if normalized_outcome not in {"success", "failure"}:
            raise ValueError("演示结果只能是 success 或 failure")

        now = self._clock()
        locked_until = self._locked_until.get(normalized_profile)
        if locked_until and now < locked_until:
            result = SimulationResult(
                SimulationStatus.LOCKED,
                normalized_profile,
                len(self._active_attempts(normalized_profile, now)),
                locked_until,
                f"演示配置处于锁定状态，预计于 {locked_until.isoformat()} 解锁。",
            )
            self.audit_logger.record(
                "synthetic_attempt_blocked",
                normalized_profile,
                {"status": result.status, "locked_until": locked_until.isoformat()},
            )
            return result

        if normalized_outcome == "success":
            self._failed_attempts.pop(normalized_profile, None)
            self._locked_until.pop(normalized_profile, None)
            result = SimulationResult(
                SimulationStatus.SUCCESS,
                normalized_profile,
                0,
                None,
                "已记录一次合成的成功事件，并重置该配置的失败计数。",
            )
            self.audit_logger.record("synthetic_success", normalized_profile, {"status": result.status})
            return result

        attempts = self._active_attempts(normalized_profile, now)
        attempts.append(now)
        self._failed_attempts[normalized_profile] = attempts
        if len(attempts) >= self.max_failures:
            until = now + self.lockout
            self._locked_until[normalized_profile] = until
            result = SimulationResult(
                SimulationStatus.LOCKED,
                normalized_profile,
                len(attempts),
                until,
                f"达到 {self.max_failures} 次合成失败阈值；已模拟锁定策略。",
            )
            self.audit_logger.record(
                "synthetic_lockout",
                normalized_profile,
                {
                    "status": result.status,
                    "attempts_in_window": len(attempts),
                    "locked_until": until.isoformat(),
                },
            )
            return result

        result = SimulationResult(
            SimulationStatus.ALLOWED,
            normalized_profile,
            len(attempts),
            None,
            f"已记录合成失败事件：当前窗口内 {len(attempts)}/{self.max_failures} 次。",
        )
        self.audit_logger.record(
            "synthetic_failure",
            normalized_profile,
            {"status": result.status, "attempts_in_window": len(attempts)},
        )
        return result

    def reset_profile(self, profile: str) -> None:
        """Reset a synthetic profile's in-memory counters and record that action."""
        normalized_profile = profile.strip()[:64] or "未命名演示配置"
        self._failed_attempts.pop(normalized_profile, None)
        self._locked_until.pop(normalized_profile, None)
        self.audit_logger.record("synthetic_policy_reset", normalized_profile)

    def _active_attempts(self, profile: str, now: datetime) -> list[datetime]:
        cutoff = now - self.window
        return [item for item in self._failed_attempts.get(profile, []) if item >= cutoff]
