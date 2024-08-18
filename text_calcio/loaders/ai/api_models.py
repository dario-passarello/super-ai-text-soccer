from typing import Optional
from openai import BaseModel


class PlayerEvaluation(BaseModel):
    player_placeholder : str
    evaluation : int

    class Config: # type: ignore
        extra = 'forbid'

  
class ActionResponse(BaseModel):
    phrases : list[str]
    player_evaluation : list[PlayerEvaluation]
    scorer_player : Optional[str]
    assist_player : Optional[str]

    class Config: # type: ignore
        extra = 'forbid'

