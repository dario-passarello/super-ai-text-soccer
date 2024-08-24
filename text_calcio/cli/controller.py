from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal, Optional

from aioconsole import ainput, aprint
import yaml

from text_calcio.cli.display import clean_screen, CLIDisplay
from text_calcio.state.match import Match, Penalty


class CLIController:
    @dataclass
    class Config:
        automatic_mode: bool = False
        penalty_mode: Literal["always_auto", "always_player"] = "always_player"

    def __init__(
        self, match: Match, config: Optional[CLIController.Config] = None
    ) -> None:
        self.config = config or CLIController.Config()
        self.match = match
        self.display = CLIDisplay(match)

    async def __call__(self, require_input=False) -> Optional[str]:
        if require_input:
            return await self.get_user_input()
        else:
            await self.prompt_continue()
            return None

    def update_match(self, match):
        self.match = match
        self.display.match = match

    async def get_user_input(self):
        result = await ainput("> ")
        return result

    async def prompt_continue(self):
        if self.config.automatic_mode:
            await asyncio.sleep(1)
        else:
            await ainput("[↵]")

    async def run(self):
        await self.match.prefetch_blueprints(3)
        while not self.match.is_match_finished():
            with open("match.yaml", "w") as f:
                yaml.dump(self.match.serialize(), f)

            curr_action = self.match.get_current_action()

            if curr_action is None:
                await aprint(self.display.render_header(), end="\n\n\n")
                await self.prompt_continue()
            else:
                async for _ in self.display.display_action_sequence():
                    await self.prompt_continue()

                if curr_action.is_penalty_pending():
                    penalty_result = await self.display.penalty_interaction(self)

                    penalty = Penalty.create_player_kicked_penalty(
                        penalty_result.player_kicking,
                        penalty_result.player_saving,
                        penalty_result.kick_direction,
                        penalty_result.save_direction,
                    )

                    self.update_match(self.match.kick_penalty(penalty))

                await clean_screen()

                if curr_action.is_goal():
                    await aprint(self.display.render_after_goal_view())
                    await self.prompt_continue()

                await clean_screen()

                await aprint(
                    self.display.render_evaluations(self.match.get_current_action())
                )
                await self.prompt_continue()

            await clean_screen()

            await aprint(self.display.render_header(), end="\n\n\n")

            await aprint("Loading ...")

            self.update_match(await self.match.next())

            await clean_screen()
        with open("match.yaml", "w") as f:
            yaml.dump(self.match.serialize(), f)
