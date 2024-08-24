from __future__ import annotations

from typing import Literal

import attr
import numpy as np


import json

from text_calcio.state.match_phase import MatchPhase


@attr.s(frozen=True, auto_attribs=True)
class MatchConfig:
    tie_breaker: Literal[
        "allow_tie", "on_tie_extra_time_and_penalties", "on_tie_penalties"
    ] = "on_tie_extra_time_and_penalties"
    start_from_phase: MatchPhase = MatchPhase.FIRST_HALF
    goal_added_time_min: float = 0.5
    goal_added_time_max: float = 1.5
    penalty_added_time_min: float = 0.75
    penalty_added_time_max: float = 1.75
    var_added_time_min: float = 1.0
    var_added_time_max: float = 2.0
    standard_action_probability: float = 0.15
    extra_time_action_probability: float = 0.30
    added_time_action_probability: float = 0.45
    default_action_no_goal_probability: float = 0.72
    default_action_goal_probability: float = 0.18
    default_action_own_goal_probability: float = 0.02
    default_action_penalty_probability: float = 0.08
    default_action_var_probability: float = 0.1
    penalties_shoot_count: int = 5

    def __post_init__(self):
        # Verify probabilities that should add up to 1
        action_type_probs = [
            self.default_action_no_goal_probability,
            self.default_action_goal_probability,
            self.default_action_own_goal_probability,
            self.default_action_penalty_probability,
        ]

        total_prob = sum(action_type_probs)
        if not np.isclose(total_prob, 1.0, atol=1e-6):
            raise ValueError(
                f"Action type probabilities should sum to 1, but they sum to {total_prob}"
            )

        # Verify all probabilities are not more than 1
        for key, value in vars(self).items():
            if key.endswith("_probability") and value > 1:
                raise ValueError(
                    f"Config '{key}' must be less than or equal to 1, but it is {value}"
                )

    @classmethod
    def from_json(cls, json_file: str):
        with open(json_file, "r") as f:
            config_data = json.load(f)
        # Retrieve MatchPhase id stored in config to instatiate correct MatchPhase
        config_data["start_from_phase"] = MatchPhase.get_phase_by_id(
            int(config_data["start_from_phase"])
        )
        return cls(**config_data)
