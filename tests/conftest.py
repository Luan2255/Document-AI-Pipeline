"""Provide an isolated SQLite database and FastAPI test client."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.session import get_db_session


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Run requests against an in-memory database without external services."""

    import app.main as main_module

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session_factory = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(main_module, "engine", test_engine)

    def override_database_session():
        """Yield a session bound to the isolated test database."""

        with test_session_factory() as session:
            yield session

    main_module.app.dependency_overrides[get_db_session] = override_database_session
    main_module.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, llm_api_key="test-key"
    )

    try:
        with TestClient(main_module.app) as test_client:
            yield test_client
    finally:
        main_module.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()