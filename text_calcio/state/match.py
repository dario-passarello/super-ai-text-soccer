from __future__ import annotations

from collections import defaultdict
import random
from typing import Optional, cast

import numpy as np

from text_calcio.loaders.action import ActionBlueprint, ActionRequest
from text_calcio.loaders.action_provider import AsyncActionProvider
from text_calcio.state.penalty import Penalty
from text_calcio.state.stadium import Stadium
from text_calcio.state.team import Team
from text_calcio.state.match_action import MatchAction, ActionType
from text_calcio.state.match_config import MatchConfig
from text_calcio.state.match_phase import MatchPhase


# TODO: consider renaming "Added time" to "Stoppage time"/"Additional time" https://en.wikipedia.org/wiki/Association_football#Duration_and_tie-breaking_methods


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

    def __init__(
        self,
        home_team: Team,
        away_team: Team,
        stadium: Stadium,
        referee: str,
        action_provider: AsyncActionProvider,
        config: Optional[MatchConfig] = None,
    ):
        self.config = config or MatchConfig()

        self.teams = (home_team, away_team)
        self.home_team = home_team
        self.away_team = away_team

        # TODO: maybe less hardcoded/hacky way to test specific phases?
        if self.config.start_from_penalties:
            self.curr_phase: MatchPhase = MatchPhase.PENALTIES
        else:
            self.curr_phase: MatchPhase = MatchPhase.FIRST_HALF

        self.curr_minute: int = 1
        self.stadium = stadium
        self.referee = referee
        self.actions: list[MatchAction] = []
        self.action_provider = action_provider
        self.action_configs = []
        self.added_time: dict[MatchPhase, float] = defaultdict(float)
        self.finished = False

    def get_added_time_minutes(self, phase: Optional[MatchPhase] = None) -> int:
        """
        Returns the added time minutes for the current phase or for a specific phase

        Parameters
        ---
        phase : MatchPhase or None
            The phase of which you want to get the current added time. If left None
            it returns the added times of the current phase.

        Returns
        ---
        result : int
            The added time minutes of the desired phase
        """
        return int(round(self.added_time[phase or self.curr_phase]))

    def get_score(self, hide_latest_result: bool = False) -> tuple[int, int]:
        """
        Returns the current match score.

        Parameters
        ---
        hide_latest_result : bool, optional
            If True, excludes the latest action from the score calculation.
            Default is False.

        Returns
        ---
        tuple[int, int]: Goals scored by (home_team, away_team).
        """
        score = [0, 0]
        latest_action = self.get_current_action() if hide_latest_result else None

        for action in self.actions:
            if action.is_goal() and action is not latest_action:
                score[action.team_atk_id] += 1

        return cast(tuple[int, int], tuple(score))

    def get_current_action(self) -> Optional[MatchAction]:
        """
        Gets the action happening at the current minute and current phase (curr_minute, curr_phase), if present

        Returns
        ---
        result : Action or None
            Returns the current action, or None if no action is happening at the current minute and phase
        """
        for action in self.actions:
            if action.minute == self.curr_minute and action.phase == self.curr_phase:
                return action

        return None

    def get_actions_up_to_current_minute(self) -> list[MatchAction]:
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

        if self.curr_phase == MatchPhase.PENALTIES:
            await self.handle_penalties()
        elif self.is_current_phase_finished():
            self.handle_phase_transition()
        else:
            await self.perform_action()

    async def handle_penalties(self):
        score_1, score_2 = self.get_score()

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
            penalty_blueprint = ActionBlueprint("penalty", False, [], {}, None, None)

            self.actions.append(
                MatchAction.create_from_blueprint(
                    penalty_blueprint,
                    self.curr_phase,
                    self.curr_minute,
                    curr_team_kicking,
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

    def is_current_phase_finished(self) -> bool:
        return (
            self.curr_minute
            > self.curr_phase.duration_minutes + self.get_added_time_minutes()
        )

    def handle_phase_transition(self):
        match self.curr_phase:
            case MatchPhase.FIRST_HALF:
                self.curr_minute = 1
                self.curr_phase = MatchPhase.SECOND_HALF
            case MatchPhase.SECOND_HALF:
                self.handle_second_half_end()
            case MatchPhase.FIRST_EXTRA_TIME:
                self.curr_minute = 1
                self.curr_phase = MatchPhase.SECOND_EXTRA_TIME
            case MatchPhase.SECOND_EXTRA_TIME:
                self.handle_extra_time_end()

    def handle_second_half_end(self):
        if self.config.tie_breaker == "allow_tie":
            self.finished = True
        elif self.is_tie():
            self.curr_minute = 1
            if self.config.tie_breaker == "on_tie_extra_time_and_penalties":
                self.curr_phase = MatchPhase.FIRST_EXTRA_TIME
            elif self.config.tie_breaker == "on_tie_penalties":
                self.curr_phase = MatchPhase.PENALTIES
        else:
            self.finished = True

    def handle_extra_time_end(self):
        if self.is_tie():
            self.curr_minute = 1
            self.curr_phase = MatchPhase.PENALTIES
        else:
            self.finished = True

    def determine_action_probability(self):
        if self.curr_minute >= self.curr_phase.duration_minutes:
            return self.config.added_time_action_probability
        elif self.curr_phase in [
            MatchPhase.FIRST_EXTRA_TIME,
            MatchPhase.SECOND_EXTRA_TIME,
        ]:
            return self.config.extra_time_action_probability
        else:
            return self.config.standard_action_probability

    def is_last_minute_of_current_phase(self) -> bool:
        return (
            self.curr_minute
            == self.curr_phase.duration_minutes + self.get_added_time_minutes()
        )

    def should_perform_action(self, action_probability):
        return (
            np.random.random() < action_probability
            or self.is_last_minute_of_current_phase()
        )

    def determine_attacking_team(self):
        score_1, score_2 = self.get_score()

        if self.is_last_minute_of_current_phase() and not self.is_tie():
            # Allow the team that is losing to try to score a goal in the last minute
            return 0 if score_1 < score_2 else 1
        else:
            return random.choice([0, 1])

    def update_added_time(self, blueprint):
        if self.curr_minute <= self.curr_phase.duration_minutes:
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

    async def perform_action(self):
        action_probability = self.determine_action_probability()

        if self.should_perform_action(action_probability):
            await self.prefetch_blueprints()
            blueprint = await self.action_provider.get()

            atk_team = self.determine_attacking_team()

            self.update_added_time(blueprint)

            self.actions.append(
                MatchAction.create_from_blueprint(
                    blueprint,
                    self.curr_phase,
                    self.curr_minute,
                    atk_team,
                    self.teams,
                    self.referee,
                    self.stadium,
                )
            )

    def is_tie(self):
        score_1, score_2 = self.get_score()

        return score_1 == score_2
