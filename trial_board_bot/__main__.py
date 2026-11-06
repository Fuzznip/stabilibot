"""Run offline checks by default; --live and enabled=true are both required to log in."""
import argparse
import asyncio
import logging
import os
import sys

from .bot import Config, build_bot
from .store import RuleError, Store


def main():
    parser=argparse.ArgumentParser(description='Stability trial coordination bot')
    parser.add_argument('--config',default='private/trial-board.toml')
    parser.add_argument('--live',action='store_true',help='Connect the approved bot to Discord')
    parser.add_argument('--sync',action='store_true',help='Explicitly register commands in the configured guild')
    args=parser.parse_args()
    try:
        cfg=Config.read(args.config)
        if not args.live:
            print('Configuration parsed. Offline only; no Discord login or command registration.')
            return
        if not cfg.enabled:
            raise RuleError('Set enabled=true only after approving the channels and workflow.')
        token=os.environ.get('TRIAL_BOT_TOKEN')
        if not token:
            raise RuleError('Set TRIAL_BOT_TOKEN in the hosting secret store. Never commit it.')
        store=Store(cfg.database,shared_pool=cfg.shared_pool)
        bot,runtime=build_bot(cfg,store)
        async def run():
            if args.sync:
                @bot.listen('on_ready')
                async def register_commands():
                    await bot.sync_commands(guild_ids=[cfg.guild_id])
            try:
                await bot.start(token)
            finally:
                if runtime.dispatch.is_running():
                    runtime.dispatch.cancel()
                await bot.close()
        logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
        asyncio.run(run())
    except RuleError as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)


if __name__=='__main__':
    main()
