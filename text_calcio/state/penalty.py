from dataclasses import dataclass
import random
from typing import Literal

import numpy as np


PenaltyDirection = Literal['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low']
ALL_PENALTY_DIRECTIONS : list[PenaltyDirection] = ['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low']

@dataclass
class Penalty:
    player_kicking : str
    goal_keeper : str
    kick_direction : PenaltyDirection
    dive_direction : PenaltyDirection
    is_goal : bool

    @staticmethod
    def calculate_is_goal(kick_direction : PenaltyDirection, dive_direction : PenaltyDirection):
        x_kick, y_kick = kick_direction.split('_')
        x_dive, y_dive = dive_direction.split('_')
        if kick_direction == dive_direction:
            return False
        if x_kick != x_dive:
            return True
        else:
            return np.random.random() < 0.5
        
    @staticmethod
    def create_player_kicked_penalty(player_kicking : str, goal_keeper: str, kick_direction : PenaltyDirection, dive_direction : PenaltyDirection):
        is_goal = Penalty.calculate_is_goal(kick_direction, dive_direction)

        return Penalty(
            player_kicking,
            goal_keeper,
            kick_direction,
            dive_direction,
            is_goal
        )

    @staticmethod
    def create_auto_penalty(player_kicking : str, goal_keeper: str):
        kick_direction : PenaltyDirection = random.choice(['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low'])
        dive_direction : PenaltyDirection = random.choice(['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low'])
        is_goal = Penalty.calculate_is_goal(kick_direction, dive_direction)

        return Penalty(
            player_kicking,
            goal_keeper,
            kick_direction,
            dive_direction,
            is_goal
        )

