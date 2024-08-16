

import asyncio
import os
from text_calcio.ai import AsyncAIActionGenerator, AsyncActionProducer
from text_calcio.loader import load_flavors, load_phrases
from text_calcio.display import CLIController
from text_calcio.match_state import MatchConfig, MatchState
from text_calcio.team import Team
import random
from openai import AsyncOpenAI, OpenAI
from dotenv import load_dotenv

def main():

    load_dotenv()

    client = AsyncOpenAI(
        # This is the default and can be omitted
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

    phrases = load_phrases()
    stadiums, referees = load_flavors()

    random_stadium = random.choice(stadiums)
    random_referee = random.choice(referees)

    action_generator = AsyncAIActionGenerator(client)

    team_1 = Team(
        'A.C. FORGIA', 'FORGIA', 'FOR', "blue", ['Kien', 'Dani', 'Dario', 'Dav', 'Max']
    )

    team_2 = Team(
        'F.C. PASTA CALCISTICA', 'PASTA', 'PAS', "red", ['Gio', 'Giammy', 'Pit', 'Stef', 'Paso']
    )

    match_config = MatchConfig()
    match = MatchState(team_1, team_2, phrases, random_stadium, random_referee, match_config)


    controller = CLIController(match)
    producer = AsyncActionProducer(action_generator, match.blueprint_queue, match.demand_queue)
    asyncio.run(run_controller_producer(controller, producer))

async def run_controller_producer(controller : CLIController, producer : AsyncActionProducer):
    await asyncio.gather(controller.run(), producer.produce())


if __name__ == '__main__':
    main()