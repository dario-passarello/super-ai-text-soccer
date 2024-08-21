from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


from text_calcio.loaders.action import ActionBlueprint
from text_calcio.state.penalty import Penalty
from text_calcio.state.stadium import Stadium
from text_calcio.state.team import Team
from text_calcio.state.match_phase import MatchPhase


ActionType = Literal["goal", "no_goal", "penalty", "own_goal"]


@dataclass
class MatchAction:
    """
    An Action object represents a single goal attempt by one of the two teams
    in a match.

    The Action is created from an ActionBlueprint, which provides the template
    narration, details about who scored, who assisted, and the performance
    evaluations of all players involved in the action.

    If the action results in a penalty, additional details about the penalty
    are stored in the penalty_info field.
    """

    team_atk_id: Literal[0, 1]
    phase: MatchPhase
    minute: int
    type: ActionType
    goal_player: Optional[str]
    assist_player: Optional[str]
    players_evaluation: dict[str, int]
    sentences: list[str]
    player_assigments: dict[str, str]
    support_assigments: dict[str, str]
    penalty_info: Optional[Penalty] = None

    def __post_init__(self):
        if self.type == "penalty":
            self.assist_player = None

            if self.penalty_info is None:
                self.goal_player = None
            else:
                self.goal_player = self.penalty_info.player_kicking

        elif self.type == "own_goal":
            self.assist_player = None

    def is_goal(self) -> bool:
        return self.goal_player is not None

    def is_own_goal(self) -> bool:
        return self.goal_player is not None and "def_" in self.goal_player

    def is_penalty_pending(self) -> bool:
        return self.type == "penalty" and self.penalty_info is None

    def kick_penalty(self, penalty: Penalty):
        if not self.is_penalty_pending():
            raise RuntimeError("There is no penalty to kick")

        self.penalty_info = penalty
        self.assist_player = None

        if penalty.is_goal:
            self.goal_player = penalty.player_kicking
        else:
            self.goal_player = None

    def map_role_to_name(self, role: str):
        role = role.strip("{}")

        return self.get_all_assigments()[role]

    def get_all_assigments(self):
        return {**self.player_assigments, **self.support_assigments}

    def get_atk_players_assignments(self):
        return {
            placeholder: name
            for placeholder, name in self.player_assigments.items()
            if "atk_" in placeholder
        }

    @staticmethod
    def create_from_blueprint(
        action_response: ActionBlueprint,
        phase: MatchPhase,
        minute: int,
        atk_team_id: Literal[0, 1],
        teams: tuple[Team, Team],
        referee: str,
        stadium: Stadium,
    ):
        atk_team = teams[atk_team_id]
        def_team = teams[1 - atk_team_id]

        atk_player_order = atk_team.random_order(include_goalkeeper=False)
        def_player_order = def_team.random_order(include_goalkeeper=False)

        player_assignments = {
            # Attacking team field players
            **{f"atk_{i+1}": player for i, player in enumerate(atk_player_order)},
            "atk_goalkeeper": atk_team.get_goalkeeper(),
            # Defending team field players
            **{f"def_{i+1}": player for i, player in enumerate(def_player_order)},
            "def_goalkeeper": def_team.get_goalkeeper(),
        }

        support_assigments = {
            "referee": referee,
            "stadium": stadium.name,
            "atk_team_name": atk_team.familiar_name,
            "def_team_name": def_team.familiar_name,
        }

        goal_player = action_response.scorer_player
        assist_player = action_response.assist_player

        return MatchAction(
            atk_team_id,
            phase,
            minute,
            action_response.action_type,
            goal_player,
            assist_player,
            action_response.player_evaluation,
            action_response.phrases,
            player_assignments,
            support_assigments,
        )
