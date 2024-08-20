from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from operator import itemgetter
from typing import Mapping, Optional
from aioconsole import ainput
import numpy as np
from termcolor import colored

from text_calcio.state.match import Action, Match
from text_calcio.state.match_stats import GoalStats, MatchStats
from text_calcio.state.penalty import ALL_PENALTY_DIRECTIONS, PenaltyDirection
from text_calcio.state.team import Team

from text_calcio.cli.i18n import _

import tabulate

CLEAR_CHAR = "\033c"


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

    def display_minute(self):
        additional_time = (
            self.match.curr_minute - self.match.curr_phase.duration_minutes
        )

        base_minute = min(
            self.match.curr_phase.duration_minutes, self.match.curr_minute
        )

        phase_indicator = ""
        if self.match.curr_phase == Match.Phase.FIRST_HALF:
            phase_indicator = _("1st")
            base_minute += 0
        elif self.match.curr_phase == Match.Phase.SECOND_HALF:
            phase_indicator = _("2nd")
            base_minute += 45
        elif self.match.curr_phase == Match.Phase.FIRST_EXTRA_TIME:
            phase_indicator = _("1st ET")
            base_minute += 90
        elif self.match.curr_phase == Match.Phase.SECOND_EXTRA_TIME:
            phase_indicator = _("2nd ET")
            base_minute += 105
        elif self.match.curr_phase == Match.Phase.PENALTIES:
            phase_indicator = _("Shootout")
            base_minute += 120
            return _("Kick") + f" {(self.match.curr_minute // 2)} {phase_indicator}"

        final_str = f"{base_minute}:00"
        if additional_time > 0:
            final_str += (
                f" + {additional_time}:00  (+{self.match.get_added_time_minutes()})"
            )
        final_str += f" {phase_indicator}"

        return final_str

    def display_score(self):
        t1 = self.match.get_team_1()
        t2 = self.match.get_team_2()
        score_t1, score_t2 = self.match.get_no_spoiler_score()

        return f"{t1.abbr} {score_t1} - {score_t2} {t2.abbr}"

    def display_header(self):
        t1 = self.match.get_team_1()
        t2 = self.match.get_team_2()
        score_t1, score_t2 = self.match.get_no_spoiler_score()
        t1_fmt = colored(t1.abbr, t1.color)  # type: ignore
        t2_fmt = colored(t2.abbr, t2.color)  # type: ignore

        display = tabulate.tabulate(
            [[t1_fmt, f"{score_t1} - {score_t2}", t2_fmt, self.display_minute()]],
            headers=[],
            tablefmt="rounded_grid",
        )
        return display

    def display_after_goal(self):
        t1 = self.match.get_team_1()
        t2 = self.match.get_team_2()
        score_t1, score_t2 = self.match.get_current_score()
        t1_fmt = colored(t1.full_name, t1.color)  # type: ignore
        t2_fmt = colored(t2.full_name, t2.color)  # type: ignore
        stats = MatchStats.create_from_match(self.match)

        t1_goals = [format_goal_entry(goal) for goal in stats.team_1_stats.goals]
        t2_goals = [format_goal_entry(goal) for goal in stats.team_2_stats.goals]

        headers = [t1_fmt, f"{score_t1} - {score_t2}", t2_fmt]

        data = [["\n".join(t1_goals), "", "\n".join(t2_goals)]]

        display = tabulate.tabulate(
            data,
            headers=headers,
            tablefmt="rounded_grid",
            colalign=["left", "center", "right"],
        )
        return display

    def display_evalations(self, action: Optional[Action] = None):
        stats = MatchStats.create_from_match(self.match)
        tm_1_eval = [
            (pl, ev, 0) for pl, ev in stats.team_1_stats.player_evaluation.items()
        ]
        tm_2_eval = [
            (pl, ev, 1) for pl, ev in stats.team_2_stats.player_evaluation.items()
        ]
        merged = sorted(tm_1_eval + tm_2_eval, key=itemgetter(1), reverse=True)
        if action is not None:
            delta_evals = action.players_evaluation
            # Replace role placeholder with names
            delta_evals = {
                action.map_role_to_name(role): delta_eval
                for role, delta_eval in delta_evals.items()
            }
            delta_evals = defaultdict(int, delta_evals)
            data = [
                (colored(pl, self.match.teams[tm].color), ev, delta_evals[pl])
                for pl, ev, tm in merged
            ]  # type: ignore
            headers = [_("Player"), _("Evaluation"), _("Change")]
            colalign = ["left", "right", "right"]
        else:
            headers = [_("Player"), _("Evaluation")]
            data = [
                (colored(pl, self.match.teams[tm].color), ev) for pl, ev, tm in merged
            ]  # type: ignore
            colalign = ["left", "right"]

        display = tabulate.tabulate(
            data, headers=headers, tablefmt="rounded_grid", colalign=colalign
        )
        return display

    def display(self) -> tuple[str, list[list[str]]]:
        last_action = self.match.get_current_action()
        header = CLEAR_CHAR + self.display_header()

        if last_action is None:
            return header, []

        team_1 = self.match.get_team_1()
        team_2 = self.match.get_team_2()

        team_atk = team_1 if last_action.team_atk_id == 0 else team_2
        team_def = team_2 if last_action.team_atk_id == 0 else team_1

        formatted_phrases: list[str] = []

        for i, phrase in enumerate(last_action.sentences):
            formatted_phrases.append(
                format_phrase(
                    phrase, team_atk, team_def, last_action.get_all_assigments()
                )
            )

        return header, [
            formatted_phrases[: i + 1] for i in range(len(formatted_phrases))
        ]

    def print_display(self, header: str, phrases_order: list[str]):
        print(header)
        print()
        print()
        last_phrases = phrases_order[::-1][:5]
        if len(last_phrases) > 0:
            print(colored(f"> {last_phrases[0]}"))
            print()

            for phrase in last_phrases[1:]:
                print(phrase)
                print()

    async def penalty_interaction(
        self,
    ) -> tuple[tuple[str, PenaltyDirection], tuple[str, PenaltyDirection]]:
        random_option = "0 - " + _("random")

        last_action = self.match.get_current_action()
        if last_action is None:
            raise RuntimeError("No penalty found")
        assigments = last_action.get_all_assigments()
        team_1 = self.match.get_team_1()
        team_2 = self.match.get_team_2()

        team_atk = team_1 if last_action.team_atk_id == 0 else team_2
        team_def = team_2 if last_action.team_atk_id == 0 else team_1

        atk_assigments = list(last_action.get_atk_players_assigments().items())

        soccer_goal = """
._____________.
|(1)  (3)  (5)|
|             |    ???
|             |  (0) ???
|(2)  (4)  (6)|    ???
"""

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

        print(CLEAR_CHAR)
        while q0_remain:
            print(self.display_header())
            print()
            print(
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
            print(player_list)
            q0_choice = await ainput("> ")
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
                await ainput(_("You chose {} to kick the penalty").format(kicker_name))
                q0_remain = False

            except ValueError:
                print(CLEAR_CHAR)
        assert kicker_name is not None and kicker_placeholder is not None

        print(CLEAR_CHAR)
        print(self.display_header())
        print()
        await ainput(
            format_phrase(
                _(
                    "Now all the players and supporter of {def_team_name} must close their eyes or look away from the screen."
                ),
                team_atk,
                team_def,
                assigments,
            )
        )
        print(CLEAR_CHAR)
        print(self.display_header())
        print()

        _kick_direction_name, kick_direction_id = None, None
        q1_remain = True
        while q1_remain:
            print(soccer_goal)
            print()
            print(position_text)
            print()
            print(
                format_phrase(
                    _("{}, where are you kicking the ball?").format(kicker_placeholder),
                    team_atk,
                    team_def,
                    assigments,
                )
            )
            q1_choice = await ainput("> ")
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

            except ValueError:
                await ainput(_("Invalid answer."))
                print(CLEAR_CHAR)

        print(CLEAR_CHAR)
        print(self.display_header())
        print()
        await ainput(_("Everyone can look again at the screen"))
        print(CLEAR_CHAR)
        print(self.display_header())
        print()
        await ainput(
            format_phrase(
                _(
                    "Now all the players and supporter of {atk_team_name} must close their eyes or look away from the screen."
                ),
                team_atk,
                team_def,
                assigments,
            )
        )
        print(CLEAR_CHAR)
        print(self.display_header())
        print()

        _def_goalie = assigments["def_goalie"]

        _save_direction_name, save_direction_id = None, None
        q2_remain = True
        while q2_remain:
            print(self.display_header())
            print()
            print(soccer_goal)
            print()
            print(position_text)
            print()
            print(
                format_phrase(
                    _("{def_goalie} where are you diving?"),
                    team_atk,
                    team_def,
                    assigments,
                )
            )
            q2_choice = await ainput("> ")
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

            except ValueError:
                await ainput(_("Invalid answer."))
                print(CLEAR_CHAR)

        print(CLEAR_CHAR)
        print(self.display_header())
        print()
        await ainput(_("Everyone can look again at the screen"))
        print(CLEAR_CHAR)

        assert save_direction_id is not None
        assert kick_direction_id is not None
        return (kicker_placeholder, kick_direction_id), (
            "{def_goalie}",
            save_direction_id,
        )


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
    minute = format_minute(goal.match_phase, goal.minute)
    if goal.goal_type == "goal":
        return f"{player_name} {minute}"
    elif goal.goal_type == "own_goal":
        return f"{player_name} {minute} (AG)"
    elif goal.goal_type == "penalty":
        return f"{player_name} {minute} (R)"
    else:
        return f"{player_name} {minute}"


def format_minute(phase: Match.Phase, minute: int):
    base_minute = 0
    if phase > Match.Phase.FIRST_HALF:
        base_minute += Match.Phase.FIRST_HALF.duration_minutes
    if phase > Match.Phase.SECOND_HALF:
        base_minute += Match.Phase.SECOND_HALF.duration_minutes
    if phase > Match.Phase.FIRST_EXTRA_TIME:
        base_minute += Match.Phase.FIRST_EXTRA_TIME.duration_minutes
    if phase > Match.Phase.SECOND_EXTRA_TIME:
        base_minute += Match.Phase.SECOND_EXTRA_TIME.duration_minutes

    added_time = max(0, minute - phase.duration_minutes)

    total_minute = base_minute + min(phase.duration_minutes, minute)

    if added_time > 0:
        return f"{total_minute}'+{added_time}"
    else:
        return f"{total_minute}'"
