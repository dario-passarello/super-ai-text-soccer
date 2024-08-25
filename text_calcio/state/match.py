from __future__ import annotations

import random
from typing import Any, Literal, Optional, cast

import attr
import cattrs
import numpy as np

from text_calcio.loaders.action import ActionBlueprint, ActionRequest, AsyncActionLoader
from text_calcio.loaders.serialization import Serializable
from text_calcio.state.match_time import MatchTime
from text_calcio.state.penalty import Penalty
from text_calcio.state.stadium import Stadium
from text_calcio.state.team import Team
from text_calcio.state.match_action import MatchAction, ActionType
from text_calcio.state.match_config import MatchConfig
from text_calcio.state.match_phase import MatchPhase

from frozendict import frozendict

# TODO: consider renaming "Added time" to "Stoppage time"/"Additional time" https://en.wikipedia.org/wiki/Association_football#Duration_and_tie-breaking_methods


@attr.s(frozen=True)
class Match(Serializable):
    """
    Match is an immutable class that represent the state of the match
    at a given game_clock time.

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

    home_team: Team = attr.ib()
    away_team: Team = attr.ib()
    game_clock: MatchTime = attr.ib()
    stadium: Stadium = attr.ib()
    referee: str = attr.ib()
    actions: tuple[MatchAction, ...] = attr.ib(default=attr.Factory(tuple))
    stoppage_times: frozendict[MatchPhase, float] = attr.ib(
        factory=lambda: frozendict({p: 0.0 for p in list(MatchPhase)})
    )
    finished: bool = attr.ib(default=False)
    config: MatchConfig = attr.ib(factory=MatchConfig)

    @classmethod
    def initialize_new_match(
        cls,
        home_team: Team,
        away_team: Team,
        stadium: Stadium,
        referee: str,
        config: Optional[MatchConfig] = None,
    ):
        return Match(
            home_team,
            away_team,
            MatchTime(),
            stadium,
            referee,
            config=config or MatchConfig(),
        )

    def get_stoppage_time_minutes(self, phase: Optional[MatchPhase] = None) -> int:
        """
        Returns the stoppage time minutes for the current phase or for a specific phase.
        The stoppage time is the time added for recovering lost minutes during the game for
        events like goals, penalties and VAR reviews rounded to the nearest integer.

        Parameters
        ---
        phase : MatchPhase or None
            The phase of which you want to get the current stoppage time. If left None
            it returns the added times of the current phase.

        Returns
        ---
        result : int
            The stoppage time minutes of the desired phase
        """
        return int(round(self.stoppage_times[phase or self.game_clock.phase]))

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
        latest_action = (
            self.get_action_from_game_clock() if hide_latest_result else None
        )

        for action in self.actions:
            if action.is_goal() and action is not latest_action:
                score[action.team_atk_id] += 1

        return cast(tuple[int, int], tuple(score))

    def get_teams(self):
        """
        Returns the home and away teams.

        Returns
        ---
        result : tuple[Team, Team]
            A tuple containing the home team and the away team.
        """
        return self.home_team, self.away_team

    def get_action_from_game_clock(
        self, game_clock: Optional[MatchTime] = None
    ) -> Optional[MatchAction]:
        """
        Gets the action happening at the current minute and current phase (curr_minute, curr_phase), or
        at a specified time

        Parameters
        ---
        game_clock : MatchTime or None
            The match time when the requested action happened. If not specified the current match time is
            used.

        Returns
        ---
        result : Action or None
            Returns the current action, or None if no action is happening at the specified MatchTime
        """

        time = game_clock or self.game_clock

        for action in self.actions:
            if action.time == time:
                return action

        return None

    def get_actions_up_to_minute(
        self, game_clock: Optional[MatchTime] = None
    ) -> list[MatchAction]:
        actions = []

        time = game_clock or self.game_clock

        for action in self.actions:
            if action.time <= time:
                actions.append(action)

        return actions

    def is_penalty_pending(self) -> bool:
        """
        Checks if a penalty has to be kicked at the current state before continuing with the next() method.
        If the result of this functio    def from_dict(self)n is True a penalty must be kicked before continuing.

        Returns
        ---
        result : bool
            Returns True if a penalty kick is pending, False otherwise

        See also
        ---
        kick_penalty : method to call if this check returns True
        next : method to call if this check returns False
        """
        curr_action = self.get_action_from_game_clock()

        return curr_action is not None and curr_action.is_penalty_pending()

    async def generate_action_and_advance(
        self, action_loader: AsyncActionLoader
    ) -> Match:
        if self.is_penalty_pending():
            raise RuntimeError("Penalty pending, could not advance to next action")

        next_state = attr.evolve(self, game_clock=self.game_clock.add_minutes(1))
        stoppage_time = next_state.get_stoppage_time_minutes()

        if next_state.game_clock.phase == MatchPhase.PENALTIES:
            return await next_state.handle_penalties()
        elif next_state.game_clock.is_phase_time_expired(stoppage_time):
            return next_state.handle_phase_transition()
        else:
            new_action = await next_state.generate_action(action_loader)

            if new_action:
                new_stoppage_time = self.update_stoppage_time(new_action)

                return attr.evolve(
                    next_state.perform_action(new_action),
                    stoppage_times=new_stoppage_time,
                )
            else:
                return next_state

    async def advance_from_action_list(
        self, actions: tuple[MatchAction, ...], stoppage_time: dict[MatchPhase, float]
    ):
        if self.is_penalty_pending():
            raise RuntimeError("Penalty pending, could not advance to next action")

        next_state = attr.evolve(
            self,
            game_clock=self.game_clock.add_minutes(1),
            actions=actions,
            stoppage_times=stoppage_time,
        )
        curr_stoppage_time = next_state.get_stoppage_time_minutes()
        if next_state.game_clock.phase == MatchPhase.PENALTIES:
            return await next_state.handle_penalties()
        elif next_state.game_clock.is_phase_time_expired(curr_stoppage_time):
            return next_state.handle_phase_transition()
        else:
            curr_action = next_state.get_action_from_game_clock()
            if curr_action is not None:
                return next_state.perform_action(curr_action)
            else:
                return next_state

    async def handle_penalties(self):
        score_1, score_2 = self.get_score()

        # TODO This may not work in case of sudden death (tie after 5 penalties)
        # penalties shootout has completely different rules
        # Calculate who kicks now
        penalty_kick_count = (self.game_clock.minute - 1) // 2
        penalties_remaining = max(
            self.config.penalties_shoot_count - penalty_kick_count, 1
        )

        curr_team_kicking = cast(Literal[0, 1], (self.game_clock.minute + 1) % 2)

        # Calculate penalty win condition
        score_curr_team = score_1 if curr_team_kicking == 0 else score_2
        score_other_team = score_2 if curr_team_kicking == 0 else score_1

        if score_curr_team + penalties_remaining < score_other_team:
            # If it is impossible to win
            return attr.evolve(self, finished=True)
        else:
            penalty_blueprint = ActionBlueprint("penalty", False, [], {}, None, None)
            new_action = MatchAction.create_from_blueprint(
                penalty_blueprint,
                self.game_clock,
                curr_team_kicking,
                (self.home_team, self.away_team),
                self.referee,
                self.stadium,
            )
            return attr.evolve(self, actions=self.actions + (new_action,))

    def generate_action_request(self):
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
        return ActionRequest(action_type, var)

    def kick_penalty(self, penalty: Penalty):
        if not self.is_penalty_pending():
            raise RuntimeError("There is no penalty to kick")

        curr_action = self.get_action_from_game_clock()

        assert curr_action is not None
        new_action = curr_action.kick_penalty(penalty)
        action_list = list(self.actions)
        action_list[action_list.index(curr_action)] = new_action
        return attr.evolve(self, actions=tuple(action_list))

    def is_match_finished(self) -> bool:
        return self.finished

    def is_current_phase_finished(self) -> bool:
        return (
            self.game_clock.minute
            > self.game_clock.phase.duration_minutes + self.get_stoppage_time_minutes()
        )

    def handle_phase_transition(self):
        match self.game_clock.phase:
            case MatchPhase.FIRST_HALF:
                return attr.evolve(self, game_clock=self.game_clock.next_phase())
            case MatchPhase.SECOND_HALF:
                return self.handle_second_half_end()
            case MatchPhase.FIRST_EXTRA_TIME:
                return attr.evolve(self, game_clock=self.game_clock.next_phase())
            case MatchPhase.SECOND_EXTRA_TIME:
                return self.handle_extra_time_end()
            case MatchPhase.PENALTIES:
                raise ValueError("Cannot Transition phase after PENALTIES")
            case _:
                raise ValueError(
                    "This block should not be reached. Something went really wrong"
                )

    def handle_second_half_end(self):
        if self.config.tie_breaker == "allow_tie":
            return attr.evolve(self, finished=True)
        elif self.is_tie():
            if self.config.tie_breaker == "on_tie_extra_time_and_penalties":
                next_phase = MatchPhase.FIRST_EXTRA_TIME
            else:  # on_tie_penalties
                next_phase = MatchPhase.PENALTIES
            return attr.evolve(self, game_clock=MatchTime(next_phase, 1))
        else:
            return attr.evolve(self, finished=True)

    def handle_extra_time_end(self):
        if self.is_tie():
            return attr.evolve(self, game_clock=MatchTime(MatchPhase.PENALTIES, 1))
        else:
            return attr.evolve(self, finished=True)

    def determine_action_probability(self):
        if self.game_clock.minute >= self.game_clock.phase.duration_minutes:
            return self.config.added_time_action_probability
        elif self.game_clock.phase in [
            MatchPhase.FIRST_EXTRA_TIME,
            MatchPhase.SECOND_EXTRA_TIME,
        ]:
            return self.config.extra_time_action_probability
        else:
            return self.config.standard_action_probability

    def is_last_minute_of_current_phase(self) -> bool:
        return (
            self.game_clock.minute
            == self.game_clock.phase.duration_minutes + self.get_stoppage_time_minutes()
        )

    def should_perform_action(self, action_probability):
        return (
            np.random.random() < action_probability
            or self.is_last_minute_of_current_phase()
        )

    def determine_attacking_team(self) -> Literal[0, 1]:
        score_1, score_2 = self.get_score()

        if self.is_last_minute_of_current_phase() and not self.is_tie():
            # Allow the team that is losing to try to score a goal in the last minute
            return 0 if score_1 < score_2 else 1
        else:
            return random.choice([0, 1])

    def update_stoppage_time(self, action: MatchAction):
        if action.time.minute <= action.time.phase.duration_minutes:
            stoppage_time_change = 0.0
            if action.type == "goal":
                stoppage_time_change += np.random.uniform(
                    self.config.goal_added_time_min,
                    self.config.goal_added_time_max,
                )
            elif action.type == "penalty":
                stoppage_time_change += np.random.uniform(
                    self.config.penalty_added_time_min,
                    self.config.penalty_added_time_max,
                )
            if action.type:
                stoppage_time_change += np.random.uniform(
                    self.config.var_added_time_min,
                    self.config.var_added_time_max,
                )
            new_stoppage_time = (
                self.stoppage_times[self.game_clock.phase] + stoppage_time_change
            )

            return frozendict(
                {**self.stoppage_times, self.game_clock.phase: new_stoppage_time}
            )
        else:
            return self.stoppage_times

    async def generate_action(self, action_loader: AsyncActionLoader):
        action_probability = self.determine_action_probability()

        if self.should_perform_action(action_probability):
            atk_team = self.determine_attacking_team()

            request = self.generate_action_request()
            blueprint = await action_loader.generate(request)

            new_action = MatchAction.create_from_blueprint(
                blueprint,
                self.game_clock,
                atk_team,
                (self.home_team, self.away_team),
                self.referee,
                self.stadium,
            )

            return new_action

        else:
            return None

    def perform_action(self, new_action: MatchAction):
        return attr.evolve(
            self,
            actions=self.actions + (new_action,),
        )

    def is_tie(self):
        score_1, score_2 = self.get_score()

        return score_1 == score_2

    def serialize(self) -> dict[str, Any]:
        return cattrs.unstructure(self)

    @classmethod
    def deserialize(cls, data: dict[str, Any]):
        return cattrs.structure(data, cls)


def custom_unstructure(instance):
    # Use attr.asdict but exclude the 'secret' field
    return attr.asdict(
        instance, filter=lambda attr, value: attr.name != "action_provider"
    )


cattrs.register_unstructure_hook(Match, custom_unstructure)
