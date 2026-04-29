"""
Thin adapter that wraps the prediction FunctionTools into a QueryEngine
so the RouterQueryEngine can treat it like the other tools.

The LLM is asked to parse the user's intent (which prediction + which params),
call the right function, and return a formatted answer.
"""
import json
from llama_index.core.base.base_query_engine import BaseQueryEngine
from llama_index.core.callbacks import CallbackManager
from llama_index.core.schema import QueryBundle
from llama_index.core.base.response.schema import Response
from ml.predictor import predict_win_probability, forecast_player_performance

PREDICTION_DISPATCH_PROMPT = """You are a sports analytics assistant with two prediction tools.

Tool A — win_probability(home_team, away_team):
  Use when the question is about which team will win or their chances.
  Example: "Warriors vs Celtics" → home_team="Golden State Warriors", away_team="Boston Celtics"

Tool B — player_forecast(player_name, metric, periods):
  Use when the question is about a player's future stats.
  metric must be one of: pts, ast, reb
  periods = number of future games (default 10)
  Example: "LeBron scoring next 5 games" → player_name="LeBron James", metric="pts", periods=5

Question: {question}

Respond with JSON only (no explanation):
For win probability: {{"tool": "win_probability", "home_team": "...", "away_team": "..."}}
For player forecast: {{"tool": "player_forecast", "player_name": "...", "metric": "pts", "periods": 10}}
"""

PREDICTION_SYNTHESIS_PROMPT = """Question: {question}

Prediction result:
{result}

Provide a clear, conversational answer based on this prediction.
Explain what the numbers mean in plain English.
Mention any caveats (e.g., model is trained on historical data, injuries not accounted for).
"""


class PredictionQueryEngine(BaseQueryEngine):
    def __init__(self, llm):
        self._llm = llm
        super().__init__(callback_manager=CallbackManager())

    def _get_prompt_modules(self):
        return {}

    def _query(self, query_bundle: QueryBundle) -> Response:
        question = query_bundle.query_str

        # Step 1: parse intent
        dispatch_prompt = PREDICTION_DISPATCH_PROMPT.format(question=question)
        raw = str(self._llm.complete(dispatch_prompt)).strip()

        # Extract JSON
        try:
            # Handle markdown fences
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            intent = json.loads(raw)
        except Exception:
            return Response(
                response=(
                    "I couldn't parse the prediction request. "
                    "Try: 'Predict win probability: Warriors vs Celtics' or "
                    "'Forecast LeBron's points for 10 games'."
                ),
                source_nodes=[],
            )

        # Step 2: call the right predictor
        tool = intent.get("tool", "")
        try:
            if tool == "win_probability":
                result = predict_win_probability(
                    home_team=intent.get("home_team", ""),
                    away_team=intent.get("away_team", ""),
                )
            elif tool == "player_forecast":
                result = forecast_player_performance(
                    player_name=intent.get("player_name", ""),
                    metric=intent.get("metric", "pts"),
                    periods=int(intent.get("periods", 10)),
                )
            else:
                return Response(
                    response="Could not determine prediction type. Please specify teams or a player name.",
                    source_nodes=[],
                )
        except Exception as e:
            return Response(response=f"Prediction error: {e}", source_nodes=[])

        if "error" in result:
            return Response(response=result["error"], source_nodes=[])

        # Step 3: synthesise natural language response
        result_str = json.dumps(result, indent=2)
        synth_prompt = PREDICTION_SYNTHESIS_PROMPT.format(
            question=question, result=result_str
        )
        answer = str(self._llm.complete(synth_prompt))
        return Response(response=answer, source_nodes=[])

    async def _aquery(self, query_bundle: QueryBundle) -> Response:
        return self._query(query_bundle)
