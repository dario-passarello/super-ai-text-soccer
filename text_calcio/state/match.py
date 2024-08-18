from __future__ import annotations

import asyncio
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


ActionType = Literal["goal", "no_goal", "penalty", "own_goal"]


@dataclass
class Action:
    """
    An Action object represents a single goal attempt from one of the two teams
    playing the match. The Action is generating started by an ActionBlueprint
    that contains the template narration and the details about who eventually
    scored and who gave the assist, other than the evaluation of all player
    during that action. An action may end in a penalty, in this case more details
    about the penalty are stored in the penalty_info field.
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
            raise RuntimeError("Penalty not pending")
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

    def get_atk_players_assigments(self):
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

        # atk_player_order = atk_team.random_order(no_goalie=True)
        # def_player_order = def_team.random_order(no_goalie=True)

        player_assignments = {
            **{f"atk_{i}": atk_team.players[i] for i in range(1, len(atk_team))},
            "atk_goalie": atk_team.get_goalkeeper(),
            **{f"def_{i}": def_team.players[i] for i in range(1, len(def_team))},
            "def_goalie": def_team.get_goalkeeper(),
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


class Match:
    """
    Represents the state of a simulated footbal match.

    The match is divided in phases (first half, second half, additional times, penalties),
    each phase is divided in minutes. At every minute an Action may happen. An Action contains
    a human readable narration of what happened, which team attacks and which defends,
    the roles of the players and the outcome of the action (goal, no goal, own goal or penalty)

    Calling the next() method of this class, advances the game clock and triggers the generation of the actions
    that can be prefetched for perfomrance reasons.
    At first the method extracts a random outcome of the action and then it requests the action_provider
    to construct an action object (the creation logic is abstracted, it may be generate from AI or it can
    be taken from a database). The action_provider returns a detailed ActionBlueprint that is used
    to construct the Action object tied to the Match and then added to tle list of actions.
    """

    @dataclass
    class Config:
        tie_breaker: Literal[
            "allow_tie", "on_tie_extra_time_and_penalties", "on_tie_penalties"
        ] = "on_tie_extra_time_and_penalties"
        start_from_penalties: bool = False
        goal_added_time_min: float = 0.75
        goal_added_time_max: float = 1.75
        penalty_added_time_min: float = 1
        penalty_added_time_max: float = 2.5
        var_added_time_min: float = 1
        var_added_time_max: float = 2.5

        standard_action_probability = 0.2
        extra_time_action_probability = 0.35
        added_time_action_probability = 0.5

        # Soft requirment: These for probabilities should sum to 1
        default_action_no_goal_probability = 0.65
        default_action_goal_probability = 0.2
        default_action_own_goal_probability = 0.05
        default_action_penalty_probability = 0.10

        default_action_var_probaility = 0.10

        penalties_shoot_count = 5

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
        config: Optional[Match.Config] = None,
    ):
        self.config = config or Match.Config()

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
        Returns the current added time minutes for the current phase or for a spefic phase

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
        if phase is None:
            return int(round(self.added_time[self.curr_phase]))
        else:
            return int(round(self.added_time[phase]))

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
        return curr_action is not None and curr_action.is_penalty_pending()

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
            curr_team_kicking = 0 if self.curr_minute % 2 == 1 else 1
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
                            self.curr_phase = Match.Phase.FIRST_EXTRA_TIME # Skip to extra time
                        elif self.config.tie_breaker == "on_tie_penalties":
                            self.curr_phase = Match.Phase.PENALTIES # Skip to penalties
                    else: # No tie to break at end of second half ==> finish game
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
        else: # We are playing normally
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
                if is_last_minute and not is_tie: # last minute action of every half is always given to the disadnvated team
                    # At last minute of every time let the disadvantage team try a last action
                    atk_team: Literal[0, 1] = [score_1, score_2].index(min([score_1, score_2]))  # type: ignore
                else: # otherwise the two teams have the same odds to play as attackers
                    atk_team = 1 if np.random.random() <= 0.5 else 0
                if (
                    self.curr_minute <= self.curr_phase.duration_minutes
                ):  # If we are not in additional time, then increase additional times depending on actions
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
            probs = [
                self.config.default_action_goal_probability,
                self.config.default_action_no_goal_probability,
                self.config.default_action_penalty_probability,
                self.config.default_action_own_goal_probability,
            ]
            (action_type,) = random.choices(choices, probs, k=1)
            var = np.random.random() < self.config.default_action_var_probaility
            # Send the request to the provider that will fetch the blueprints used in get
            await self.action_provider.request(ActionRequest(action_type, var))

    def kick_penalty(self, penalty: Penalty):
        if not self.is_penalty_pending():
            raise RuntimeError("Penalty not pending")
        curr_action = self.get_current_action()
        assert curr_action is not None
        curr_action.kick_penalty(penalty)

    def is_match_finished(self):
        return self.finished
