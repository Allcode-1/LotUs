from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def use_binary_file_format(openapi_schema: dict[str, Any]) -> None:
    for value in openapi_schema.values():
        if isinstance(value, dict):
            if (
                value.get("type") == "string"
                and value.get("contentMediaType") == "application/octet-stream"
            ):
                value.pop("contentMediaType")
                value["format"] = "binary"

            use_binary_file_format(value)

        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    use_binary_file_format(item)


def setup_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        use_binary_file_format(openapi_schema)
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
