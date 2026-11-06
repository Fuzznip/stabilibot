"""Offline integration tests for an existing Pycord bot and website handoff."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from trial_board_bot.client import RuleError

HAS_DISCORD=importlib.util.find_spec('discord') is not None
HAS_WEB=all(importlib.util.find_spec(m) is not None for m in ('fastapi','httpx'))
if HAS_DISCORD:
    import discord
    from discord.ext import commands
    from trial_board_bot.bot import Config, attach_to_bot
    from trial_board_bot.integration import load_trial_board
@unittest.skipUnless(HAS_DISCORD,'Install Pycord to test the cog integration')
class CogIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root=Path(__file__).resolve().parents[1]/'work/test-runs'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.client=SimpleNamespace(call=AsyncMock())
        self.cfg=Config(True,1,100,200,[300],[400])
        self.bot=commands.Bot(command_prefix='!',intents=discord.Intents.none(),auto_sync_commands=False)
        @self.bot.slash_command(name='apply',guild_ids=[1],description='Existing application command')
        async def apply(ctx):
            await ctx.respond('Existing behavior',ephemeral=True)
        self.apply=apply
        @self.bot.event
        async def on_application_command_error(ctx,error):
            pass
        self.original_error=self.bot.on_application_command_error
        self.original_ready=getattr(self.bot,'on_ready',None)

    async def asyncTearDown(self):
        if self.bot.get_cog('TrialBoard'):
            self.bot.remove_cog('TrialBoard')
        await self.bot.close()
        self.temp.cleanup()

    async def test_attach_preserves_existing_handlers_commands_and_settings(self):
        mentions=self.bot.allowed_mentions
        runtime=attach_to_bot(self.bot,self.cfg,self.client)
        self.assertIs(self.bot.get_cog('TrialBoard'),runtime)
        self.assertIs(self.bot.on_application_command_error,self.original_error)
        self.assertIs(getattr(self.bot,'on_ready',None),self.original_ready)
        self.assertIs(self.bot.allowed_mentions,mentions)
        self.assertEqual({c.name for c in self.bot.pending_application_commands},{'apply','trial','board'})
        for group in runtime.command_groups:
            self.assertTrue(all(c.has_error_handler() for c in group.subcommands))
        self.assertFalse(runtime.dispatch.is_running())

    async def test_unload_removes_only_its_commands_and_stops_views(self):
        runtime=attach_to_bot(self.bot,self.cfg,self.client)
        view=runtime.view({'id':1,'revision':1})
        self.bot.add_view(view)
        self.bot.remove_cog('TrialBoard')
        self.assertFalse(runtime.loaded)
        self.assertTrue(view.is_finished())
        self.assertEqual({c.name for c in self.bot.pending_application_commands},{'apply'})

    async def test_duplicate_install_does_not_remove_existing_commands(self):
        attach_to_bot(self.bot,self.cfg,self.client)
        with self.assertRaises(RuleError): attach_to_bot(self.bot,self.cfg,self.client)
        self.assertEqual({c.name for c in self.bot.pending_application_commands},{'apply','trial','board'})

    async def test_disabled_loader_does_not_read_config_or_initialize_database(self):
        with patch.dict(os.environ,{'TRIAL_BOARD_ENABLED':'false'}),patch('trial_board_bot.bot.Config.read') as read:
            self.assertIsNone(load_trial_board(self.bot))
            read.assert_not_called()
        self.assertEqual({c.name for c in self.bot.pending_application_commands},{'apply'})

    async def test_bad_or_wrong_guild_config_does_not_break_host_bot(self):
        with patch.dict(os.environ,{'TRIAL_BOARD_ENABLED':'true','GUILD_ID':'2'}),patch('trial_board_bot.bot.Config.read',return_value=self.cfg):
            self.assertIsNone(load_trial_board(self.bot))
        self.assertEqual({c.name for c in self.bot.pending_application_commands},{'apply'})

    async def test_bad_channel_permissions_pause_only_trial_feature(self):
        runtime=attach_to_bot(self.bot,self.cfg,self.client)
        runtime.validate_channels=AsyncMock(side_effect=RuleError('Invalid channel access'))
        with patch.object(self.bot,'close',new_callable=AsyncMock) as close, patch.object(runtime.dispatch,'start') as start:
            await runtime.on_ready()
            close.assert_not_awaited()
            start.assert_called_once()
        self.client.call.assert_awaited_with('suspend')
        self.assertFalse(runtime.dispatch.is_running())



if __name__=='__main__':unittest.main()
