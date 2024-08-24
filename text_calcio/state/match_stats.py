from __future__ import annotations

from typing import Literal, Optional, cast

import attr

from text_calcio.state.match import MatchAction, Match
from text_calcio.state.match_phase import MatchPhase
from text_calcio.state.match_time import MatchTime
from text_calcio.state.team import Team


@attr.s(frozen=True, auto_attribs=True)
class MatchStats:
    home_team_stats: TeamStats
    away_team_stats: TeamStats

    @classmethod
    def create_from_match(cls, match: Match) -> MatchStats:
        return cls(
            TeamStats.create_from_match(match, team_id=0),
            TeamStats.create_from_match(match, team_id=1),
        )


@attr.s(frozen=True, auto_attribs=True)
class TeamStats:
    updated_at: MatchTime
    team: Team
    score: int
    n_attempts: int
    goals: list[GoalStats]
    ball_possession_percentage: float
    player_evaluation: dict[str, int]

    @staticmethod
    def create_from_match(match: Match, team_id: Literal[0, 1]) -> TeamStats:
        all_actions = match.get_actions_up_to_current_minute()
        team = match.get_teams()[team_id]

        n_attempts = sum(
            1
            for action in all_actions
            if action.team_atk_id == team_id
            and action.time.phase != MatchPhase.PENALTIES
        )

        score = match.get_score()[team_id]

        goals = [
            GoalStats.create_from_action(action)
            for action in all_actions
            if action.team_atk_id == team_id and action.is_goal()
        ]

        goals = cast(list[GoalStats], list(filter(lambda x: x is not None, goals)))

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
            updated_at=match.game_clock,
            team=team,
            score=score,
            n_attempts=n_attempts,
            goals=goals,
            ball_possession_percentage=ball_possession_percentage,
            player_evaluation=dict(player_evaluation),
        )


@attr.s(frozen=True, auto_attribs=True)
class GoalStats:
    author: str
    time: MatchTime
    assist: Optional[str]
    goal_type: Literal["goal", "own_goal", "penalty"]

    @staticmethod
    def create_from_action(action: MatchAction) -> Optional[GoalStats]:
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
            time=action.time,
            assist=assist_player,
            goal_type=action.type,
        )
