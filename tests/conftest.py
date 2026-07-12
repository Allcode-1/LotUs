import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.session import Base, get_db
from app.main import app as fastapi_app
import app.models  # noqa: F401


load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is not set")
    return value


DATABASE_URL = os.getenv("DATABASE_URL")
TEST_DATABASE_URL = require_env("TEST_DATABASE_URL")


def validate_test_database_url() -> None:
    test_url = make_url(TEST_DATABASE_URL)

    if DATABASE_URL:
        main_url = make_url(DATABASE_URL)
        if (
            test_url.drivername == main_url.drivername
            and test_url.username == main_url.username
            and test_url.host == main_url.host
            and test_url.port == main_url.port
            and test_url.database == main_url.database
        ):
            raise RuntimeError(
                "TEST_DATABASE_URL points to the main database. "
                "Refusing to run destructive test setup."
            )

    if not test_url.database or "test" not in test_url.database.lower():
        raise RuntimeError(
            "TEST_DATABASE_URL must point to a dedicated test database "
            "(database name should contain 'test')."
        )


validate_test_database_url()


engine_options = {}
if make_url(TEST_DATABASE_URL).get_backend_name() == "sqlite":
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(TEST_DATABASE_URL, echo=False, **engine_options)


@pytest.fixture(scope="session")
def test_engine():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session):
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(fastapi_app) as test_client:
        yield test_client
    
    fastapi_app.dependency_overrides.clear()
