from typing import Mapping

from termcolor import colored
from text_calcio.match_state import MatchState
from text_calcio.team import Team

CLEAR_CHAR = "\033c"


class CLIDisplay:

    def __init__(self, match: MatchState) -> None:
        self.match = match
        self.phrase_counter = 0

    def display_minute(self):
        if self.match.curr_phase == MatchState.Phase.FIRST_HALF:
            return f"{self.match.curr_minute}' (1T)"
        elif self.match.curr_phase == MatchState.Phase.SECOND_HALF:
            return f"{self.match.curr_minute + 45}' (2T)"
        elif self.match.curr_phase == MatchState.Phase.FIRST_ADD_TIME:
            return f"{self.match.curr_minute + 90}' (1TS)"
        elif self.match.curr_phase == MatchState.Phase.SECOND_ADD_TIME:
            return f"{self.match.curr_minute + 105}' (2TS)"
        elif self.match.curr_phase == MatchState.Phase.SECOND_ADD_TIME:
            return f"Penalties"

    def display_score(self):

        t1 = self.match.get_team_1()
        t2 = self.match.get_team_2()
        score_t1, score_t2 = self.match.get_current_score()

        return f"{t1.abbr} {score_t1} - {score_t2} {t2.abbr}"

    def display_header(self):

        display = CLEAR_CHAR
        display += f"{self.display_score()} || {self.display_minute()}"
        display += "\n" * 2
        return display

    def display(self):
        last_action = self.match.get_current_action()
        header = self.display_header()

        if last_action is None:
            return [header]
        
        team_1 = self.match.get_team_1()
        team_2 = self.match.get_team_2()

        team_atk = team_1 if last_action.team_atk_id == 0 else team_2
        team_def = team_2 if last_action.team_atk_id == 0 else team_1

        formatted_phrases : list[str] = []

        for phrase in last_action.sentences:
            formatted_phrases.append(format_phrase(phrase, team_atk, team_def, last_action.get_all_assigments()))


        return [header + '\n'.join(formatted_phrases[:i + 1]) for i in range(len(formatted_phrases))]

class CLIController:

    def __init__(self, match: MatchState) -> None:
        self.match = match
        self.display = CLIDisplay(match)

    def run(self):
        while not self.match.is_match_finised():

            strings = self.display.display()
            for string in strings:
                print(string)
                x = input()
            self.match.next()


def format_phrase(
    phrase: str, atk_team: Team, def_team: Team, assignments: Mapping[str, str]
):
    formatted_dict = {}
    for assign_key, value in assignments.items():
        if "atk" in assign_key:
            formatted_dict[assign_key] = colored(
                assignments[assign_key], atk_team.color  # type: ignore
            )  # type:ignore
        elif "def" in assign_key:
            formatted_dict[assign_key] = colored(
                assignments[assign_key], def_team.color  # type: ignore
            )  # type:ignore
        else:
            formatted_dict[assign_key] = assignments[assign_key]
            

    return phrase.format(**formatted_dict)
