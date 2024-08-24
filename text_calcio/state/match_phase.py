from __future__ import annotations

from abc import ABCMeta
from enum import Enum, EnumMeta
from functools import total_ordering

import cattrs


class ABCEnumMeta(ABCMeta, EnumMeta):
    """
    Hack
    """

    pass


@total_ordering
class MatchPhase(Enum):
    FIRST_HALF = "FIRST_HALF"
    SECOND_HALF = "SECOND_HALF"
    FIRST_EXTRA_TIME = "FIRST_EXTRA_TIME"
    SECOND_EXTRA_TIME = "SECOND_EXTRA_TIME"
    PENALTIES = "PENALTIES"

    def __init__(self, id) -> None:
        self.id = id
        match id:
            case "FIRST_HALF":
                self.duration_minutes = 45
            case "SECOND_HALF":
                self.duration_minutes = 45
            case "FIRST_EXTRA_TIME":
                self.duration_minutes = 15
            case "SECOND_EXTRA_TIME":
                self.duration_minutes = 15
            case "PENALTIES":
                self.duration_minutes = 0

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

        return self.id < other.id

    def from_name(self, name: str):
        MatchPhase[self.name]

    @classmethod
    def get_phase_by_id(cls, id: int):
        match_phase_instances = list(cls)
        if id < 0 or id >= len(match_phase_instances):
            raise ValueError(
                f"MatchPhase ids must be between 0 and {len(match_phase_instances) - 1}"
            )
        return list(cls)[id]

    def next_phase(self):
        if self == MatchPhase.PENALTIES:
            raise ValueError("No more phases after PENALTIES")
        return MatchPhase.get_phase_by_id(self.id + 1)


# Hooks used to register globally how to handle serialization and deseriaziation for this function
# Serialize
cattrs.register_unstructure_hook(MatchPhase, lambda enum: enum.name)
# Deserialize
cattrs.register_structure_hook(MatchPhase, lambda name, _: MatchPhase[name])
