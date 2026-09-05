"""
Database Session Management

This module provides database connection and session management for the application.

What is this for?
This module handles:
- Creating the database engine (connection pool)
- Providing database sessions to FastAPI route handlers
- Managing database connections efficiently

What is a database session?
A database session is a temporary connection to the database that allows you to:
- Query data
- Add, update, or delete records
- Commit or rollback transactions
- Automatically handle connection cleanup

How it works:
1. The engine is created once when the application starts
2. FastAPI calls get_session() for each request
3. A new session is created and yielded to the route handler
4. After the request completes, the session is automatically closed

Why use sessions?
- Automatic connection management (no need to manually open/close)
- Transaction support (commit/rollback)
- Connection pooling (reuse connections for better performance)
- Thread-safe (each request gets its own session)

How to use in FastAPI routes:
    from fastapi import Depends
    from sqlmodel import Session, select
    from app.db.session import get_session
    from app.models.user import User
    
    @router.get("/users/{user_id}")
    def get_user(user_id: str, session: Session = Depends(get_session)):
        # session is automatically provided by FastAPI
        user = session.get(User, user_id)
        return user
"""

from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.core.config import settings

# Create the database engine
# The engine manages a pool of database connections for efficient reuse
# connect_args={"check_same_thread": False} allows SQLite to work with multiple threads
# (needed for FastAPI's async nature, even though we're using sync database operations)
# pool_size/max_overflow raised above SQLAlchemy's defaults (5/10 = 15 total): every public chat
# request holds a connection for its whole duration (see api/public_chat.py), so the default 15
# becomes the ceiling on simultaneous requests — a class of ~30 needs more headroom than that.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    pool_size=20,
    max_overflow=40,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """Tune each new SQLite connection for concurrent access.

    What is WAL (write-ahead logging)? SQLite's default journal mode gives a writer an
    exclusive lock over the whole database file, blocking every reader until it commits. WAL
    lets readers keep going while a write is in progress instead — needed here because even a
    page load writes a row (visitor_service.log_access), so with ~30 students arriving within
    the same lesson, reads and writes overlap constantly.
    busy_timeout makes a connection that still can't get the lock it needs (e.g. two writers at
    once) wait and retry for up to 5s before raising "database is locked", instead of failing
    immediately. synchronous=NORMAL is the WAL-recommended durability level — full fsync safety
    without paying its cost on every single commit.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_session() -> Generator[Session, None, None]:
    """
    Create and yield a database session.
    
    This is a FastAPI dependency function that provides a database session to route handlers.
    The session is automatically closed after the request completes.
    
    How it works:
    1. FastAPI calls this function when a route needs a session
    2. A new session is created from the engine
    3. The session is yielded to the route handler
    4. After the route completes, the session is automatically closed
    
    Why use a generator?
    - FastAPI automatically handles cleanup after the yield
    - Ensures sessions are always closed, even if an error occurs
    - Prevents connection leaks
    
    Example:
        @router.post("/users")
        def create_user(
            user_data: UserCreate,
            session: Session = Depends(get_session)  # Session is injected here
        ):
            user = User(**user_data.dict())
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
    """
    with Session(engine) as session:
        yield session