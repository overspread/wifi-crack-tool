"""Offline WiFi security education utilities.

This package intentionally performs no WiFi discovery, packet capture, authentication,
or network connection. It is designed only for local password-strength assessment,
training simulations, and local audit records.
"""

from .audit import AuditLogger
from .policy import OfflineAuthSimulator, SimulationStatus
from .strength import PasswordAssessment, assess_password

__all__ = [
    "AuditLogger",
    "OfflineAuthSimulator",
    "PasswordAssessment",
    "SimulationStatus",
    "assess_password",
]
