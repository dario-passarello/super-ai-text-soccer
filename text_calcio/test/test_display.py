from text_calcio.state.match import Match, MatchAction, Penalty

from pydantic import BaseModel
from openai import OpenAI

from tqdm import tqdm

from collections import defaultdict

client = OpenAI()


class PlayerEvaluation(BaseModel):
    player_placeholder: str
    evaluation: int

    class Config:
        extra = "forbid"


class CommentedAction(BaseModel):
    commented_action: list[str]
    player_evaluations: list[PlayerEvaluation]
    summary: str

    class Config:
        extra = "forbid"


SYSTEM_PROMPT = """
<personality>
- You are a passionate Italian sportscaster.
- You are knowledgeable about the game and the teams.
- You are engaging and entertaining.
- You are unbiased and fair.
- You know the state of the game and the score. Use this information to make the narration exciting, make jokes, and engage the audience.
- You describe each action in detail, with 15 to 20 phrases per action.
- You don't repeat yourself when describing actions, both in structure and content.
- Don't always mention time, stadium, or referee, to avoid being repetitive.
- You strictly speak Italian.
</personality>

<available-placeholders>
- Attacking team: {atk_1}, {atk_2}, {atk_3}, {atk_4}, {atk_goalkeeper}
- Defending team: {def_1}, {def_2}, {def_3}, {def_4}, {def_goalkeeper}
- Support variables (optional use): {atk_team_name}, {def_team_name}, {referee}, {stadium}
</available-placeholders>

<task>
- Generate 15-20 phrases per action
- Include 1-2 phrases on how the action began.
- Describe the action in detail, including the players involved, the action type, and the outcome.
- Use only the specified placeholders. 
- Assume the game has already started.
- Provide a short summary of the action.
- Evaluate the performance of the players involved in the action.
- Each evaluation should be a score from -3 to 3. E.g. 3 for a great performance, -3 for a poor performance. 0 if the player was not involved or had no impact.
</task>
"""

DESCRIBE_ACTIONS_PROMPT = """
Score: %s
Minute: %s
Phase: %s
Previous actions:
<list-of-old-actions>
%s
</list-of-old-actions>

Describe the next actions:
<list-of-actions>
%s
</list-of-actions>
"""


class TestDisplay:
    current_minute = 0
    commented_actions: list[list[str]] = []
    summaries: list[str] = []
    player_evaluations: dict[str, int] = defaultdict(int)

    def __init__(self):
        pass

    async def display_match(self, match: Match):
        # print from current_minute to the current minute of the match, then increment the current minute
        actions = match.get_actions_in_time_range(
            self.current_minute, match.get_absolute_minute()
        )

        def format_penalty(action: MatchAction, penalty: Penalty):
            player_kicking = action.get_placeholder_from_name(penalty.player_kicking)
            goalkeeper = action.get_placeholder_from_name(penalty.goalkeeper)
            kick_direction = penalty.kick_direction
            dive_direction = penalty.dive_direction
            is_goal = penalty.is_goal
            is_out = penalty.is_out

            return f"""
            Penalty Details:
            Player kicking: {player_kicking}
            Goalkeeper: {goalkeeper}
            Kick direction: {kick_direction}
            Dive direction: {dive_direction}
            Is goal: {is_goal}
            Is out: {is_out}
            """

        def format_action(action: MatchAction):
            action_type_string = f"Action type: {action.type}"

            player_scored_string = (
                f"Player that scored: {action.get_placeholder_from_name(action.goal_player)}"  # type: ignore
                if action.is_goal()
                else ""
            )

            player_assist_string = (
                f"Player that assisted: {action.get_placeholder_from_name(action.assist_player)}"
                if action.assist_player
                else ""
            )

            penalty_string = (
                f"Penalty Details: {format_penalty(action, action.penalty)}"
                if action.penalty
                else ""
            )

            return "\n".join(
                s
                for s in [
                    action_type_string,
                    player_scored_string,
                    player_assist_string,
                    penalty_string,
                ]
                if s
            )

        for action in tqdm(actions):
            action_minute = action.time.absolute_minute()
            action_phase = action.time.phase

            describe_action_prompt = DESCRIBE_ACTIONS_PROMPT % (
                match.get_score_at(action_minute),
                action_minute,
                action_phase,
                "\n".join(self.summaries),
                format_action(action),
            )

            completion = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": describe_action_prompt},
                ],
                response_format=CommentedAction,
            )

            response = completion.choices[0].message.parsed

            if response is None:
                raise RuntimeError("Cannot parse API response")

            self.commented_actions += [response.commented_action]
            self.summaries += [response.summary]

            # sum up all the evaluations per each player
            for player_eval in response.player_evaluations:
                self.player_evaluations[player_eval.player_placeholder] = (
                    self.player_evaluations.get(player_eval.player_placeholder, 0)
                    + player_eval.evaluation
                )

            print("Player evaluations:")

            for player, evaluation in self.player_evaluations.items():
                print(f"{player}: {evaluation}")

            print(
                "\n".join(self.replace_placeholders(action, response.commented_action)),
                end="\n\n\n",
            )

        input("Press enter to continue")

        for commented_action in self.commented_actions:
            print("Summaries:")
            print("\n".join(self.summaries), end="\n\n\n")

            print("Action:")
            print("\n".join(commented_action), end="\n\n\n")

        self.current_minute = match.get_absolute_minute() + 1

    def replace_placeholders(self, action: MatchAction, commented_action: list[str]):
        return [
            ca.format(**action.placeholders_to_names_map()) for ca in commented_action
        ]
