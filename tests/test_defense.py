from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from wifi_defense.app import WifiDefenseApp
from wifi_defense.audit import AuditLogger
from wifi_defense.policy import OfflineAuthSimulator, SimulationStatus
from wifi_defense.strength import assess_password


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class InterfaceImportTests(unittest.TestCase):
    def test_offline_interface_is_available(self) -> None:
        self.assertTrue(callable(WifiDefenseApp))


class PasswordAssessmentTests(unittest.TestCase):
    def test_weak_common_pattern_receives_feedback(self) -> None:
        result = assess_password("password123")
        self.assertLessEqual(result.score, 1)
        self.assertTrue(any("常见" in item for item in result.feedback))
        self.assertEqual(result.length, 11)

    def test_long_varied_password_receives_good_score(self) -> None:
        result = assess_password("Frost!7Lake#Orbit$92")
        self.assertGreaterEqual(result.score, 3)
        self.assertEqual(result.label, "强")


class OfflineSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.audit = AuditLogger(Path(self.tempdir.name))
        self.clock = MutableClock()
        self.simulator = OfflineAuthSimulator(
            self.audit,
            max_failures=3,
            window_seconds=60,
            lockout_seconds=120,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_failure_threshold_locks_only_synthetic_profile(self) -> None:
        self.assertEqual(self.simulator.simulate("training-profile", "failure").status, SimulationStatus.ALLOWED)
        self.assertEqual(self.simulator.simulate("training-profile", "failure").status, SimulationStatus.ALLOWED)
        locked = self.simulator.simulate("training-profile", "failure")
        self.assertEqual(locked.status, SimulationStatus.LOCKED)
        self.assertIsNotNone(locked.locked_until)

        blocked = self.simulator.simulate("training-profile", "success")
        self.assertEqual(blocked.status, SimulationStatus.LOCKED)
        self.assertGreaterEqual(len(self.audit.read_recent()), 4)

    def test_window_expiry_clears_old_failures(self) -> None:
        self.simulator.simulate("training-profile", "failure")
        self.clock.advance(61)
        result = self.simulator.simulate("training-profile", "failure")
        self.assertEqual(result.status, SimulationStatus.ALLOWED)
        self.assertEqual(result.attempts_in_window, 1)


if __name__ == "__main__":
    unittest.main()
