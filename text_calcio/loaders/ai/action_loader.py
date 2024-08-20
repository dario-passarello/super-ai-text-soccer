from openai import AsyncOpenAI
from text_calcio.loaders.action import ActionBlueprint, ActionRequest, AsyncActionLoader
from text_calcio.loaders.ai.api_models import ActionResponse
from text_calcio.loaders.ai.prompt import build_prompt


class AsyncAIActionLoader(AsyncActionLoader):
    def __init__(self, ai_client: AsyncOpenAI) -> None:
        self.ai_client = ai_client

    async def generate(self, request: ActionRequest) -> ActionBlueprint:
        prompt = build_prompt(request)
        result = await self.ai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            response_format=ActionResponse,
        )

        api_response = result.choices[0].message
        if api_response.refusal:
            raise RuntimeError(f"API response refused: {api_response.refusal}")

        action_response = api_response.parsed

        if action_response is None:
            raise RuntimeError("Cannot parse API response")

        evaluations = {
            evl.player_placeholder: evl.evaluation
            for evl in action_response.player_evaluation
        }
        action_schema = ActionBlueprint(
            request.action_type,
            request.use_var,
            action_response.phrases,
            evaluations,
            action_response.scorer_player,
            action_response.assist_player,
        )
        return action_schema
