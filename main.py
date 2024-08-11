

from text_calcio.loader import load_flavors, load_phrases
from text_calcio.display import CLIController
from text_calcio.match_state import MatchState
from text_calcio.team import Team
import random

def main():
    phrases = load_phrases()
    stadiums, referees = load_flavors()

    random_stadium = random.choice(stadiums)
    random_referee = random.choice(referees)

    team_1 = Team(
        'A.C. FORGIA', 'FOS', "blue", ['Kien', 'Dani', 'Dario', 'Dav', 'Max']
    )

    team_2 = Team(
        'F.C. PASTA CALCISTICA', 'PAS', "red", ['Gio', 'Giammy', 'Pit', 'Stef', 'Paso']
    )


    match = MatchState(team_1, team_2, phrases, random_stadium, random_referee)

    controller = CLIController(match)

    controller.run()




if __name__ == '__main__':
    main()