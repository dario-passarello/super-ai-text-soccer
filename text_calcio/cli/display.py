
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional
from aioconsole import ainput
import numpy as np
from termcolor import colored

from text_calcio.state.match import Match
from text_calcio.state.penalty import ALL_PENALTY_DIRECTIONS, PenaltyDirection
from text_calcio.state.team import Team


CLEAR_CHAR = "\033c"


class CLIDisplay:
    @dataclass
    class Config:
        pass

    def __init__(self, match: Match, config : Optional[CLIDisplay.Config] = None) -> None:
        self.config = config or CLIDisplay.Config()
        self.match = match
        self.phrase_counter = 0

    def display_minute(self):
        if self.match.curr_phase == Match.Phase.FIRST_HALF:
            return f"{self.match.curr_minute}' (1T)"
        elif self.match.curr_phase == Match.Phase.SECOND_HALF:
            return f"{self.match.curr_minute + 45}' (2T)"
        elif self.match.curr_phase == Match.Phase.FIRST_ADD_TIME:
            return f"{self.match.curr_minute + 90}' (1TS)"
        elif self.match.curr_phase == Match.Phase.SECOND_ADD_TIME:
            return f"{self.match.curr_minute + 105}' (2TS)"
        elif self.match.curr_phase == Match.Phase.SECOND_ADD_TIME:
            return f"Penalties"

    def display_score(self):

        t1 = self.match.get_team_1()
        t2 = self.match.get_team_2()
        score_t1, score_t2 = self.match.get_no_spoiler_score()

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

    async def penalty_interaction(self) -> tuple[tuple[str, PenaltyDirection], tuple[str , PenaltyDirection]]:
        last_action = self.match.get_current_action()
        if last_action is None:
            raise RuntimeError('No penalty found')
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

        direction_names = ['Top Left corner', 'Top Left on the ground', 'Center below crossbar', 'Center on the ground', 'Top Right corner', 'Right on the ground']

        position_text = '\n'.join(['0 - Random'] + [f'{i + 1} - {position}' for i, position in enumerate(direction_names)])

        q0_remain = True
        role, kicker_name, kicker_placeholder = None, None, None

        print(CLEAR_CHAR)
        while q0_remain:
            print(assigments)
            print(format_phrase('A penality was awarded to {atk_team_name} kicks the penalty. Who is going to kick it?', team_atk, team_def, assigments))
            player_list = '\n'.join(['0 - Random'] + [f'{i + 1} - {name}' for i, (role, name) in enumerate(atk_assigments)])
            print(player_list)
            q0_choice = await ainput('> ')
            try:
                q0_int = int(q0_choice)
                if not 0 <= q0_int <= len(team_atk.players):
                    raise ValueError(f'Number must be between 0 and {len(team_atk.players)}')
                if q0_int == 0:
                    kicker_idx = np.random.randint(0, len(team_atk.players) - 1) 
                else:          
                    kicker_idx = q0_int - 1
                role, kicker_name = atk_assigments[kicker_idx]
                kicker_placeholder = '{' + role + '}'
                await ainput(f'You chose {kicker_name} to kick the penalty')
                q0_remain = False

            except ValueError:
                print(CLEAR_CHAR)
        assert kicker_name is not None and kicker_placeholder is not None

        print(CLEAR_CHAR)
        await ainput(format_phrase('Now all the players and supporter of {def_team_name} must close their eyes or look away from the screen.', team_atk, team_def, assigments))
        print(CLEAR_CHAR)


        kick_direction_name, kick_direction_id = None, None
        q1_remain = True
        while q1_remain:
            print(soccer_goal)
            print()
            print(position_text)
            print()
            print(format_phrase(f'{kicker_placeholder}, where are you kicking the ball?', team_atk, team_def, assigments))
            q1_choice = await ainput('> ')
            try:
                q1_int = int(q1_choice)
                if not 0 <= q1_int <= len(direction_names):
                    raise ValueError(f'Number must be between 0 and {len(direction_names)}')
                if q1_int == 0:
                    kick_direction_index = np.random.randint(0, len(direction_names) - 1) 
                else:          
                    kick_direction_index = q1_int - 1
                kick_direction_name = direction_names[kick_direction_index]
                kick_direction_id = ALL_PENALTY_DIRECTIONS[kick_direction_index]
                await ainput(format_phrase(f'{kicker_placeholder} chose to kick the ball to {kick_direction_name}', team_atk, team_def, assigments))
                q1_remain = False

            except ValueError:
                await ainput('Invalid answer.')
                print(CLEAR_CHAR)

        print(CLEAR_CHAR)
        await ainput('Everyone can look again at the screen')
        print(CLEAR_CHAR)
        await ainput(format_phrase('Now all the players and supporter of {atk_team_name} must close their eyes or look away from the screen.', team_atk, team_def, assigments))
        print(CLEAR_CHAR)

        def_goalie = assigments['def_goalie']

        save_direction_name, save_direction_id = None, None
        q2_remain = True
        while q2_remain:
            print(soccer_goal)
            print()
            print(position_text)
            print()
            print(format_phrase('{def_goalie} where are you diving?', team_atk, team_def, assigments))
            q2_choice = await ainput('> ')
            try:
                q2_int = int(q2_choice)
                if not 0 <= q2_int <= len(direction_names):
                    raise ValueError(f'Number must be between 0 and {len(direction_names)}')
                if q2_int == 0:
                    save_position_idx = np.random.randint(0, len(direction_names) - 1) 
                else:          
                    save_position_idx = q2_int - 1
                save_direction_name = direction_names[save_position_idx]
                save_direction_id = ALL_PENALTY_DIRECTIONS[save_position_idx]
                await ainput(format_phrase(f'{{def_goalie}} chose to dive {save_direction_name}', team_atk, team_def, assigments))
                q2_remain = False

            except ValueError:
                await ainput('Invalid answer.')
                print(CLEAR_CHAR)

        print(CLEAR_CHAR)
        print('Everyone can look again at the screen')
        await ainput('Narration resuming... GOOD LUCK')
        print(CLEAR_CHAR)

        assert save_direction_id is not None
        assert kick_direction_id is not None
        return (kicker_placeholder, kick_direction_id), ('{def_goalie}', save_direction_id)



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
