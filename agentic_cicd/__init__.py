"""Agentic CI/CD control plane foundation.

This package intentionally separates reasoning/planning from privileged execution.
All execution flows through typed tasks, policy evaluation, runner selection, and audit.
"""

from agentic_cicd.core.intent import Intent, IntentParser
from agentic_cicd.core.pipeline import PipelineIR

__all__ = ["Intent", "IntentParser", "PipelineIR"]
__version__ = "0.3.0"
