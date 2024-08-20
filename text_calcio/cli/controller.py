from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from aioconsole import ainput

from text_calcio.cli.display import clean_screen, CLIDisplay
from text_calcio.state.match import Match, Penalty


class CLIController:
    @dataclass
    class Config:
        penalty_mode: Literal["always_auto", "always_player"] = "always_player"

    def __init__(
        self, match: Match, config: Optional[CLIController.Config] = None
    ) -> None:
        self.config = config or CLIController.Config()
        self.match = match
        self.display = CLIDisplay(match)

    async def run(self):
        await self.match.prefetch_blueprints(3)
        while not self.match.is_match_finished():
            curr_action = self.match.get_current_action()
            header, strings = self.display.display()

            if curr_action is None:
                self.display.print_display(header, [])
                _x = await ainput()
            else:
                for phrases in strings:
                    self.display.print_display(header, phrases)
                    _x = await ainput()
                if self.match.is_penalty_pending():
                    (
                        (kicker, kick_pos),
                        (goalie, save_pos),
                    ) = await self.display.penalty_interaction()
                    penality = Penalty.create_player_kicked_penalty(
                        kicker, goalie, kick_pos, save_pos
                    )
                    self.match.kick_penalty(penality)
                clean_screen()
                if curr_action.is_goal():
                    print(self.display.display_after_goal())
                    await ainput()
                clean_screen()
                print(self.display.display_evalations(self.match.get_current_action()))
                await ainput()
            clean_screen()
            self.display.print_display(header, [])
            print("Loading ...")
            await self.match.next()
            clean_screen()
