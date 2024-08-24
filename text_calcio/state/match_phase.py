from __future__ import annotations

from enum import Enum
from functools import total_ordering

import cattrs


@total_ordering
class MatchPhase(Enum):
    FIRST_HALF = 0
    SECOND_HALF = 1
    FIRST_EXTRA_TIME = 2
    SECOND_EXTRA_TIME = 3
    PENALTIES = 4

    def __contains__(self, value: object) -> bool:
        if hasattr(value, "phase"):
            if isinstance(value.phase, MatchPhase) and value.phase == self:  # type: ignore
                return True
            else:
                return False
        else:
            return NotImplemented

    def __lt__(self, other):
        if not isinstance(other, MatchPhase):
            return NotImplemented

        return self.value < other.value

    def from_name(self, name: str):
        return MatchPhase[name]

    @property
    def duration_minutes(self) -> int:
        match self:
            case self.FIRST_HALF:
                return 45
            case self.SECOND_HALF:
                return 45
            case self.FIRST_EXTRA_TIME:
                return 15
            case self.SECOND_EXTRA_TIME:
                return 15
            case self.PENALTIES:
                return 0
        return 0

    @classmethod
    def get_phase_by_id(cls, id: int):
        match_phase_instances = list(cls)
        if id < 0 or id >= len(match_phase_instances):
            raise ValueError(
                f"MatchPhase ids must be between 0 and {len(match_phase_instances) - 1}"
            )
        return list(cls)[id]

    def next_phase(self) -> MatchPhase:
        if self == MatchPhase.PENALTIES:
            raise ValueError("No more phases after PENALTIES")
        match self:
            case self.FIRST_HALF:
                return self.SECOND_HALF
            case self.SECOND_HALF:
                return self.FIRST_EXTRA_TIME
            case self.FIRST_EXTRA_TIME:
                return self.SECOND_EXTRA_TIME
            case self.SECOND_EXTRA_TIME:
                return self.PENALTIES


# Hooks used to register globally how to handle serialization and deseriaziation for this function
# Serialize
cattrs.register_unstructure_hook(MatchPhase, lambda enum: enum.name)
# Deserialize
cattrs.register_structure_hook(MatchPhase, lambda name, _: MatchPhase[name])
