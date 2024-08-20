from dataclasses import dataclass
from enum import Enum
import random


@dataclass
class Team:
    class Role(Enum):
        ATTACK = 0
        MIDFIELD = 1
        DEFENSE = 2

    full_name: str
    familiar_name: str
    abbr: str
    color: str
    players: list[str]

    def get_goalkeeper(self):
        return self.players[0] if self.players else None

    def __len__(self):
        return len(self.players)

    def random_order(
        self, include_goalkeeper: bool = True, exclude: list[str] = None
    ) -> list[str]:
        exclude = exclude or []
        player_pool = self.players[1:] if not include_goalkeeper else self.players[:]
        filtered_players = [player for player in player_pool if player not in exclude]
        return random.sample(filtered_players, len(filtered_players))
