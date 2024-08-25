from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from operator import itemgetter
from typing import AsyncGenerator, Awaitable, Callable, Literal, Mapping, Optional
from aioconsole import aprint
import numpy as np
from termcolor import colored

from text_calcio.state.match import MatchAction, Match
from text_calcio.state.match_stats import GoalStats, MatchStats
from text_calcio.state.match_phase import MatchPhase
from text_calcio.state.match_time import MatchTime
from text_calcio.state.penalty import ALL_PENALTY_DIRECTIONS, PenaltyDirection
from text_calcio.state.team import Team

from text_calcio.cli.i18n import _

import tabulate

CLEAR_CHAR = "\033c"

KICK_OR_DIVE_SELECTION_TEXT_ART = """
._____________.
|(1)  (3)  (5)|
|             |    ???
|             |  (0) ???
|(2)  (4)  (6)|    ???
"""


@dataclass
class PenaltyInteractionResult:
    player_kicking: str
    kick_direction: PenaltyDirection
    player_saving: str
    save_direction: PenaltyDirection


class CLIDisplay:
    @dataclass
    class Config:
        pass

    def __init__(
        self, match: Match, config: Optional[CLIDisplay.Config] = None
    ) -> None:
        self.config = config or CLIDisplay.Config()
        self.match = match
        self.phrase_counter = 0

    def format_minute(self):
        curr_time = self.match.game_clock

        additional_time = curr_time.minute - curr_time.phase.duration_minutes

        base_minute = min(curr_time.phase.duration_minutes, curr_time.minute)

        phase_indicator = ""

        match curr_time.phase:
            case MatchPhase.FIRST_HALF:
                phase_indicator = _("1st")
                base_minute += 0
            case MatchPhase.SECOND_HALF:
                phase_indicator = _("2nd")
                base_minute += 45
            case MatchPhase.FIRST_EXTRA_TIME:
                phase_indicator = _("1st ET")
                base_minute += 90
            case MatchPhase.SECOND_EXTRA_TIME:
                phase_indicator = _("2nd ET")
                base_minute += 105
            case MatchPhase.PENALTIES:
                phase_indicator = _("Shootout")
                base_minute += 120

                return _("Kick") + f" {(curr_time.minute // 2)} {phase_indicator}"
            case _:
                raise ValueError("Invalid phase")

        final_str = f"{base_minute}:00"

        if additional_time > 0:
            final_str += (
                f" + {additional_time}:00  (+{self.match.get_stoppage_time_minutes()})"
            )

        final_str += f" {phase_indicator}"

        return final_str

    def format_score(self):
        t1 = self.match.home_team
        t2 = self.match.away_team

        # Avoid spoilers by not showing the latest result
        score_t1, score_t2 = self.match.get_score(hide_latest_result=True)

        return f"{t1.short_name} {score_t1} - {score_t2} {t2.short_name}"

    def render_header(self):
        t1 = self.match.home_team
        t2 = self.match.away_team

        t1_fmt = colored(t1.short_name, t1.color)  # type: ignore
        t2_fmt = colored(t2.short_name, t2.color)  # type: ignore

        # Avoid spoilers by not showing the latest result
        score_t1, score_t2 = self.match.get_score(hide_latest_result=True)

        display = tabulate.tabulate(
            [[t1_fmt, f"{score_t1} - {score_t2}", t2_fmt, self.format_minute()]],
            headers=[],
            tablefmt="rounded_grid",
        )

        return display

    def render_after_goal_view(self):
        t1 = self.match.home_team
        t2 = self.match.away_team

        t1_fmt = colored(t1.full_name, t1.color)  # type: ignore
        t2_fmt = colored(t2.full_name, t2.color)  # type: ignore

        stats = MatchStats.create_from_match(self.match)

        t1_goals = [format_goal_entry(goal) for goal in stats.home_team_stats.goals]
        t2_goals = [format_goal_entry(goal) for goal in stats.away_team_stats.goals]

        score_t1, score_t2 = self.match.get_score()

        headers = [t1_fmt, f"{score_t1} - {score_t2}", t2_fmt]

        data = [["\n".join(t1_goals), "", "\n".join(t2_goals)]]

        display = tabulate.tabulate(
            data,
            headers=headers,
            tablefmt="rounded_grid",
            colalign=["left", "center", "right"],
        )

        return display

    def render_evaluations(self, action: Optional[MatchAction] = None):
        stats = MatchStats.create_from_match(self.match)

        evaluations = sorted(
            [
                (player, evaluation, 0)
                for player, evaluation in stats.home_team_stats.player_evaluation.items()
            ]
            + [
                (player, evaluation, 1)
                for player, evaluation in stats.away_team_stats.player_evaluation.items()
            ],
            key=itemgetter(1),
            reverse=True,
        )

        if action is not None:
            delta_evals = action.players_evaluation
            # Replace role placeholder with names
            delta_evals = {
                action.map_role_to_name(role): delta_eval
                for role, delta_eval in delta_evals.items()
            }
            delta_evals = defaultdict(int, delta_evals)
            data = [
                (
                    colored(player, self.match.get_teams()[team_id].color),
                    evaluation,
                    delta_evals[player],
                )
                for player, evaluation, team_id in evaluations
            ]  # type: ignore

            headers = [_("Player"), _("Evaluation"), _("Change")]
            colalign = ["left", "right", "right"]
        else:
            headers = [_("Player"), _("Evaluation")]

            data = [
                (colored(player, self.match.get_teams()[team_id].color), evaluation)
                for player, evaluation, team_id in evaluations
            ]  # type: ignore

            colalign = ["left", "right"]

        display = tabulate.tabulate(
            data, headers=headers, tablefmt="rounded_grid", colalign=colalign
        )

        return display

    async def display_action_sequence(self) -> AsyncGenerator[None, None]:
        last_action = self.match.get_action_from_game_clock()

        if last_action is None:
            yield
            return

        home_team = self.match.home_team
        away_team = self.match.away_team

        team_atk = home_team if last_action.team_atk_id == 0 else away_team
        team_def = away_team if last_action.team_atk_id == 0 else home_team

        formatted_phrases: list[str] = []

        for i, phrase in enumerate(last_action.sentences):
            formatted_phrases.append(
                format_phrase(
                    phrase, team_atk, team_def, last_action.get_all_assigments()
                )
            )

        for i in range(len(formatted_phrases)):
            await clean_screen()
            await aprint(self.render_header(), end="\n" * 3)
            phrases_revelaed = formatted_phrases[: i + 1]
            reordered_phrases = phrases_revelaed[::-1][:5]
            if len(reordered_phrases) > 0:
                await aprint(colored(f"> {reordered_phrases[0]}"), end="\n\n")

                for phrase in reordered_phrases[1:]:
                    await aprint(phrase, end="\n\n")
            yield

    PenaltyInteractionMessage = (
        Literal["prompt_continue", "require_input"]
        | tuple[Literal["interaction_complete"], PenaltyInteractionResult]
    )

    async def penalty_interaction(
        self, controller: Callable[[bool], Awaitable[Optional[str]]]
    ) -> PenaltyInteractionResult:
        random_option = "0 - " + _("random")

        last_action = self.match.get_action_from_game_clock()
        if last_action is None:
            raise RuntimeError("No penalty found")
        assigments = last_action.get_all_assigments()
        home_team = self.match.home_team
        away_team = self.match.away_team

        team_atk = home_team if last_action.team_atk_id == 0 else away_team
        team_def = away_team if last_action.team_atk_id == 0 else home_team

        atk_assigments = list(last_action.get_atk_players_assignments().items())

        direction_names = [
            _("top left corner"),
            _("left on the ground"),
            _("center below crossbar"),
            _("center on the ground"),
            _("top right corner"),
            _("right on the ground"),
        ]

        position_text = "\n".join(
            [random_option]
            + [f"{i + 1} - {position}" for i, position in enumerate(direction_names)]
        )

        q0_remain = True
        role, kicker_name, kicker_placeholder = None, None, None

        await clean_screen()

        while q0_remain:
            await aprint(self.render_header(), end="\n\n")

            await aprint(
                format_phrase(
                    _(
                        "A penality was awarded to {atk_team_name}. Who is going to kick it?"
                    ),
                    team_atk,
                    team_def,
                    assigments,
                )
            )

            player_list = "\n".join(
                [random_option]
                + [f"{i + 1} - {name}" for i, (role, name) in enumerate(atk_assigments)]
            )

            await aprint(player_list)

            q0_choice = await controller(require_input=True)
            if q0_choice is None:
                raise TypeError("An user imput was expected, but None was found")
            try:
                q0_int = int(q0_choice)

                if not 0 <= q0_int <= len(team_atk.players):
                    raise ValueError(
                        _("Number must be between 0 and ") + str(len(team_atk.players))
                    )
                if q0_int == 0:
                    kicker_idx = np.random.randint(0, len(team_atk.players) - 1)
                else:
                    kicker_idx = q0_int - 1

                role, kicker_name = atk_assigments[kicker_idx]
                kicker_placeholder = "{" + role + "}"

                await aprint(_("You chose {} to kick the penalty").format(kicker_name))

                q0_remain = False
            except (ValueError, TypeError):
                await aprint(_("Invalid answer."))
                await controller(require_input=False)
                await clean_screen()

        assert kicker_name is not None and kicker_placeholder is not None

        await clean_screen()

        await aprint(self.render_header(), end="\n\n")

        await aprint(
            format_phrase(
                _(
                    "Now all the players and supporter of {def_team_name} must close their eyes or look away from the screen."
                ),
                team_atk,
                team_def,
                assigments,
            )
        )

        await controller(require_input=False)

        await clean_screen()

        await aprint(self.render_header(), end="\n\n")

        _kick_direction_name, kick_direction_id = None, None
        q1_remain = True

        while q1_remain:
            await aprint(KICK_OR_DIVE_SELECTION_TEXT_ART, end="\n\n")
            await aprint(position_text, end="\n\n")

            await aprint(
                format_phrase(
                    _("{}, where are you kicking the ball?").format(kicker_placeholder),
                    team_atk,
                    team_def,
                    assigments,
                )
            )

            q1_choice = await controller(require_input=True)
            if q1_choice is None:
                raise TypeError("An user input was expected, but None was found.")
            try:
                q1_int = int(q1_choice)
                if not 0 <= q1_int <= len(direction_names):
                    raise ValueError(
                        _("Number must be between 0 and ") + str(len(team_def.players))
                    )
                if q1_int == 0:
                    kick_direction_index = np.random.randint(
                        0, len(direction_names) - 1
                    )
                else:
                    kick_direction_index = q1_int - 1
                kick_direction_id = ALL_PENALTY_DIRECTIONS[kick_direction_index]
                q1_remain = False

            except (ValueError, TypeError):
                await aprint(_("Invalid answer."))
                await controller(require_input=False)
                await clean_screen()

        await clean_screen()
        await aprint(self.render_header(), end="\n\n")
        await aprint(_("Everyone can look again at the screen"))
        await controller(require_input=False)

        await clean_screen()

        await aprint(self.render_header(), end="\n\n")
        await aprint(
            format_phrase(
                _(
                    "Now all the players and supporter of {atk_team_name} must close their eyes or look away from the screen."
                ),
                team_atk,
                team_def,
                assigments,
            )
        )
        await controller(require_input=False)

        await clean_screen()
        await aprint(self.render_header(), end="\n\n")

        _def_goalkeeper = assigments["def_goalkeeper"]

        _save_direction_name, save_direction_id = None, None
        q2_remain = True

        while q2_remain:
            await aprint(self.render_header(), end="\n\n")
            await aprint(KICK_OR_DIVE_SELECTION_TEXT_ART, end="\n\n")
            await aprint(position_text, end="\n\n")

            await aprint(
                format_phrase(
                    _("{def_goalkeeper} where are you diving?"),
                    team_atk,
                    team_def,
                    assigments,
                )
            )
            q2_choice = await controller(require_input=True)
            if q2_choice is None:
                raise TypeError("An user input was expected, but None was found.")
            try:
                q2_int = int(q2_choice)

                if not 0 <= q2_int <= len(direction_names):
                    raise ValueError(
                        _("Number must be between 0 and ") + str(len(direction_names))
                    )
                if q2_int == 0:
                    save_position_idx = np.random.randint(0, len(direction_names) - 1)
                else:
                    save_position_idx = q2_int - 1

                save_direction_id = ALL_PENALTY_DIRECTIONS[save_position_idx]
                q2_remain = False
            except (ValueError, TypeError):
                await aprint(_("Invalid answer."))
                await controller(require_input=False)
                await clean_screen()

        await clean_screen()
        await aprint(self.render_header(), end="\n\n")
        await aprint(_("Everyone can look again at the screen"))
        await controller(require_input=False)

        await clean_screen()

        assert save_direction_id is not None
        assert kick_direction_id is not None

        return PenaltyInteractionResult(
            kicker_placeholder, kick_direction_id, "{def_goalie}", save_direction_id
        )


async def clean_screen():
    # await aprint(CLEAR_CHAR)
    pass


def format_phrase(
    phrase: str,
    atk_team: Team,
    def_team: Team,
    assignments: Mapping[str, str],
    attrs=[],
):
    formatted_dict = {}

    for assign_key, value in assignments.items():
        if "atk" in assign_key:
            formatted_dict[assign_key] = colored(
                assignments[assign_key],
                atk_team.color,
                attrs=attrs,  # type: ignore
            )  # type:ignore
        elif "def" in assign_key:
            formatted_dict[assign_key] = colored(
                assignments[assign_key],
                def_team.color,
                attrs=attrs,  # type: ignore
            )  # type:ignore
        else:
            formatted_dict[assign_key] = assignments[assign_key]

    return phrase.format(**formatted_dict)


def format_goal_entry(goal: GoalStats):
    player_name = goal.author
    minute = format_minute(goal.time)

    match goal.goal_type:
        case "goal":
            return f"{player_name} {minute}"
        case "own_goal":
            return f"{player_name} {minute} (AG)"
        case "penalty":
            return f"{player_name} {minute} (R)"
        case _:
            return f"{player_name} {minute}"


def format_minute(time: MatchTime):
    base_minute = 0

    if time.phase > MatchPhase.FIRST_HALF:
        base_minute += MatchPhase.FIRST_HALF.duration_minutes
    if time.phase > MatchPhase.SECOND_HALF:
        base_minute += MatchPhase.SECOND_HALF.duration_minutes
    if time.phase > MatchPhase.FIRST_EXTRA_TIME:
        base_minute += MatchPhase.FIRST_EXTRA_TIME.duration_minutes
    if time.phase > MatchPhase.SECOND_EXTRA_TIME:
        base_minute += MatchPhase.SECOND_EXTRA_TIME.duration_minutes

    added_time = max(0, time.minute - time.phase.duration_minutes)
    total_minute = base_minute + min(time.phase.duration_minutes, time.minute)

    if added_time > 0:
        return f"{total_minute}'+{added_time}"
    else:
        return f"{total_minute}'"
