from functools import total_ordering

import attr

from text_calcio.state.match_phase import MatchPhase


@total_ordering
@attr.s(frozen=True, auto_attribs=True)
class MatchTime:
    phase: MatchPhase = MatchPhase.FIRST_HALF
    minute: int = 1

    def __lt__(self, other):
        if not isinstance(other, MatchTime):
            return NotImplemented
        return self.phase < other.phase or (
            self.phase == other.phase and self.minute < other.minute
        )

    def __add__(self, minutes):
        if not isinstance(minutes, int):
            return NotImplemented
        return self.add_minutes(minutes)

    def __sub__(self, minutes):
        if not isinstance(minutes, int):
            return NotImplemented
        return self.add_minutes(-minutes)

    def add_minutes(self, minutes: int):
        return MatchTime(self.phase, self.minute + minutes)

    def next_phase(self):
        return MatchTime(self.phase.next_phase(), 1)

    def is_phase_time_expired(self, stoppage_time: float) -> bool:
        return self.minute > self.phase.duration_minutes + stoppage_time
