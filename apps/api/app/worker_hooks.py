"""Registers post-execution hooks run by the worker after each job."""

from app.execution.service import completion_hooks


def register_hooks() -> None:
    from app.interview.service import on_execution_completed

    completion_hooks[:] = [on_execution_completed]
