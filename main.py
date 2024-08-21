import asyncio
import os
import random
from openai import AsyncOpenAI
from dotenv import load_dotenv

from text_calcio.cli.controller import CLIController
from text_calcio.loaders.action_provider import AsyncQueueActionProvider
from text_calcio.loaders.ai.action_loader import AsyncAIActionLoader
from text_calcio.loaders.flavor import load_flavors
from text_calcio.state.match import Match, MatchConfig
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

    home_team = Team(
        "A.C. FORGIA", "FORGIA", "FOR", "blue", ["Kien", "Dani", "Dario", "Dav", "Max"]
    )

    away_team = Team(
        "F.C. PASTA CALCISTICA",
        "PASTA",
        "PAS",
        "red",
        ["Gio", "Giammy", "Pit", "Stef", "Paso"],
    )

    config = MatchConfig.from_json(
        os.path.join(os.path.dirname(__file__), "text_calcio/resources/config.json")
    )

    with AsyncQueueActionProvider(action_generator) as provider:
        match = Match(
            home_team=home_team,
            away_team=away_team,
            stadium=random_stadium,
            referee=random_referee,
            action_provider=provider,
            config=config,
        )

        controller = CLIController(match)
        await controller.run()


if __name__ == "__main__":
    main()
