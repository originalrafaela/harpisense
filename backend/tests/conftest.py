import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--postgres-url",
        action="store",
        default=os.getenv("HARPI_TEST_DATABASE_URL"),
        help="PostgreSQL URL used by integration tests.",
    )


@pytest.fixture(scope="session")
def postgres_url(pytestconfig: pytest.Config) -> str:
    url = pytestconfig.getoption("--postgres-url")
    if not url:
        pytest.skip("Set HARPI_TEST_DATABASE_URL or pass --postgres-url to run PostgreSQL integration tests.")
    if not url.startswith("postgresql"):
        pytest.fail("Integration tests require PostgreSQL; SQLite must not be used for compatibility claims.")
    return url


@pytest.fixture(scope="session")
def engine(postgres_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(postgres_url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        pytest.fail("Integration tests require the PostgreSQL dialect.")
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL test database is unavailable: {exc}")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture()
def client(engine: Engine):
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    original_admin_username = settings.admin_username
    original_admin_password = settings.admin_password
    original_gateway_username = settings.gateway_username
    original_gateway_password = settings.gateway_password
    settings.admin_username = "admin"
    settings.admin_password = "secret"
    settings.gateway_username = "harpisense.gateway.edge-1"
    settings.gateway_password = "gateway-secret"
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        settings.admin_username = original_admin_username
        settings.admin_password = original_admin_password
        settings.gateway_username = original_gateway_username
        settings.gateway_password = original_gateway_password
