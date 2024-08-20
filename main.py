import asyncio
import os
import random
from openai import AsyncOpenAI
from dotenv import load_dotenv

from text_calcio.cli.controller import CLIController
from text_calcio.loaders.action_provider import AsyncQueueActionProvider
from text_calcio.loaders.ai.action_loader import AsyncAIActionLoader
from text_calcio.loaders.flavor import load_flavors
from text_calcio.state.match import Match
from text_calcio.state.team import Team


def main():
    asyncio.run(execute())


async def execute():
    load_dotenv()

    client = AsyncOpenAI(
        # This is the default and can be omitted
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

    stadiums, referees = load_flavors()

    random_stadium = random.choice(stadiums)
    random_referee = random.choice(referees)

    action_generator = AsyncAIActionLoader(client)

    team_1 = Team(
        "A.C. FORGIA", "FORGIA", "FOR", "blue", ["Kien", "Dani", "Dario", "Dav", "Max"]
    )

    team_2 = Team(
        "F.C. PASTA CALCISTICA",
        "PASTA",
        "PAS",
        "red",
        ["Gio", "Giammy", "Pit", "Stef", "Paso"],
    )

    with AsyncQueueActionProvider(action_generator) as provider:
        match = Match(team_1, team_2, random_stadium, random_referee, provider)

        controller = CLIController(match)
        await controller.run()


if __name__ == "__main__":
    main()
