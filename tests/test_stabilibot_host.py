"""Load the real host offline: no Discord login, cron jobs, HTTP or API listener."""
import os
import logging
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

import discord
from discord.ext import tasks

from trial_board_bot.bot import Config
from trial_board_bot.store import Store

ROOT=Path(__file__).resolve().parents[1]


class StabilibotHostTests(unittest.IsolatedAsyncioTestCase):
    async def load_host(self,enabled):
        root=ROOT/'work/test-runs'
        root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            cfg=Config(True,1,100,200,[300],[400],database=str(Path(temp)/'trials.sqlite3'))
            original=Path.cwd()
            sys.path.insert(0,str(ROOT))
            try:
                os.chdir(temp)
                with patch.dict(os.environ,{'GUILD_ID':'1','TOKEN':'offline-test-token',
                    'TRIAL_BOARD_ENABLED':str(enabled).lower(),'API_TOKEN':'offline-test-key'}), \
                    patch('dotenv.load_dotenv'),patch.object(discord.Bot,'run') as run, \
                    patch.object(tasks.Loop,'start') as start, \
                    patch('logging.basicConfig'),patch('logging.FileHandler',return_value=logging.NullHandler()), \
                    patch.object(Config,'read',return_value=cfg) as read:
                    namespace=runpy.run_path(str(ROOT/'main.py'),run_name='__offline_host_test__')
                    bot=namespace['bot']
                    run.assert_called_once_with('offline-test-token')
                    # Only the two existing cron constructors attempted to start tasks;
                    # the trial worker waits for a validated Discord on_ready event.
                    self.assertEqual(start.call_count,2)
                    self.assertEqual(read.call_count,int(enabled))
                names={c.name for c in bot.pending_application_commands}
                self.assertTrue({'apply','gear','namechange','roll','stats','register_account'} <= names)
                self.assertEqual(bool(bot.get_cog('TrialBoard')),enabled)
                self.assertEqual({'trial','board'} <= names,enabled)
                self.assertEqual(bot.on_ready.__func__,namespace['Stabilibot'].on_ready)
                self.assertEqual(bot.on_application_command_error.__func__,
                                 namespace['Stabilibot'].on_application_command_error)
                self.assertIsNotNone(bot.get_cog('Api'))
                self.assertIsNotNone(bot.get_cog('EventUser'))
                self.assertTrue(bot.intents.members)
                self.assertTrue(bot.intents.message_content)
                from api.v1 import V1
                routes={route.path for route in V1(bot).router.routes}
                self.assertIn('/trials/start',routes)
                self.assertIn('/{user_id}/roles/add',routes)
                if enabled:
                    self.assertTrue(bot.get_cog('TrialBoard').store.paused())
                    bot.remove_cog('TrialBoard')
                await bot.close()
                return names
            finally:
                os.chdir(original)
                sys.path.remove(str(ROOT))

    async def test_default_disabled_preserves_existing_host(self):
        await self.load_host(False)

    async def test_enabled_adds_only_trial_command_groups(self):
        disabled=await self.load_host(False)
        enabled=await self.load_host(True)
        self.assertEqual(enabled-disabled,{'trial','board'})
        self.assertFalse(disabled-enabled)


if __name__=='__main__':
    unittest.main()
