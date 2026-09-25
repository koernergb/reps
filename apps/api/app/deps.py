from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.local_mode import get_local_user, get_session
from app.models import User

SessionDependency = Annotated[Session, Depends(get_session)]


def current_user(session: SessionDependency) -> User:
    """Resolve the acting user. Local mode has exactly one user; authenticated modes must
    replace this dependency so every user-scoped query keeps using `user.id`."""
    return get_local_user(session)


UserDependency = Annotated[User, Depends(current_user)]
