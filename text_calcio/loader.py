from __future__ import annotations

import json

from text_calcio.stadium import Stadium


def load_phrases(path : str = 'phrases.json'):
    with open(path, 'r') as f:
        phr = json.load(f)
    return phr


def load_flavors(path : str = 'flavors.json'):
    with open(path, 'r') as f:
        flavs = json.load(f)
    stadiums = flavs['stadiums']

    list_stadium = [Stadium.from_dict(stadium_dict) for stadium_dict in stadiums]
    list_referee = flavs['referees']
    return list_stadium, list_referee