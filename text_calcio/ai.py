from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Container, Literal, Optional
from openai import BaseModel, OpenAI
import string


AI_SYSTEM_PROMPT_BEGIN = """
# Introduction

You are a bot that narrates a football game like an Italian sportcaster, you must speak Italian.
You mainly will return a list of phrases that narrate sequentially the course of a single action.

# Player Variables

When you write the sentences you use the placeholders {atk_1} {atk_2} {atk_3} {atk_4} {atk_goalie} for 
the name of the players of the attacking team.
Similarly you will use {def_1} {def_2} {def_3} {def_4} {def_goalie} as placeholders of the name
of the players of the defending team. 

# Support Variables

{atk_team_name} and {def_team_name} contains the name of the attacking and defending teams.
{referee} is a variable containing the name of the referee, and {stadium} contains the name of the arena
where the match is played. It is not necessary to mention any support variables during the narration, 
but you can use them as you wish to make the narration better.

# Task

Generate a list of strings that narrates an action, assume that the game is already started so do not
introduce the stadium. The list of strings must strictly contain only the placeholders I told you before.
The action must be between 10 and 20 phrases long.

# Outcome of the Action
"""

GOAL_PROMPT_NO_VAR = """
The action concludes with a goal of the attacking team.
"""

GOAL_PROMPT_VAR = """
The action concludes with a goal of the attacking team. After the goal the referee checks the VAR and
confirms that the goal happened regularly awarding the goal to the attacking team.
A GOAL MUST BE AWARDED IN THIS NARRATION.
"""

NO_GOAL_PROMPT_NO_VAR = """
The action concludes with a failed action of the attacking team. After this action make sure, narrating it in maximum 1-2 phrases,
the possesion of the ball goes to the defending team (example: with a free kick in case of foul,with a throw-in,
goal kick, interception or ball recovery, or anthing else it comes to your mind).
"""

NO_GOAL_PROMPT_VAR = """
The action concludes with a goal, however the referee goes to check the VAR and decides that the goal is not
valid. NO GOAL MUST BE AWARDED IN THIS NARRATION.
"""

PENALTY_PROMPT_NO_VAR ="""
The action concludes with a penalty assigned to the attacking team. Stop the narration before
the penalty is kicked.
"""

PENALTY_PROMPT_VAR ="""
The action concludes with a penalty assigned to the attacking team after the referee checked the VAR. Stop the narration before
the penalty is kicked.
"""

CONCLUDING_PROMPT = """ 

# Structured Response fields

All the fields of the response 
must contain only strictly the placeholders for the player names of one of the two teams. If there is nothing that
can fit a field leave that field null.

# Concluding Remarks

Remember that this narration that you are generating is part of a game, you do not have the full context of the game so
don't make assumptions on information that you do not have (such as the score or how well a player is going)
"""

def build_prompt(outcome : Literal["goal", "no_goal", "penalty"], var_check : bool):
    prompt = AI_SYSTEM_PROMPT_BEGIN
    prompt += '\n'
    if outcome == "goal" and var_check:
        prompt += GOAL_PROMPT_VAR
    elif outcome == "goal" and not var_check:
        prompt += GOAL_PROMPT_NO_VAR

    elif outcome == "no_goal" and var_check:
        prompt += NO_GOAL_PROMPT_VAR
    elif outcome == "no_goal" and not var_check:
        prompt += NO_GOAL_PROMPT_NO_VAR
    elif outcome == "penalty" and var_check:
        prompt += PENALTY_PROMPT_VAR
    elif outcome == "penalty" and not var_check:
        prompt += PENALTY_PROMPT_NO_VAR
    
    prompt += CONCLUDING_PROMPT

    return prompt

    
class ActionResponse(BaseModel):
    phrases : list[str]
    best_player : Optional[str]
    worst_player : Optional[str]
    scorer_player : Optional[str]
    assist_player : Optional[str]

    class Config:
        extra = 'forbid'

class ActionGenerator(ABC):
    
    @abstractmethod
    def generate(self, action_ending : Literal["goal", "no_goal", "penalty"], var_check : bool) -> ActionResponse:
        pass

class AIActionGenerator(ActionGenerator):


    def __init__(self, ai_client : OpenAI) -> None:
        self.ai_client = ai_client

    def generate(self, action_ending : Literal["goal", "no_goal", "penalty"], var_check : bool) -> ActionResponse:
        prompt = build_prompt(action_ending, var_check)
        result = self.ai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format=ActionResponse,
        )

        api_response = result.choices[0].message
        if api_response.refusal:
            raise RuntimeError(f'Api response refused: {api_response.refusal}')
        else:
            return api_response.parsed # type: ignore
        


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

