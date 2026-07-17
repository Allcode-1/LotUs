from math import ceil
from time import monotonic


class FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self.get_calls: list[str] = []
        self.setex_calls: list[tuple[str, int, str]] = []
        self.delete_calls: list[tuple[str, ...]] = []
        self.incr_calls: list[str] = []
        self.publish_calls: list[tuple[str, str]] = []

    def get(self, name: str) -> str | None:
        self._purge_if_expired(name)
        self.get_calls.append(name)
        return self._values.get(name)

    def setex(self, name: str, time: int, value: str) -> bool:
        self.setex_calls.append((name, time, value))
        self._values[name] = value
        self._expires_at[name] = monotonic() + time
        return True

    def delete(self, *names: str) -> int:
        self.delete_calls.append(tuple(names))
        deleted_count = 0
        for name in names:
            self._purge_if_expired(name)
            if name in self._values:
                deleted_count += 1
                self._values.pop(name, None)
            self._expires_at.pop(name, None)
        return deleted_count

    def incr(self, name: str) -> int:
        self._purge_if_expired(name)
        self.incr_calls.append(name)
        current_value = int(self._values.get(name, "0")) + 1
        self._values[name] = str(current_value)
        return current_value

    def expire(self, name: str, time: int) -> bool:
        self._purge_if_expired(name)
        if name not in self._values:
            return False
        self._expires_at[name] = monotonic() + time
        return True

    def ttl(self, name: str) -> int:
        self._purge_if_expired(name)
        if name not in self._values:
            return -2
        expires_at = self._expires_at.get(name)
        if expires_at is None:
            return -1
        return max(ceil(expires_at - monotonic()), 0)

    def publish(self, channel: str, message: str) -> int:
        self.publish_calls.append((channel, message))
        return 1

    def _purge_if_expired(self, name: str) -> None:
        expires_at = self._expires_at.get(name)
        if expires_at is not None and expires_at <= monotonic():
            self._values.pop(name, None)
            self._expires_at.pop(name, None)
