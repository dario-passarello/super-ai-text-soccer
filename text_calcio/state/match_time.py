from functools import total_ordering

import attr

from text_calcio.state.match_phase import MatchPhase


@total_ordering
@attr.s(frozen=True, auto_attribs=True)
class MatchTime:
    start_minute: int = 0
    minute: int = 1
    phase: MatchPhase = MatchPhase.FIRST_HALF

    def __lt__(self, other):
        if not isinstance(other, MatchTime):
            return NotImplemented
        return self.phase < other.phase or (
            self.phase == other.phase and self.minute < other.minute
        )

    def __add__(self, delta_minutes):
        if not isinstance(delta_minutes, int):
            return NotImplemented
        return self.add_minutes(delta_minutes)

    def __sub__(self, delta_minutes):
        if not isinstance(delta_minutes, int):
            return NotImplemented
        return self.add_minutes(-delta_minutes)

    def add_minutes(self, delta_minutes: int):
        return MatchTime(self.start_minute, self.minute + delta_minutes, self.phase)

    def absolute_minute(self):
        return self.start_minute + self.minute

    def next_phase(self):
        return MatchTime(
            self.start_minute + self.minute + 1, 1, self.phase.next_phase()
        )

    def is_phase_time_expired(self, stoppage_time: float) -> bool:
        return self.minute > self.phase.duration_minutes + stoppage_time
