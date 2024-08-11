from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random
from typing import Literal, Mapping, Optional

import numpy as np
from termcolor import colored

from text_calcio.stadium import Stadium
from text_calcio.team import Team


@dataclass
class ActionPart:
    class Type(Enum):

        def __init__(self, name):
            self.ident: str = name

        INITIAL = "initial"
        CONTINUE = "continue"
        GOAL = "goal"
        NO_GOAL = "no_goal"

    action: Action
    event_type: Type
    phrases: list[str]
    assignments: Mapping[str, str]

    def is_final_part(self):
        return self.event_type in [ActionPart.Type.GOAL, ActionPart.Type.NO_GOAL]

    def get_curr_atk(self):
        return self.assignments["atk_curr"]

    def get_next_atk(self):
        return self.assignments["atk_next"]


class Action:

    def __init__(self, match: MatchState, team_atk_id: Literal[0, 1]):
        self.match = match
        self.team_atk_id = team_atk_id
        self.phase = match.curr_phase
        self.minute = match.curr_minute
        self.goal_player = None
        self.action_parts: list[ActionPart] = []

    def is_goal(self) -> bool:
        return self.goal_player is not None

    def is_concluded(self) -> bool:
        return len(self.action_parts) > 0 and self.action_parts[-1].is_final_part()

    def get_atk_def_teams(self) -> tuple[Team, Team]:
        atk_team = self.match.teams[self.team_atk_id]
        def_team_id = 1 - self.team_atk_id
        def_team = self.match.teams[def_team_id]
        return atk_team, def_team

    def get_curr_conclusion_probability(self):
        if len(self.action_parts) < 2:
            return 0.0
        else:
            return min(0.8, len(self.action_parts) / 15)

    def create_random_phrase(
        self, group: Literal["initial", "continue", "goal", "no_goal", "penalty"]
    ):
        chosen_sequence = random.choice(self.match.phrases[group])
        final_sequence: list[str] = []
        for alternatives in chosen_sequence:
            chosen_alternative = random.choice(alternatives)
            if len(chosen_alternative) > 0:
                final_sequence.append(chosen_alternative)
        return final_sequence

    def continue_action(self):

        assert (
            not self.is_concluded()
        ), "Action is concluded but continuation was requested"

        team_atk, team_def = self.get_atk_def_teams()

        if len(self.action_parts) == 0:
            phrase = self.create_random_phrase("initial")
            atk_player_order = team_atk.random_order(no_goalie=True)
            def_player_order = team_def.random_order(no_goalie=True)
            player_assignment = {
                "atk_curr": atk_player_order[0],
                "atk_next": atk_player_order[1],
                "atk_1": atk_player_order[2],
                "atk_2": atk_player_order[3],
                "atk_goalie": team_atk.get_goalkeeper(),
                "def_1": def_player_order[0],
                "def_2": def_player_order[1],
                "def_3": def_player_order[2],
                "def_4": def_player_order[3],
                "def_goalie": team_def.get_goalkeeper(),
                "referee": self.match.referee,
                "stadium": self.match.stadium.name,
                "stadium_prefix": self.match.stadium.prefix,
                "stadium_capacity": self.match.stadium.capacity
            }
            self.action_parts.append(
                ActionPart(self, ActionPart.Type.INITIAL, phrase, player_assignment)
            )
        else:
            conclude = np.random.random() < self.get_curr_conclusion_probability()
            goal = np.random.random() < 0.3

            if conclude:
                if goal:
                    phrase_type = "goal"
                    action_type = ActionPart.Type.GOAL
                else:
                    phrase_type = "no_goal"
                    action_type = ActionPart.Type.NO_GOAL
            else:
                phrase_type = "continue"
                action_type = ActionPart.Type.CONTINUE

            curr_atk = self.action_parts[-1].get_next_atk()
            phrase = self.create_random_phrase(phrase_type)
            atk_player_order = team_atk.random_order(
                no_goalie=True, exclude_also=[curr_atk]
            )
            def_player_order = team_def.random_order(no_goalie=True)
            player_assignment = {
                "atk_curr": curr_atk,
                "atk_next": atk_player_order[0],
                "atk_1": atk_player_order[1],
                "atk_2": atk_player_order[2],
                "atk_goalie": team_atk.get_goalkeeper(),
                "def_1": def_player_order[0],
                "def_2": def_player_order[1],
                "def_3": def_player_order[2],
                "def_4": def_player_order[3],
                "def_goalie": team_def.get_goalkeeper(),
                "referee": self.match.referee,
                "stadium": self.match.stadium.name,
                "stadium_prefix": self.match.stadium.prefix,
                "stadium_capacity": self.match.stadium.capacity
            }
            if conclude and goal:
                self.goal_player = player_assignment["atk_curr"]

            self.action_parts.append(
                ActionPart(self, action_type, phrase, player_assignment)
            )


class MatchState:
    class Phase(Enum):
        FIRST_HALF = 0, 45
        SECOND_HALF = 1, 45
        FIRST_ADD_TIME = 2, 15
        SECOND_ADD_TIME = 3, 15
        PENALTIES = 4, 0

        def __init__(self, id: int, duration_minutes: int) -> None:
            self.id = id
            self.duration_minutes = duration_minutes

    def __init__(
        self,
        team_1: Team,
        team_2: Team,
        phrases: dict[str, list[list[list[str]]]],
        stadium: Stadium,
        referee: str,
    ):
        self.teams = (team_1, team_2)
        self.curr_phase: MatchState.Phase = MatchState.Phase.FIRST_HALF
        self.curr_minute: int = 1
        self.phrases: dict[str, list[list[list[str]]]] = phrases
        self.stadium = stadium
        self.referee = referee
        self.actions: list[Action] = []
        self.observers = []

    def add_observer(self, observer):
        self.observers.append(observer)

    def remove_observer(self, observer):
        self.observers.remove(observer)

    def get_team_1(self):
        return self.teams[0]

    def get_team_2(self):
        return self.teams[1]

    def get_current_score(self) -> tuple[int, int]:
        score = [0, 0]
        for action in self.actions:
            if action.is_goal():
                score[action.team_atk_id] += 1
        return tuple(score)  # type: ignore

    def get_last_action(self) -> Optional[Action]:
        if len(self.actions) == 0:
            return None
        return self.actions[-1]

    def get_current_action(self):
        last_action = self.get_last_action()
        if (
            last_action is None
            or last_action.minute != self.curr_minute
            or last_action.phase != self.curr_phase
        ):
            return None
        return last_action

    def get_other_actions(self) -> list[Action]:
        if len(self.actions) < 1:
            return []

        return self.actions[:-1]

    def is_last_action_concluded(self):
        if len(self.actions) == 0:
            return True
        return self.actions[-1].is_concluded()

    def on_event(self, event: str):
        for obs in self.observers:
            obs.on_event(event, self)

    def next(self):
        if self.is_last_action_concluded():
            self.curr_minute += 1
            if self.curr_minute >= self.curr_phase.duration_minutes:
                if self.curr_phase == MatchState.Phase.FIRST_HALF:
                    self.curr_minute = 0
                    self.curr_phase = MatchState.Phase.SECOND_HALF
                else:
                    self.on_event("finish")

            else:
                do_action = np.random.random() < 0.3
                if do_action:
                    atk_team = 1 if np.random.random() <= 0.5 else 0
                    self.actions.append(Action(self, atk_team))
                    curr_action = self.actions[-1]
                    curr_action.continue_action()
                    self.on_event("update")

        else:
            curr_action = self.actions[-1]
            curr_action.continue_action()
            self.on_event("update")

    def is_match_finised(self):
        return (
            self.is_last_action_concluded()
            and self.curr_minute >= self.curr_phase.duration_minutes
            and self.curr_phase == MatchState.Phase.SECOND_HALF
        )
