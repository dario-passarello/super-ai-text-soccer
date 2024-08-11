from dataclasses import dataclass
from enum import Enum
import random


@dataclass
class Team:
    class Role(Enum):
        ATTACK = 0
        MIDFIELD = 1
        DEFENSE = 2

    name : str
    abbr : str
    color : str
    players : list[str]


    def get_goalkeeper(self):
        return self.players[0]
    
    def random_order(self, no_goalie=False, exclude_also=[]):
        if no_goalie:
            clone_list = list(self.players[1:])
        else:
            clone_list = list(self.players[0])
        for player in exclude_also:
            try:
                atk_player_idx = clone_list.index(player)
            except ValueError:
                pass
            else:
                del clone_list[atk_player_idx]

        random.shuffle(clone_list)
        return clone_list


