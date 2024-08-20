from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
import random
from typing import Literal, Optional

import numpy as np

from text_calcio.loaders.action import ActionBlueprint, ActionRequest
from text_calcio.loaders.action_provider import AsyncActionProvider
from text_calcio.state.penalty import Penalty
from text_calcio.state.stadium import Stadium
from text_calcio.state.team import Team

import json


ActionType = Literal["goal", "no_goal", "penalty", "own_goal"]


@dataclass
class Action:
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
    phase: Match.Phase
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
        phase: Match.Phase,
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
            **{
                f"atk_{i + 1}": atk_player_order[i] for i in range(0, len(atk_team) - 1)
            },
            "atk_goalkeeper": atk_team.get_goalkeeper(),
            **{
                f"def_{i + 1}": def_player_order[i] for i in range(0, len(def_team) - 1)
            },
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

        return Action(
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


@dataclass
class MatchConfig:
    tie_breaker: Literal[
        "allow_tie", "on_tie_extra_time_and_penalties", "on_tie_penalties"
    ] = "on_tie_extra_time_and_penalties"
    start_from_penalties: bool = False
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
        for attr, value in vars(self).items():
            if attr.endswith("_probability") and value > 1:
                raise ValueError(
                    f"Config '{attr}' must be less than or equal to 1, but it is {value}"
                )

    @classmethod
    def from_json(cls, json_file: str):
        with open(json_file, "r") as f:
            config_data = json.load(f)
        return cls(**config_data)


class Match:
    """
    The match is divided into several phases:
    - First half
    - Second half
    - Additional time
    - Penalties

    Each phase is further divided into minutes.
    At every minute, an Action may occur.

    An Action includes the following details:
    - A human-readable narration of what happened.
    - The attacking and defending teams.
    - The roles of the players involved.
    - The outcome of the action, which can be one of the following:
        - Goal
        - No goal
        - Own goal
        - Penalty

    When the next() method is called:
    - The game clock advances, and an action is generated.
    - Actions can be prefetched to avoid delays in the narration.
    - The method first randomly determines the outcome of the action.
    - It then requests the action_provider to construct an Action object.
        - The creation logic for the action is abstracted; it may be generated
          using AI or retrieved from a database.
    - The action_provider returns a detailed ActionBlueprint, which is then used
      to construct the Action object.
    - The Action object is tied to the Match and added to the list of actions.
    """

    @total_ordering
    class Phase(Enum):
        FIRST_HALF = 0, 45
        SECOND_HALF = 1, 45
        FIRST_EXTRA_TIME = 2, 15
        SECOND_EXTRA_TIME = 3, 15
        PENALTIES = 4, 0

        def __init__(self, id: int, duration_minutes: int) -> None:
            self.id = id
            self.duration_minutes = duration_minutes

        def __lt__(self, other):
            if not isinstance(other, Match.Phase):
                return NotImplemented

            return self.id < other.id

    def __init__(
        self,
        team_1: Team,
        team_2: Team,
        stadium: Stadium,
        referee: str,
        action_provider: AsyncActionProvider,
        config: Optional[MatchConfig] = None,
    ):
        self.config = config or MatchConfig()

        self.teams = (team_1, team_2)

        if self.config.start_from_penalties:
            self.curr_phase: Match.Phase = Match.Phase.PENALTIES
        else:
            self.curr_phase: Match.Phase = Match.Phase.FIRST_HALF

        self.curr_minute: int = 1
        self.stadium = stadium
        self.referee = referee
        self.actions: list[Action] = []
        self.action_provider = action_provider
        self.action_configs = []
        self.added_time: dict[Match.Phase, float] = defaultdict(float)
        self.finished = False

    def get_team_1(self) -> Team:
        """
        Returns the home team object
        """
        return self.teams[0]

    def get_team_2(self) -> Team:
        """
        Returns the away team object
        """
        return self.teams[1]

    def get_added_time_minutes(self, phase: Optional[Match.Phase] = None) -> int:
        """
        Returns the added time minutes for the current phase or for a specific phase

        Parameters
        ---
        phase : Match.Phase or None
            The phase of which you want to get the current added time. If left None
            it returns the added times of the current phase.

        Returns
        ---
        result : int
            The added time minutes of the desired phase
        """
        return int(round(self.added_time[phase or self.curr_phase]))

    def get_current_score(self) -> tuple[int, int]:
        """
        Returns the score calculated for all actions currently contained
        in the Match object.

        NOTE: This function returns the score updated to this action. If you use this
        function for printing the score during an action, you will get the score updated to
        action end, spoiling the end of the action (goal or no-goal).

        Returns
        ---
        result : tuple of (int, int)
            Contains the number of goal scored respectively by the home and away team

        See also
        ---
        get_no_spoiler_score : Similar to this method, but omits in the score calculation the current action.
        """
        score = [0, 0]

        for action in self.actions:
            if action.is_goal():
                score[action.team_atk_id] += 1

        return tuple(score)  # type: ignore

    def get_no_spoiler_score(self) -> tuple[int, int]:
        """
        Returns the score calculated for all actions currently contained
        in the Match object excluding the action happeing in the current minute at the current phase (if present).

        If this function is used to print the score while narrating the action it avoids spoilers by omitting the
        outcome of the current action in the calculation. However it does not represent the current score that can
        be calculated from the Match state.

        Returns
        ---
        result : tuple of (int, int)
            Contains the number of goal scored respectively by the home and away team

        See also
        ---
        get_current_score : Similar to this method, but considres in the score calculation the current action.
        """
        score = [0, 0]
        curr_action = self.get_current_action()

        for action in self.actions:
            if action.is_goal() and action is not curr_action:
                score[action.team_atk_id] += 1

        return tuple(score)  # type: ignore

    def get_current_action(self) -> Optional[Action]:
        """
        Gets the action happeing at the current minute and current phase (curr_minute, curr_phase), if present

        Returns
        ---
        result : Action or None
            Returns the current action, or None if no action is happening at the current minute and phase
        """
        for action in self.actions:
            if action.minute == self.curr_minute and action.phase == self.curr_phase:
                return action

        return None

    def get_all_actions_to_now(self) -> list[Action]:
        actions = []

        for action in self.actions:
            if action.phase < self.curr_phase or (
                action.phase == self.curr_phase and action.minute <= self.curr_minute
            ):
                actions.append(action)

        return actions

    def is_penalty_pending(self) -> bool:
        """
        Checks if a penalty has to be kicked at the current state before continuing with the next() method.
        If the result of this function is True a penalty must be kicked before continuing.

        Returns
        ---
        result : bool
            Returns True if a penalty kick is pending, False otherwise

        See also
        ---
        kick_penalty : method to call if this check returns True
        next : method to call if this check returns False
        """
        curr_action = self.get_current_action()

        return curr_action and curr_action.is_penalty_pending()

    async def next(self) -> None:
        if self.is_penalty_pending():
            raise RuntimeError("Penalty pending, could not advance to next action")

        self.curr_minute += 1

        score_1, score_2 = self.get_current_score()
        is_tie = score_1 == score_2

        if self.curr_phase == Match.Phase.PENALTIES:
            # TODO This may not work in case of sudden death (tie after 5 penalties)
            # penalties shootout has completely different rules
            # Calculate who kicks now
            penalty_kick_count = (self.curr_minute - 1) // 2
            penalties_remaining = max(
                self.config.penalties_shoot_count - penalty_kick_count, 1
            )

            curr_team_kicking = (self.curr_minute + 1) % 2

            # Calculate penalty win condition
            score_curr_team = score_1 if curr_team_kicking == 0 else score_2
            score_other_team = score_2 if curr_team_kicking == 0 else score_1

            if score_curr_team + penalties_remaining < score_other_team:
                # If it is impossible to win
                self.finished = True
            else:
                penalty_blueprint = ActionBlueprint(
                    "penalty", False, [], {}, None, None
                )

                self.actions.append(
                    Action.create_from_blueprint(
                        penalty_blueprint,
                        self.curr_phase,
                        self.curr_minute,
                        curr_team_kicking,
                        self.teams,
                        self.referee,
                        self.stadium,
                    )
                )
        # else if phase is finished handle the end of phase conditions
        elif (
            self.curr_minute
            > self.curr_phase.duration_minutes + self.get_added_time_minutes()
        ):
            if self.curr_phase == Match.Phase.FIRST_HALF:
                # First half finished, continue to second half
                self.curr_minute = 1
                self.curr_phase = Match.Phase.SECOND_HALF
            elif self.curr_phase == Match.Phase.SECOND_HALF:
                if self.config.tie_breaker == "allow_tie":
                    # allow_time = Finish always at the end of second half (independent of the result)
                    self.finished = True
                else:
                    if is_tie:
                        self.curr_minute = 1
                        if self.config.tie_breaker == "on_tie_extra_time_and_penalties":
                            self.curr_phase = (
                                Match.Phase.FIRST_EXTRA_TIME
                            )  # Skip to extra time
                        elif self.config.tie_breaker == "on_tie_penalties":
                            self.curr_phase = Match.Phase.PENALTIES  # Skip to penalties
                    else:  # No tie to break at end of second half ==> finish game
                        self.finished = True
            elif self.curr_phase == Match.Phase.FIRST_EXTRA_TIME:
                self.curr_minute = 1
                self.curr_phase = Match.Phase.SECOND_EXTRA_TIME
            elif self.curr_phase == Match.Phase.SECOND_EXTRA_TIME:
                if is_tie:
                    self.curr_minute = 1
                    self.curr_phase = Match.Phase.PENALTIES
                else:
                    self.finished = True
        else:  # We are playing normally
            if self.curr_minute >= self.curr_phase.duration_minutes:
                # If we are in added time (recupero) increase the odds of action happening
                # There is more competitivity
                action_pr = self.config.added_time_action_probability
            elif self.curr_phase in [
                Match.Phase.FIRST_EXTRA_TIME,
                Match.Phase.SECOND_EXTRA_TIME,
            ]:
                # Same for added time
                action_pr = self.config.extra_time_action_probability
            else:
                action_pr = self.config.standard_action_probability

            do_action = np.random.random() < action_pr

            is_last_minute = (
                self.curr_minute
                == self.curr_phase.duration_minutes + self.get_added_time_minutes()
            )

            # In last minute an action happens always (suspence and drama goes brrr)
            if do_action or is_last_minute:
                await self.prefetch_blueprints()

                blueprint = await self.action_provider.get()

                if is_last_minute and not is_tie:
                    # Last minute action of every half is always given to the disadvantaged team

                    # At last minute of every time let the disadvantaged team try a last action
                    atk_team: Literal[0, 1] = [score_1, score_2].index(
                        min([score_1, score_2])
                    )  # type: ignore
                else:
                    # otherwise the two teams have the same odds to play as attackers
                    atk_team = 1 if np.random.random() <= 0.5 else 0

                if self.curr_minute <= self.curr_phase.duration_minutes:
                    # If we are not in additional time, then increase additional times depending on actions
                    if blueprint.action_type == "goal":
                        self.added_time[self.curr_phase] += np.random.uniform(
                            self.config.goal_added_time_min,
                            self.config.goal_added_time_max,
                        )
                    elif blueprint.action_type == "penalty":
                        self.added_time[self.curr_phase] += np.random.uniform(
                            self.config.penalty_added_time_min,
                            self.config.penalty_added_time_max,
                        )

                    if blueprint.use_var:
                        self.added_time[self.curr_phase] += np.random.uniform(
                            self.config.var_added_time_min,
                            self.config.var_added_time_max,
                        )

                self.actions.append(
                    Action.create_from_blueprint(
                        blueprint,
                        self.curr_phase,
                        self.curr_minute,
                        atk_team,
                        self.teams,
                        self.referee,
                        self.stadium,
                    )
                )

    async def prefetch_blueprints(self, n=1):
        for i in range(n):
            choices: list[ActionType] = ["goal", "no_goal", "penalty", "own_goal"]

            probabilities = [
                self.config.default_action_goal_probability,
                self.config.default_action_no_goal_probability,
                self.config.default_action_penalty_probability,
                self.config.default_action_own_goal_probability,
            ]

            (action_type,) = random.choices(choices, probabilities, k=1)

            var = np.random.random() < self.config.default_action_var_probability

            # Send the request to the provider that will fetch the blueprints used in get
            await self.action_provider.request(ActionRequest(action_type, var))

    def kick_penalty(self, penalty: Penalty):
        if not self.is_penalty_pending():
            raise RuntimeError("There is no penalty to kick")

        curr_action = self.get_current_action()

        assert curr_action is not None

        curr_action.kick_penalty(penalty)

    def is_match_finished(self):
        return self.finished
