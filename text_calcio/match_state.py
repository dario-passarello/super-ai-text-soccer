from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random
from typing import Literal, Optional

import numpy as np

from text_calcio.ai import ActionGenerator, find_invalid_keys
from text_calcio.stadium import Stadium
from text_calcio.team import Team


@dataclass
class Action:
    team_atk_id: Literal[0, 1]
    phase: MatchState.Phase
    minute: int
    type : Literal["goal", "no_goal", "penalty"]
    goal_player: Optional[str]
    assist_player: Optional[str]
    action_mvp: Optional[str]
    action_lvp: Optional[str]
    sentences: list[str]
    player_assigments : dict[str, str]
    support_assigments : dict[str, str]

    def __post_init__(self):
        self.validate()

    def is_goal(self) -> bool:
        return self.goal_player is not None
    
    def validate(self) -> None:
        if self.type == "goal" and self.goal_player is None:
            raise ValueError('Action is type goal but no goal_player specified')
        for i, sentence in enumerate(self.sentences):
            inv_keys = find_invalid_keys(sentence, set(self.get_all_assigments().keys()))
            if len(inv_keys) > 0:
                raise ValueError(f'In sentence {i} invalid keys were found: {', '.join(inv_keys)}. Sentence: {sentence}')
        
        valid_player_placeholders = ['{' + role + '}' for role in self.player_assigments.keys()]

        if self.goal_player is not None and not self.goal_player in valid_player_placeholders:
            raise ValueError(f"Invalid goal_player placeholder: {self.goal_player}")
        if self.assist_player is not None and self.assist_player not in valid_player_placeholders:
            raise ValueError(f"Invalid assist_player placeholder: {self.assist_player}")
        if self.action_mvp is not None and self.action_mvp not in valid_player_placeholders:
            raise ValueError(f"Invalid action_mvp placeholder: {self.action_mvp}")
        if self.action_lvp is not None and self.action_lvp not in valid_player_placeholders:
            raise ValueError(f"Invalid action_lvp placeholder: {self.action_lvp}")
                                    


    def get_all_assigments(self):
        return {
            **self.player_assigments,
            **self.support_assigments
        }

    @staticmethod
    def create(
        match: MatchState,
        atk_team_id: Literal[0, 1],
        action_type: Literal["goal", "no_goal", "penalty"],
        is_var: bool,
    ):

        atk_team = match.teams[atk_team_id]
        def_team = match.teams[1 - atk_team_id]

        # atk_player_order = atk_team.random_order(no_goalie=True)
        # def_player_order = def_team.random_order(no_goalie=True)

        player_assignments = {
            **{f'atk_{i}' : atk_team.players[i] for i in range(1, len(atk_team))},
            "atk_goalie": atk_team.get_goalkeeper(),
            **{f'def_{i}' : def_team.players[i] for i in range(1, len(def_team))},
            "def_goalie": def_team.get_goalkeeper(),
        }

        support_assigments = {
            "referee": match.referee,
            "stadium": match.stadium.name,
            "atk_team_name": atk_team.familiar_name,
            "def_team_name": def_team.familiar_name,
        }

        action_response = match.action_generator.generate(action_type, is_var)

        goal_player = action_response.scorer_player
        assist_player = action_response.assist_player
        mvp = action_response.best_player
        lvp = action_response.worst_player

        return Action(
            atk_team_id,
            match.curr_phase,
            match.curr_minute,
            action_type,
            goal_player,
            assist_player,
            mvp,
            lvp,
            action_response.phrases,
            player_assignments,
            support_assigments
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
        action_generator: ActionGenerator,
    ):
        self.teams = (team_1, team_2)
        self.curr_phase: MatchState.Phase = MatchState.Phase.FIRST_HALF
        self.curr_minute: int = 1
        self.phrases: dict[str, list[list[list[str]]]] = phrases
        self.stadium = stadium
        self.referee = referee
        self.actions: list[Action] = []
        self.action_generator = action_generator

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

    def next(self):
        self.curr_minute += 1
        if self.curr_minute > self.curr_phase.duration_minutes:
            if self.curr_phase == MatchState.Phase.FIRST_HALF:
                self.curr_minute = 0
                self.curr_phase = MatchState.Phase.SECOND_HALF
        else:
            do_action = np.random.random() < 0.20
            if do_action:
                atk_team = 1 if np.random.random() <= 0.5 else 0
                result, = random.choices(['goal', 'no_goal'], [20, 80], k=1)
                assert result == 'goal' or result == 'no_goal'
                var = np.random.random() < 0.1
                self.actions.append(Action.create(self, atk_team, result, var))

    def is_match_finised(self):
        return (
            self.curr_minute > self.curr_phase.duration_minutes
            and self.curr_phase == MatchState.Phase.SECOND_HALF
        )
