"""Núcleo de automação do framework de testes de QA."""

from core.adspower import AdsPowerClient, AdsPowerError
from core.browser_manager import BrowserManager, BrowserSession
from core.csv_loader import UserData, load_users_from_csv
from core.executor import QAExecutor
from core.onboarding import ExecutionResult, ExecutionStatus, execute_onboarding
from core.reporter import QAReporter, setup_framework_logging

__all__ = [
    "AdsPowerClient",
    "AdsPowerError",
    "BrowserManager",
    "BrowserSession",
    "UserData",
    "load_users_from_csv",
    "QAExecutor",
    "ExecutionResult",
    "ExecutionStatus",
    "execute_onboarding",
    "QAReporter",
    "setup_framework_logging",
]

