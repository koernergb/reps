from collections.abc import Iterator
from typing import Final

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import User

LOCAL_USER_ID: Final = "00000000-0000-4000-8000-000000000001"


def get_local_user(session: Session) -> User:
    user = session.get(User, LOCAL_USER_ID)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "local_data_not_initialized",
                "message": "Run the documented database seed command before using Reps.",
            },
        )
    return user


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
