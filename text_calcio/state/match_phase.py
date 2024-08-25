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

    def __init__(self, id: str) -> None:
        self.string_id = id
        self.duration_minutes = self._get_duration(id)

    def _get_duration(self, id: str) -> int:
        match id:
            case "FIRST_HALF" | "SECOND_HALF":
                return 45
            case "FIRST_EXTRA_TIME" | "SECOND_EXTRA_TIME":
                return 15
            case "PENALTIES":
                return 0
        raise ValueError(f"Invalid MatchPhase id: {id}")

    @property
    def id(self) -> int:
        return list(self.__class__).index(self)

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
        return MatchPhase[self.name]

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
