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

import random

from text_calcio.state.penalty import ALL_PENALTY_DIRECTIONS


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
        while not self.match_waiting_for_input() and not self.match_finished():
            self.match = await self.match.next()

    async def run(self):
        while not self.match_finished():
            await self.continue_until_input_required()

            if self.match_waiting_for_input():
                await self.handle_penalty()

        print("Match finished")
        print(self.match.to_yaml())
        print(self.match)
        return self.match

    async def handle_penalty(self):
        if not self.match_waiting_for_input():
            raise RuntimeError("No penalty to handle")

        print("Handling penalty")

        current_action = self.current_action()

        if current_action is None:
            raise RuntimeError("No action to handle")

        # Random penalty handling

        # TODO: I don't think this is the best way to store/access player data in the action.
        player_kicking = current_action.player_assignments["atk_1"]
        goalkeeper = current_action.player_assignments["def_goalkeeper"]

        penalty = Penalty.create_auto_penalty(player_kicking, goalkeeper)

        self.match = self.match.kick_penalty(penalty)
        self.match = await self.match.next()

        print("Penalty handled", penalty)

        # penalty_result = await self.display.penalty_interaction(self)

        # penalty = Penalty.create_player_kicked_penalty(
        #     penalty_result.player_kicking,
        #     penalty_result.player_saving,
        #     penalty_result.kick_direction,
        #     penalty_result.save_direction,
        # )

        # self.match = self.match.kick_penalty(penalty)
