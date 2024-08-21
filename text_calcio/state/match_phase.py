from enum import Enum
from functools import total_ordering


@total_ordering
class MatchPhase(Enum):
    FIRST_HALF = 0, 45
    SECOND_HALF = 1, 45
    FIRST_EXTRA_TIME = 2, 15
    SECOND_EXTRA_TIME = 3, 15
    PENALTIES = 4, 0

    def __init__(self, id: int, duration_minutes: int) -> None:
        self.id = id
        self.duration_minutes = duration_minutes

    def __lt__(self, other):
        if not isinstance(other, MatchPhase):
            return NotImplemented

        return self.id < other.id
