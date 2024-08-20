from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from text_calcio.state.match import Action, Match
from text_calcio.state.team import Team


@dataclass
class MatchStats:
    team_1_stats: TeamStats
    team_2_stats: TeamStats

    @classmethod
    def create_from_match(cls, match: Match) -> MatchStats:
        return cls(
            TeamStats.create_from_match(match, team_id=0),
            TeamStats.create_from_match(match, team_id=1),
        )


@dataclass
class TeamStats:
    updated_at_phase: Match.Phase
    updated_at_minute: int
    team: Team
    score: int
    n_attempts: int
    goals: list[GoalStats]
    ball_possession_percentage: float
    player_evaluation: dict[str, int]

    @staticmethod
    def create_from_match(match: Match, team_id: Literal[0, 1]) -> TeamStats:
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
            if action.team_atk_id == team_id and action.is_goal()
        ]

        ball_possession_percentage = (
            (n_attempts / len(all_actions) * 100) if all_actions else 0
        )

        player_evaluation = {player: 0 for player in team.players}

        for action in all_actions:
            team_role = "atk" if action.team_atk_id == team_id else "def"

            for placeholder, score in action.players_evaluation.items():
                role = placeholder.strip("{}")
                player_name = action.player_assigments[role]

                if team_role in role:
                    player_evaluation[player_name] += score

        return TeamStats(
            updated_at_phase=match.curr_phase,
            updated_at_minute=match.curr_minute,
            team=team,
            score=score,
            n_attempts=n_attempts,
            goals=goals,
            ball_possession_percentage=ball_possession_percentage,
            player_evaluation=dict(player_evaluation),
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
        assist_player = (
            action.map_role_to_name(action.assist_player)
            if action.assist_player
            else None
        )

        return GoalStats(
            author=scorer_player,
            match_phase=action.phase,
            minute=action.minute,
            assist=assist_player,
            goal_type=action.type,
        )
