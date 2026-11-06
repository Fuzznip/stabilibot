"""Trial coordination is opt-in; it shares Stabilibot's existing bot identity."""
from trial_board_bot.integration import load_trial_board


def setup(bot):
    return load_trial_board(bot)
