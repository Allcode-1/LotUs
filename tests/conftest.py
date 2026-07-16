import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth import utils as auth_utils
from app.api.v1 import auction as auction_api
from app.db.session import Base, get_db
from app.main import app as fastapi_app
from app.services import item as item_service
from app.services import item_image as item_image_service
from app.ws.auction import auction_ws_manager
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


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    monkeypatch.setattr(
        auth_utils,
        "hash_password",
        lambda password: f"test-hash:{password}",
    )
    monkeypatch.setattr(
        auth_utils,
        "validate_password",
        lambda password, hashed_password: hashed_password == f"test-hash:{password}",
    )


@pytest.fixture(autouse=True)
def fake_object_storage(monkeypatch):
    def fake_upload_fileobj(fileobj, storage_key: str, content_type: str) -> None:
        fileobj.seek(0)

    monkeypatch.setattr(item_image_service, "upload_fileobj", fake_upload_fileobj)
    monkeypatch.setattr(
        item_image_service,
        "create_presigned_url",
        lambda storage_key: f"https://storage.test/{storage_key}",
    )
    monkeypatch.setattr(item_image_service, "delete_object", lambda storage_key: None)
    monkeypatch.setattr(item_service, "delete_object", lambda storage_key: None)


@pytest.fixture(autouse=True)
def disable_auto_confirm_timer(monkeypatch):
    async def no_auto_confirm(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(
        auction_api.auction_timers,
        "auto_confirm_lot_sale",
        no_auto_confirm,
    )


@pytest.fixture(autouse=True)
def clear_websocket_connections():
    auction_ws_manager._connections.clear()
    yield
    auction_ws_manager._connections.clear()
