from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from typing import Optional

from aioconsole import aprint
from text_calcio.loaders.action import ActionBlueprint, ActionRequest
from text_calcio.loaders.ai.action_loader import AsyncActionLoader
from text_calcio.loaders.ai.action_loader import AsyncAIActionLoader


class AsyncActionProvider(ABC):
    @abstractmethod
    async def get(self) -> ActionBlueprint:
        pass

    @abstractmethod
    async def request(self, request: ActionRequest):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def __enter__(self) -> AsyncActionProvider:
        pass

    @abstractmethod
    def __exit__(self, type, value, traceback):
        pass


class AsyncQueueActionProvider(AsyncActionProvider):
    MAX_RETRIES = 3

    def __init__(
        self,
        loader: AsyncActionLoader,
        result_queue: Optional[asyncio.Queue[ActionBlueprint]] = None,
        request_queue: Optional[asyncio.Queue[ActionRequest]] = None,
    ) -> None:
        self.loader = loader
        self.result_queue = result_queue or asyncio.Queue()
        self.request_queue = request_queue or asyncio.Queue()
        self.task: Optional[asyncio.Task] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def start(self):
        self.task = asyncio.create_task(self.produce())

    def close(self):
        if self.task is not None:
            self.task.cancel()
            self.task = None

    async def produce(self):
        try:
            while True:
                request = await self.request_queue.get()

                for attempt in range(self.MAX_RETRIES):
                    try:
                        generated_blueprint = await self.loader.generate(request)
                        generated_blueprint.validate()
                        await self.result_queue.put(generated_blueprint)
                        break
                    except Exception as e:
                        if isinstance(e, asyncio.CancelledError):
                            raise
                        if attempt < self.MAX_RETRIES - 1:
                            pass
                        else:
                            await aprint("Max retries reached. Operation failed.")
                            raise  # Re-raise the exception if max retries reached
        except asyncio.CancelledError:
            pass

    async def get(self):
        return await self.result_queue.get()

    async def request(self, request: ActionRequest):
        await self.request_queue.put(request)
