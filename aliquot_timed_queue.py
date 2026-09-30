"""Timed queue class

This class is used to wait 3 minutes after processing an sequence before making sure it is complete.
"""

import heapq
import time

class AliquotTimedQueue:
    """Queue with wait time"""

    def __init__(self, time_interval: int):
        """Initializes the queue with a mandatory delay interval in seconds.

        Attributes:
            time_interval: Time to wait before returning a sequence.
            _queue: Holds the times and sequences for heapq.
        """

        self.time_interval = time_interval
        self._queue = []

    def add_item(self, seq: int) -> None:
        """Adds an item with a timestamp set to now() + time_interval.
        Args:
            seq: Sequence to add to queue.
        """

        available_at = time.time() + self.time_interval
        heapq.heappush(self._queue, (available_at, seq))

    def get_item(self) -> int | None:
        """Gets item from queue if it exists.

        Returns:
             seq if time_interval has passed since oldest insertion. Otherwise None
        """
        if self.is_empty():
            return None

        # Peek at the item with the smallest timestamp
        available_at, _ = self._queue[0]

        if time.time() >= available_at:
            _, ready_seq = heapq.heappop(self._queue)
            return ready_seq

        return None

    def is_empty(self) -> bool:
        """Returns True if the queue contains no elements, False otherwise."""

        return len(self._queue) == 0
