import collections
from asyncio import Queue


class SongQueue(Queue):
    loop: bool = False
    repeat: bool = False

    def _init(self, maxsize):
        self._queue = collections.deque()

    def _get(self):
        if self.loop:
            self._queue.rotate(n=1)

        if self.repeat or self.loop:
            return self._queue[0]

        return self._queue.popleft()

    def to_list(self) -> list:
        return list(self._queue)

    def __delitem__(self, key):
        # TODO: improve this making it awaitable
        del self._queue[key]

    def __len__(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0