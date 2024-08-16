from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
import random
from typing import Literal, Optional

import numpy as np

from text_calcio.action import ActionBlueprint
from text_calcio.stadium import Stadium
from text_calcio.team import Team



PenaltyDirection = Literal['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low']
ALL_PENALTY_DIRECTIONS : list[PenaltyDirection] = ['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low']

@dataclass
class Penalty:
    player_kicking : str
    goal_keeper : str
    kick_direction : PenaltyDirection
    dive_direction : PenaltyDirection
    is_goal : bool

    @staticmethod
    def calculate_is_goal(kick_direction : PenaltyDirection, dive_direction : PenaltyDirection):
        x_kick, y_kick = kick_direction.split('_')
        x_dive, y_dive = dive_direction.split('_')
        if kick_direction == dive_direction:
            return False
        if x_kick != x_dive:
            return True
        else:
            return np.random.random() < 0.5
        
    @staticmethod
    def create_player_kicked_penalty(player_kicking : str, goal_keeper: str, kick_direction : PenaltyDirection, dive_direction : PenaltyDirection):
        is_goal = Penalty.calculate_is_goal(kick_direction, dive_direction)

        return Penalty(
            player_kicking,
            goal_keeper,
            kick_direction,
            dive_direction,
            is_goal
        )

    @staticmethod
    def create_auto_penalty(player_kicking : str, goal_keeper: str):
        kick_direction : PenaltyDirection = random.choice(['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low'])
        dive_direction : PenaltyDirection = random.choice(['left_top', 'left_low', 'center_top', 'center_low', 'right_top', 'right_low'])
        is_goal = Penalty.calculate_is_goal(kick_direction, dive_direction)

        return Penalty(
            player_kicking,
            goal_keeper,
            kick_direction,
            dive_direction,
            is_goal
        )


@dataclass
class Action:
    team_atk_id: Literal[0, 1]
    phase: MatchState.Phase
    minute: int
    type : Literal["goal", "no_goal", "penalty", "own_goal"]
    goal_player: Optional[str]
    assist_player: Optional[str]
    players_evaluation: dict[str, int]
    sentences: list[str]
    player_assigments : dict[str, str]
    support_assigments : dict[str, str]
    penalty_info : Optional[Penalty] = None

    def __post_init__(self):
        if self.type == 'penalty':
            self.assist_player = None
            if self.penalty_info is None:
                self.goal_player = None
            else:
                self.goal_player = self.penalty_info.player_kicking
        elif self.type == 'own_goal':
            self.assist_player = None


    def is_goal(self) -> bool:
        return self.goal_player is not None and 'atk_' in self.goal_player
    
    def is_own_goal(self) -> bool:
        return self.goal_player is not None and 'def_' in self.goal_player
    
    def is_penalty_pending(self) -> bool:
        return self.type == 'penalty' and self.penalty_info is None
    
    def kick_penalty(self, penalty : Penalty):
        if not self.is_penalty_pending():
            raise RuntimeError('Penalty not pending')       
        self.penalty_info = penalty
        self.assist_player = None

        if penalty.is_goal:
            self.goal_player = penalty.player_kicking
        else:
            self.goal_player = None
    

    def get_all_assigments(self):
        return {
            **self.player_assigments,
            **self.support_assigments
        }

    def get_atk_players_assigments(self):
        return {
            placeholder : name for placeholder, name in self.player_assigments.items()
            if 'atk_' in placeholder
        }

    @staticmethod
    def create(
        action_response : ActionBlueprint,
        phase: MatchState.Phase,
        minute: int,
        atk_team_id : Literal[0, 1],
        teams : tuple[Team, Team],
        referee : str,
        stadium : Stadium
    ):

        atk_team = teams[atk_team_id]
        def_team = teams[1 - atk_team_id]

        # atk_player_order = atk_team.random_order(no_goalie=True)
        # def_player_order = def_team.random_order(no_goalie=True)

        player_assignments = {
            **{f'atk_{i}' : atk_team.players[i] for i in range(1, len(atk_team))},
            "atk_goalie": atk_team.get_goalkeeper(),
            **{f'def_{i}' : def_team.players[i] for i in range(1, len(def_team))},
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
            support_assigments
        )

@dataclass
class MatchConfig:
    tie_breaking : Literal['allow_tie', 'extra_time_and_penalties', 'only_penalties', 'golden_goal', 'silver_goal'] = 'allow_tie'



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
        config : MatchConfig
    ):
        self.teams = (team_1, team_2)
        self.curr_phase: MatchState.Phase = MatchState.Phase.FIRST_HALF
        self.curr_minute: int = 1
        self.phrases: dict[str, list[list[list[str]]]] = phrases
        self.stadium = stadium
        self.referee = referee
        self.actions: list[Action] = []
        self.config = config
        self.blueprint_queue = asyncio.Queue()
        self.demand_queue = asyncio.Queue()
        self.action_configs = []

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
    
    def get_no_spoiler_score(self) -> tuple[int, int]:
        score = [0, 0]
        curr_action = self.get_current_action()
        for action in self.actions:
            if action.is_goal() and action is not curr_action:
                score[action.team_atk_id] += 1
        return tuple(score)  # type: ignore

    def get_last_action(self) -> Optional[Action]:
        if len(self.actions) == 0:
            return None
        return self.actions[-1]

    def get_current_action(self):
        for action in self.actions:
            if action.minute == self.curr_minute and action.phase == self.curr_phase:
                return action
        return None

    def get_other_actions(self) -> list[Action]:
        if len(self.actions) < 1:
            return []
        return self.actions[:-1]
    
    def is_penalty_pending(self) -> bool:
        curr_action = self.get_current_action()
        return curr_action is not None and curr_action.is_penalty_pending()
    
    async def next(self):
        if self.is_penalty_pending():
            raise RuntimeError('Penalty pending, could not advance to next action')
        self.curr_minute += 1
        if self.curr_minute > self.curr_phase.duration_minutes:
            if self.curr_phase == MatchState.Phase.FIRST_HALF:
                self.curr_minute = 0
                self.curr_phase = MatchState.Phase.SECOND_HALF
        else:
            do_action = np.random.random() < 0.20
            if do_action:
                await self.prefetch_blueprints()
                blueprint = await self.blueprint_queue.get()
                atk_team = 1 if np.random.random() <= 0.5 else 0
                self.actions.append(Action.create(blueprint, self.curr_phase, self.curr_minute, atk_team, self.teams, self.referee, self.stadium))
                self.blueprint_queue.task_done()

    async def prefetch_blueprints(self, n = 1):
        demands = []
        for i in range(n):
            action_type, = random.choices(['goal', 'no_goal', 'penalty', 'own_goal'], [20, 65, 10, 5], k=1)
            var = np.random.random() < 0.1
            demands.append((action_type, var))
        await self.demand_queue.put(demands)


    def kick_penalty(self, penalty : Penalty):
        if not self.is_penalty_pending():
            raise RuntimeError('Penalty not pending')        
        curr_action = self.get_current_action()
        assert curr_action is not None
        curr_action.kick_penalty(penalty)

    def is_match_finished(self):
        return (
            self.curr_minute > self.curr_phase.duration_minutes
            and self.curr_phase == MatchState.Phase.SECOND_HALF
        )
