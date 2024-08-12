

import os
from text_calcio.ai import AIActionGenerator
from text_calcio.loader import load_flavors, load_phrases
from text_calcio.display import CLIController
from text_calcio.match_state import MatchState
from text_calcio.team import Team
import random
from openai import OpenAI
from dotenv import load_dotenv

def main():

    load_dotenv()

    client = OpenAI(
        # This is the default and can be omitted
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

    phrases = load_phrases()
    stadiums, referees = load_flavors()

    random_stadium = random.choice(stadiums)
    random_referee = random.choice(referees)

    action_generator = AIActionGenerator(client)

    team_1 = Team(
        'A.C. FORGIA', 'FORGIA', 'FOS', "blue", ['Kien', 'Dani', 'Dario', 'Dav', 'Max']
    )

    team_2 = Team(
        'F.C. PASTA CALCISTICA', 'PASTA', 'PAS', "red", ['Gio', 'Giammy', 'Pit', 'Stef', 'Paso']
    )


    match = MatchState(team_1, team_2, phrases, random_stadium, random_referee, action_generator)

    controller = CLIController(match)

    controller.run()




if __name__ == '__main__':
    main()