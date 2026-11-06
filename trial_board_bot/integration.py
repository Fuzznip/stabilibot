"""Opt-in loader for Stabilibot. Importing this module never reads secrets or logs in."""
import logging
import os

log=logging.getLogger(__name__)


def load_trial_board(bot):
    # Check the switch before importing the adapter, opening SQLite or registering commands.
    if os.getenv('TRIAL_BOARD_ENABLED','false').strip().lower() != 'true':
        return None
    existing=bot.get_cog('TrialBoard')
    if existing is not None:
        return existing
    from .bot import Config, attach_to_bot
    from .client import BackendClient
    try:
        cfg=Config.read(os.getenv('TRIAL_BOARD_CONFIG','private/trial-board.toml'))
        if not cfg.enabled:
            log.info('Trial board disabled in config; existing Stabilibot continues normally.')
            return None
        if cfg.guild_id != int(os.getenv('GUILD_ID','0')):
            raise ValueError('Trial configuration must use the existing Stabilibot guild.')
        return attach_to_bot(bot,cfg,BackendClient(cfg.guild_id))
    except Exception as error:
        # A trial config problem must not take down unrelated clan functions.
        # Do not log private configuration values or exception payloads.
        log.error('Trial board was not loaded (%s). Check its private config.',type(error).__name__)
        return None
