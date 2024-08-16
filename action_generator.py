



from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from text_calcio.ai import AIActionGenerator
from text_calcio.match_state import Action


def generate_actions_ai(n_actions_per_type : int):

    load_dotenv()


    ai_client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    generator = AIActionGenerator(ai_client)

    for action in range(n_actions_per_type): 
        with ThreadPoolExecutor(8) as executor:
            for ending in ["goal", "no_goal", "penalty", "own_goal"]:
                for is_var in [False, True]:
                    action = generator.generate(ending, is_var)
                    
