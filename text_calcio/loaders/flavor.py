from __future__ import annotations

import json
from typing import Optional

from text_calcio.state.stadium import Stadium

import importlib.resources as pkg_resources

def load_flavors(path : Optional[str] = None):
    if path is None:
        with pkg_resources.open_text('text_calcio.resources', 'flavors.json') as f:
            flavs = json.load(f)
        stadiums = flavs['stadiums']
    else:
        with open(path) as f:
            flavs = json.load(f)
        stadiums = flavs['stadiums']

    list_stadium = [Stadium.from_dict(stadium_dict) for stadium_dict in stadiums]
    list_referee = flavs['referees']
    return list_stadium, list_referee