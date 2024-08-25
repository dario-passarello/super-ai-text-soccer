import random
from typing import Literal

import attr
import numpy as np


PenaltyDirection = Literal[
    "left_top", "left_low", "center_top", "center_low", "right_top", "right_low"
]

ALL_PENALTY_DIRECTIONS: tuple[PenaltyDirection, ...] = (
    "left_top",
    "left_low",
    "center_top",
    "center_low",
    "right_top",
    "right_low",
)


@attr.s(frozen=True, auto_attribs=True)
class Penalty:
    player_kicking: str
    goalkeeper: str
    kick_direction: PenaltyDirection
    dive_direction: PenaltyDirection
    is_goal: bool
    is_out: bool

    def __post_init__(self):
        if self.is_out and self.is_goal:
            raise ValueError("A penalty cannot be both out and a goal")

    @staticmethod
    def determine_penalty_outcome(
        kick_direction: PenaltyDirection, dive_direction: PenaltyDirection
    ) -> tuple[bool, bool]:
        """
        Determines the outcome of a penalty kick based on the kick and dive directions.

        Args:
            kick_direction (PenaltyDirection): The direction of the penalty kick.
            dive_direction (PenaltyDirection): The direction of the goalkeeper's dive.

        Returns:
            tuple[bool, bool]: A tuple containing two booleans:
                - is_goal: True if the penalty results in a goal, False otherwise.
                - is_out: True if the penalty is kicked out of bounds, False otherwise.
        """
        x_kick, _ = kick_direction.split("_")
        x_dive, _ = dive_direction.split("_")

        # TODO: move to external config
        kick_error_chance = 0.1

        random_value = np.random.random()

        if random_value < kick_error_chance:
            is_goal, is_out = False, True  # Kicked out (missed the goal)
        elif kick_direction == dive_direction:
            is_goal, is_out = False, False  # Saved by the goalkeeper
        elif x_kick != x_dive:
            is_goal, is_out = True, False  # Goal scored
        else:
            is_goal = random_value < 0.5  # 50% chance of goal when x directions match
            is_out = False

        return is_goal, is_out

    @staticmethod
    def create_player_kicked_penalty(
        player_kicking: str,
        goalkeeper: str,
        kick_direction: PenaltyDirection,
        dive_direction: PenaltyDirection,
    ):
        is_goal, is_out = Penalty.determine_penalty_outcome(
            kick_direction, dive_direction
        )

        return Penalty(
            player_kicking, goalkeeper, kick_direction, dive_direction, is_goal, is_out
        )

    @staticmethod
    def create_auto_penalty(player_kicking: str, goalkeeper: str):
        return Penalty.create_player_kicked_penalty(
            player_kicking,
            goalkeeper,
            random.choice(ALL_PENALTY_DIRECTIONS),
            random.choice(ALL_PENALTY_DIRECTIONS),
        )
