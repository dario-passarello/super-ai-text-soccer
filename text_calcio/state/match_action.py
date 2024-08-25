from __future__ import annotations

from typing import Literal, Optional

import attr


from text_calcio.state.match_time import MatchTime
from text_calcio.state.penalty import Penalty


ActionType = Literal["goal", "no_goal", "penalty", "own_goal"]


@attr.s(auto_attribs=True, frozen=True)
class MatchAction:
    """
    An Action object represents a single goal attempt by one of the two teams
    in a match.

    The Action is created from an ActionBlueprint, which provides the template
    narration, details about who scored, who assisted, and the performance
    evaluations of all players involved in the action.

    If the action results in a penalty, additional details about the penalty
    are stored in the penalty field.
    """

    team_atk_id: Literal[0, 1]
    time: MatchTime
    type: ActionType
    goal_player: Optional[str]
    assist_player: Optional[str]
    player_assignments: dict[str, str]
    support_assignments: dict[str, str]
    penalty: Optional[Penalty] = None
    var_review: bool = False

    def is_goal(self) -> bool:
        return self.goal_player is not None and self.type in ["goal", "penalty"]

    def is_own_goal(self) -> bool:
        return self.goal_player is not None and "def_" in self.goal_player

    def is_penalty_pending(self) -> bool:
        return self.type == "penalty" and self.penalty is None

    def kick_penalty(self, penalty: Penalty):
        if not self.is_penalty_pending():
            raise RuntimeError("There is no penalty to kick")

        goal_player = penalty.is_goal if penalty.player_kicking else None

        return attr.evolve(
            self, penalty=penalty, assist_player=None, goal_player=goal_player
        )

    def get_name_from_placeholder(self, role: str):
        return self.placeholders_to_names_map()[role.strip("{}")]

    def get_placeholder_from_name(self, name: str):
        return self.names_to_placeholders_map()[name]

    def placeholders_to_names_map(self):
        return {**self.player_assignments, **self.support_assignments}

    # TODO: this might have issues if the same player name is used for multiple roles/teams
    def names_to_placeholders_map(self):
        return {v: k for k, v in self.placeholders_to_names_map().items()}

    def get_atk_players_assignments(self):
        return {
            placeholder: name
            for placeholder, name in self.player_assignments.items()
            if "atk_" in placeholder
        }

    def get_absolute_minute(self):
        return self.time.absolute_minute()
