from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from typing import Container, Literal, Optional
from openai import AsyncOpenAI, BaseModel, OpenAI
import string

from text_calcio.action import ActionBlueprint, ActionType


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
The action must be between 15 and 20 phrases long. Dedicate at least 1 or 2 phrases to narrate how the action began.

# Outcome of the Action
"""

GOAL_PROMPT_NO_VAR = """
The action concludes with a goal of the attacking team.
"""

GOAL_PROMPT_VAR = """
The action concludes with a goal of the attacking team. The referees goes to the replay at the VAR, and
confirms the goal. THE NARRATOR MUST SAY THAT THE GOAL WAS CONFIRMED.
"""

OWN_GOAL_PROMPT = """
The action concludes with an own goal, made by a player of the defending team in their goal, awarding the attacking team a goal.
In the scorer_player field you will put the name of the of the player of the defending team that made the own goal,
and set null in the assist_player.
"""

NO_GOAL_PROMPT_NO_VAR = """
The action concludes with a failed action of the attacking team. After this action make sure, narrating it in maximum 1-2 phrases,
the possesion of the ball goes to the defending team (example: with a free kick in case of foul,with a throw-in,
goal kick, interception or ball recovery, or anthing else it comes to your mind).
"""

NO_GOAL_PROMPT_VAR = """
The action concludes with a goal, however the referee goes to check the VAR and decides that the goal is not
valid. NO GOALS MUST BE AWARDED IN THIS NARRATION. The scorer field must be left at null, like in the case when a goal 
was not scored.
"""

PENALTY_PROMPT_NO_VAR ="""
The action concludes with a penalty assigned to the attacking team. Stop the narration before
the penalty is kicked. You do not know who is the player of the attacking team that is going to kick the penalty.
"""

PENALTY_PROMPT_VAR ="""
The action concludes with a penalty assigned to the attacking team after the referee checked the VAR. Stop the narration before
the penalty is kicked. You do not know who is the player  of the attacking team that is going to kick the penalty.
"""

CONCLUDING_PROMPT = """ 

# Structured Response fields

The scorer_player and the assist_player fields in the response 
must contain only strictly the placeholders for the player names of one of the two teams. The first field contains the name 
of the scorer player and the second may be a player that did the assist. In case of no goal or penalty leave those field null.

The player_evaluation field is a list of objects containg two fields: player_evalutaion contains the complete placeholder (that includes the {}) of the player and evaluation an integer mark
from -3 to 3 evaluating the performance of that player in the action. A +3 is the best mark you can give for outstanding performance
while -3 is for very important errors, 0 is neutral. You can omit players only if they did not take part in the action (i.e. not present in the narration).

# Concluding Remarks

Remember that this narration that you are generating is part of a game, you do not have the full context of the game so
don't make assumptions on information that you do not have (such as the score or how well a player is going)
"""

def build_prompt(outcome : Literal["goal", "own_goal", "no_goal", "penalty"], var_check : bool):
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
    elif outcome == "own_goal":
        prompt += OWN_GOAL_PROMPT
    elif outcome == "penalty" and var_check:
        prompt += PENALTY_PROMPT_VAR
    elif outcome == "penalty" and not var_check:
        prompt += PENALTY_PROMPT_NO_VAR
    
    prompt += CONCLUDING_PROMPT

    return prompt


class PlayerEvaluation(BaseModel):
    player_placeholder : str
    evaluation : int

    class Config:
        extra = 'forbid'

  
class ActionResponse(BaseModel):
    phrases : list[str]
    player_evaluation : list[PlayerEvaluation]
    scorer_player : Optional[str]
    assist_player : Optional[str]

    class Config:
        extra = 'forbid'


class AsyncActionGenerator(ABC):
    
    @abstractmethod
    async def generate(self, action_ending : ActionType, var_check : bool) -> ActionBlueprint:
        pass

class AsyncAIActionGenerator(AsyncActionGenerator):
    def __init__(self, ai_client : AsyncOpenAI) -> None:
        self.ai_client = ai_client

    async def generate(self, action_ending : ActionType, var_check : bool) -> ActionBlueprint:
        prompt = build_prompt(action_ending, var_check)
        result = await self.ai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format=ActionResponse,
        )

        api_response = result.choices[0].message
        if api_response.refusal:
            raise RuntimeError(f'API response refused: {api_response.refusal}')
        
        action_response = api_response.parsed

        if action_response is None:        
            raise RuntimeError(f'Cannot parse API response')

        evaluations = {
            evl.player_placeholder: evl.evaluation for evl in action_response.player_evaluation
        }
        action_schema = ActionBlueprint(
            action_ending, var_check, action_response.phrases, evaluations, action_response.scorer_player, action_response.assist_player
        )
        return action_schema

class AsyncActionProducer():

    MAX_RETRIES = 3

    def __init__(self, generator : AsyncActionGenerator, queue : asyncio.Queue[ActionBlueprint], demand_queue : asyncio.Queue[list[tuple[ActionType, bool]]]) -> None:
        self.generator = generator
        self.queue = queue
        self.demand_queue = demand_queue

    async def produce(self):
        while True:
            desired_items = await self.demand_queue.get()
            if desired_items is None:
                break

            for action_type, is_var in desired_items:
                for attempt in range(self.MAX_RETRIES):
                    try:
                        generated_blueprint = await self.generator.generate(action_type, is_var)
                        generated_blueprint.validate()
                        await self.queue.put(generated_blueprint)
                        break
                    except Exception as e:
                        if attempt < self.MAX_RETRIES - 1:
                            pass
                        else:
                            print("Max retries reached. Operation failed.")
                            raise  # Re-raise the exception if max retries reached




