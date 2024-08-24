from enum import Enum
import random
from typing import Optional

import attr


@attr.s(frozen=True)
class Team:
    class Role(Enum):
        ATTACK = 0
        MIDFIELD = 1
        DEFENSE = 2

    full_name: str = attr.ib()
    familiar_name: str = attr.ib()
    short_name: str = attr.ib()
    color: str = attr.ib()
    players: tuple[str, ...] = attr.ib()

    def get_goalkeeper(self):
        return self.players[0] if self.players else None

    def __len__(self):
        return len(self.players)

    def random_order(
        self, include_goalkeeper: bool = True, exclude: Optional[list[str]] = None
    ) -> list[str]:
        exclude = exclude or []
        player_pool = self.players[1:] if not include_goalkeeper else self.players[:]
        filtered_players = [player for player in player_pool if player not in exclude]
        return random.sample(filtered_players, len(filtered_players))
