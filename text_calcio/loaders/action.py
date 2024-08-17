from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import string
from typing import Container, Literal, Optional

ActionType = Literal["goal", "no_goal", "penalty", "own_goal"]


class AsyncActionLoader(ABC):
    
    @abstractmethod
    async def generate(self, request : ActionRequest) -> ActionBlueprint:
        pass


@dataclass
class ActionBlueprint:
    action_type : ActionType
    use_var : bool
    phrases : list[str]
    player_evaluation : dict[str, int]
    scorer_player : Optional[str]
    assist_player : Optional[str]

    def validate(self) -> None:
        if self.action_type == "goal" and self.scorer_player is None:
            raise ValueError('Action is type goal but no goal_player specified')
        for i, sentence in enumerate(self.phrases):
            inv_keys = find_invalid_keys(sentence, get_all_valid_placeholders())
            if len(inv_keys) > 0:
                raise ValueError(f'In sentence {i} invalid keys were found: {', '.join(inv_keys)}. Sentence: {sentence}')
        
        valid_player_placeholders = ['{' + role + '}' for role in get_player_valid_placeholders()]

        if self.scorer_player is not None and not self.scorer_player in valid_player_placeholders:
            raise ValueError(f"Invalid goal_player placeholder: {self.scorer_player}")
        if self.assist_player is not None and self.assist_player not in valid_player_placeholders:
            raise ValueError(f"Invalid assist_player placeholder: {self.assist_player}")
        for player, score in self.player_evaluation.items():
            if player not in valid_player_placeholders:
                raise ValueError(f"Invalid player evaluation placeholder: {player}")
            if not -3 <= score <= 3:
                raise ValueError(f"Invalid player evaluation mark: {score}")




@dataclass
class ActionRequest:
    action_type : ActionType
    use_var : bool


def get_player_valid_placeholders():
    atk = [f'atk_{i + 1}' for i in range(4)] + ['atk_goalie']
    dfn = [f'def_{i + 1}' for i in range(4)] + ['def_goalie']  

    pl = atk + dfn
    return pl

def get_all_valid_placeholders():
    pl = get_player_valid_placeholders()
    others = ['referee', 'stadium', 'atk_team_name', 'def_team_name']

    return pl + others

def extract_keys_from_format_string(format_str) -> list[str]:
    formatter = string.Formatter()
    keys = [field_name for _, field_name, _, _ in formatter.parse(format_str) if field_name]
    return keys

def find_invalid_keys(format_str : str, assignment_keys : Container[str]) -> list[str]:
    invalid_keys : list[str] = []
    keys = extract_keys_from_format_string(format_str)
    for key in keys:
        if key not in assignment_keys:
            invalid_keys.append(key)
    
    return invalid_keys
