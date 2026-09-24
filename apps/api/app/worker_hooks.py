"""Registers post-execution hooks. Later milestones append their hooks here."""

from app.execution.service import completion_hooks


def register_hooks() -> None:
    # Imported lazily so the worker only loads modules it needs.
    del completion_hooks[:]
