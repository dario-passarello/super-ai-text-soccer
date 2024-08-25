from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal, Optional

from aioconsole import ainput, aprint
import yaml

from text_calcio.cli.display import clean_screen, CLIDisplay
from text_calcio.loaders.action import AsyncActionLoader
from text_calcio.state.match import Match, Penalty


class CLIController:
    @dataclass
    class Config:
        automatic_mode: bool = False
        penalty_mode: Literal["always_auto", "always_player"] = "always_player"

    def __init__(
        self,
        match: Match,
        action_loader: AsyncActionLoader,
        config: Optional[CLIController.Config] = None,
    ) -> None:
        self.config = config or CLIController.Config()
        self.match = match
        self.prefetched_match = match
        self.action_loader = action_loader
        self.display = CLIDisplay(match)
        self.condition_variable = asyncio.Condition()

    async def __call__(self, require_input=False) -> Optional[str]:
        if require_input:
            return await self.get_user_input()
        else:
            await self.prompt_continue()
            return None

    def update_match(self, match: Match):
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

    async def prefetch_loop(self):
        while not self.match.is_match_finished():
            async with self.condition_variable:
                if self.prefetched_match.is_penalty_pending():
                    await aprint(
                        f"Penalty pending at {self.prefetched_match.game_clock}"
                    )
                    await self.condition_variable.wait_for(
                        lambda: not self.prefetched_match.is_penalty_pending()
                    )
                self.condition_variable.notify_all()

            new_data = await self.prefetched_match.generate_action_and_advance(
                self.action_loader
            )
            self.prefetched_match = new_data

    async def controller_loop(self):
        while not self.match.is_match_finished():
            with open("match.yaml", "w") as f:
                yaml.dump(self.match.serialize(), f)

            curr_action = self.match.get_action_from_game_clock()

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
                    async with self.condition_variable:
                        self.prefetched_match.kick_penalty(penalty)
                        self.condition_variable.notify_all()
                await clean_screen()

                if curr_action.is_goal():
                    await aprint(self.display.render_after_goal_view())
                    await self.prompt_continue()

                await clean_screen()

                await aprint(
                    self.display.render_evaluations(
                        self.match.get_action_from_game_clock()
                    )
                )
                await self.prompt_continue()

            await clean_screen()

            await aprint(self.display.render_header(), end="\n\n\n")

            await aprint("Loading ...")

            await aprint(
                f"Game: {self.match.game_clock} Prefetch: {self.prefetched_match.game_clock}"
            )
            async with self.condition_variable:
                if self.match.game_clock >= self.prefetched_match.game_clock:
                    await aprint("Waiting")
                    await self.condition_variable.wait_for(
                        lambda: self.match.game_clock < self.prefetched_match.game_clock
                    )
                await aprint(len(self.prefetched_match.actions))
                self.condition_variable.notify_all()
                new_match = await self.match.advance_from_action_list(
                    tuple(self.prefetched_match.actions),
                    self.prefetched_match.stoppage_times,
                )
                self.update_match(new_match)

            await clean_screen()
        with open("prefetch_match.yaml", "w") as f:
            yaml.dump(self.match.serialize(), f)

    async def run(self):
        await asyncio.gather(self.controller_loop(), self.prefetch_loop())
