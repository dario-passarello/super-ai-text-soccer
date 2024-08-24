from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal, Optional

from aioconsole import ainput, aprint
import yaml

from text_calcio.cli.display import clean_screen, CLIDisplay
from text_calcio.state.match import Match, Penalty

from text_calcio.loaders.action import ActionRequest
from text_calcio.loaders.action import ActionBlueprint, ActionRequest, AsyncActionLoader


class TestLoader(AsyncActionLoader):
    def __init__(self) -> None:
        pass

    async def generate(self, request: ActionRequest) -> ActionBlueprint:
        print(request)

        action_schema = ActionBlueprint(
            request.action_type,
            request.use_var,
            [],
            {},
            "culo",
            "cacca",
        )

        return action_schema


class TestController:
    @dataclass
    class Config:
        automatic_mode: bool = False
        penalty_mode: Literal["always_auto", "always_player"] = "always_player"

    def __init__(
        self, match: Match, config: Optional[TestController.Config] = None
    ) -> None:
        self.match = match
        self.config = config or TestController.Config()

    async def __call__(self) -> Optional[str]:
        pass

    def current_action(self):
        return self.match.get_current_action()

    def match_finished(self) -> bool:
        return self.match.is_match_finished()

    def match_waiting_for_input(self) -> bool:
        return (a := self.current_action()) is not None and a.is_penalty_pending()

    async def continue_until_input_required(self) -> None:
        while not self.match_waiting_for_input():
            self.match = await self.match.next()

    async def run(self):
        # await self.match.prefetch_blueprints(3)
        while not self.match.is_match_finished():
            await self.continue_until_input_required()

            print("awooo")

            print(self.match)

        # penalty_result = await self.display.penalty_interaction(self)

        # penalty = Penalty.create_player_kicked_penalty(
        #     penalty_result.player_kicking,
        #     penalty_result.player_saving,
        #     penalty_result.kick_direction,
        #     penalty_result.save_direction,
        # )

        # self.match = self.match.kick_penalty(penalty)
