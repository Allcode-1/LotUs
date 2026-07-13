from typing import BinaryIO, Protocol


class UploadFileLike(Protocol):
    content_type: str | None
    file: BinaryIO
