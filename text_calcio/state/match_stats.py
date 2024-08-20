from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal, Optional

from text_calcio.state.match import Action, Match
from text_calcio.state.team import Team


@dataclass
class MatchStats:
    team_1_stats: TeamStats
    team_2_stats: TeamStats

    @staticmethod
    def create_from_match(match: Match):
        return MatchStats(
            TeamStats.create_from_match(match, 0),
            TeamStats.create_from_match(match, 1),
        )


@dataclass
class TeamStats:
    updated_at_phase: Match.Phase
    updated_at_minute: int
    team: Team
    score: int
    n_attempts: int
    goals: list[GoalStats]
    ball_possesion_pct: float
    player_evaluation: dict[str, int]

    @staticmethod
    def create_from_match(match: Match, team_id: Literal[0, 1]):
        all_actions = match.get_all_actions_to_now()
        team = match.teams[team_id]
        n_attempts = sum(
            1
            for action in all_actions
            if action.team_atk_id == team_id and action.phase != Match.Phase.PENALTIES
        )
        score = match.get_current_score()[team_id]
        goals = [
            GoalStats.create_from_action(action)
            for action in all_actions
            if action.team_atk_id == team_id
        ]
        goals = [goal for goal in goals if goal is not None]
        if len(all_actions) == 0:
            ball_possesion_pct = 0
        else:
            ball_possesion_pct = n_attempts / len(all_actions) * 100
        all_evaluations = defaultdict(int)
        for pl in team.players:
            all_evaluations[pl] = 0
        for action in all_actions:
            team_role = "atk" if action.team_atk_id == team_id else "def"
            for placeholder, score in action.players_evaluation.items():
                role = placeholder.strip("{}")
                player_name = action.player_assigments[role]
                if team_role in role:
                    all_evaluations[player_name] += score
        return TeamStats(
            match.curr_phase,
            match.curr_minute,
            team,
            score,
            n_attempts,
            goals,
            ball_possesion_pct,
            all_evaluations,
        )


@dataclass
class GoalStats:
    author: str
    match_phase: Match.Phase
    minute: int
    assist: Optional[str]
    goal_type: Literal["goal", "own_goal", "penalty"]

    @staticmethod
    def create_from_action(action: Action) -> Optional[GoalStats]:
        if not action.is_goal():
            return None

        assert action.goal_player is not None and action.type != "no_goal"

        scorer_player = action.map_role_to_name(action.goal_player)
        if action.assist_player is None:
            assist_player = None
        else:
            assist_player = action.map_role_to_name(action.assist_player)

        return GoalStats(
            scorer_player, action.phase, action.minute, assist_player, action.type
        )
