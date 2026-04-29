"""
Prediction Tool — wraps ml/predictor.py as a LlamaIndex FunctionTool.
"""
import json
from llama_index.core.tools import FunctionTool
from ml.predictor import predict_win_probability, forecast_player_performance


def win_probability_tool_fn(home_team: str, away_team: str,
                             home_rest_days: int = 2, away_rest_days: int = 2) -> str:
    """
    Predict the probability that home_team beats away_team.
    Use when the user asks about chances, likelihood, or win probability between two teams.

    Args:
        home_team:      Name or abbreviation of the home team
        away_team:      Name or abbreviation of the away team
        home_rest_days: Days since home team's last game (default 2)
        away_rest_days: Days since away team's last game (default 2)
    """
    result = predict_win_probability(home_team, away_team, home_rest_days, away_rest_days)
    return json.dumps(result, indent=2)


def player_forecast_tool_fn(player_name: str, metric: str = "pts", periods: int = 10) -> str:
    """
    Forecast a player's performance over the next N games using Prophet time-series model.
    Use when the user asks to predict or forecast a player's stats.

    Args:
        player_name: Full or partial player name
        metric:      One of 'pts' (points), 'ast' (assists), 'reb' (rebounds)
        periods:     Number of future games to forecast (default 10)
    """
    result = forecast_player_performance(player_name, metric, periods)
    return json.dumps(result, indent=2)


def build_prediction_tools() -> list[FunctionTool]:
    return [
        FunctionTool.from_defaults(
            fn=win_probability_tool_fn,
            name="win_probability",
            description=(
                "Predict win probability between two NBA teams. "
                "Use for questions like 'Who will win?', 'What are the chances?', "
                "'Which team is favored?'. Requires home_team and away_team."
            ),
        ),
        FunctionTool.from_defaults(
            fn=player_forecast_tool_fn,
            name="player_forecast",
            description=(
                "Forecast a player's future game statistics (pts/ast/reb) "
                "using a time-series model. Use for questions like "
                "'How will LeBron perform?', 'Predict Curry's scoring'. "
                "Requires player_name. Optionally: metric, periods."
            ),
        ),
    ]
