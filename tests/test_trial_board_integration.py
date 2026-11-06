"""Offline integration tests for an existing Pycord bot and website handoff."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from trial_board_bot.store import Store, RuleError

HAS_DISCORD=importlib.util.find_spec('discord') is not None
HAS_WEB=all(importlib.util.find_spec(m) is not None for m in ('fastapi','httpx'))
if HAS_DISCORD:
    import discord
    from discord.ext import commands
    from trial_board_bot.bot import Config, attach_to_bot
    from trial_board_bot.integration import load_trial_board
if HAS_WEB:
    import httpx
    from fastapi import FastAPI, APIRouter
    from trial_board_bot.web import add_trial_routes


@unittest.skipUnless(HAS_DISCORD,'Install Pycord to test the cog integration')
class CogIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root=Path(__file__).resolve().parents[1]/'work/test-runs'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.store=Store(Path(self.temp.name)/'trials.sqlite3')
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
        runtime=attach_to_bot(self.bot,self.cfg,self.store)
        self.assertIs(self.bot.get_cog('TrialBoard'),runtime)
        self.assertIs(self.bot.on_application_command_error,self.original_error)
        self.assertIs(getattr(self.bot,'on_ready',None),self.original_ready)
        self.assertIs(self.bot.allowed_mentions,mentions)
        self.assertEqual({c.name for c in self.bot.pending_application_commands},{'apply','trial','board'})
        for group in runtime.command_groups:
            self.assertTrue(all(c.has_error_handler() for c in group.subcommands))
        self.assertFalse(runtime.dispatch.is_running())

    async def test_unload_removes_only_its_commands_and_stops_views(self):
        runtime=attach_to_bot(self.bot,self.cfg,self.store)
        view=runtime.view({'id':1,'revision':1})
        self.bot.add_view(view)
        self.bot.remove_cog('TrialBoard')
        self.assertFalse(runtime.loaded)
        self.assertTrue(view.is_finished())
        self.assertEqual({c.name for c in self.bot.pending_application_commands},{'apply'})

    async def test_duplicate_install_does_not_remove_existing_commands(self):
        attach_to_bot(self.bot,self.cfg,self.store)
        with self.assertRaises(RuleError): attach_to_bot(self.bot,self.cfg,self.store)
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
        runtime=attach_to_bot(self.bot,self.cfg,self.store)
        runtime.validate_channels=AsyncMock(side_effect=RuleError('Invalid channel access'))
        with patch.object(self.bot,'close',new_callable=AsyncMock) as close:
            await runtime.on_ready()
            close.assert_not_awaited()
        self.assertTrue(self.store.paused())
        self.assertFalse(runtime.dispatch.is_running())


@unittest.skipUnless(HAS_WEB,'Install FastAPI and httpx to test the website handoff')
class WebsiteHandoffTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root=Path(__file__).resolve().parents[1]/'work/test-runs'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.store=Store(Path(self.temp.name)/'trials.sqlite3')
        self.store.pause(False,99)
        self.runtime=SimpleNamespace(loaded=True,ready=True,store=self.store,
            cfg=SimpleNamespace(guild_id=1,queue_channel_id=100,staff_channel_id=200,trial_days=14),
            validate_channels=AsyncMock(),app_channel=AsyncMock())
        self.member=SimpleNamespace(id=123,bot=False)
        self.guild=SimpleNamespace(get_member=lambda ident:self.member,fetch_member=AsyncMock())
        self.bot=SimpleNamespace(get_cog=lambda name:self.runtime,get_guild=lambda ident:self.guild)
        self.app=FastAPI()
        router=APIRouter()
        add_trial_routes(router,self.bot)
        self.app.include_router(router)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://offline.test')
        self.env=patch.dict(os.environ,{'API_TOKEN':'test-only-api-key'})
        self.env.start()
        self.payload={'token':'test-only-api-key','request_id':'application:123','applicant_id':123,'application_channel_id':456}

    async def asyncTearDown(self):
        await self.client.aclose()
        self.env.stop()
        self.temp.cleanup()

    async def test_handoff_creates_once_even_after_trial_closed(self):
        first=await self.client.post('/trials/start',json=self.payload)
        self.assertEqual(first.status_code,201)
        ident=first.json()['trial_id']
        second=await self.client.post('/trials/start',json=self.payload)
        self.assertEqual(second.status_code,200)
        self.assertEqual(second.json()['trial_id'],ident)
        self.assertTrue(second.json()['replayed'])
        self.store.close(ident,99,'withdrawn')
        third=await self.client.post('/trials/start',json=self.payload)
        self.assertEqual(third.json()['trial_id'],ident)
        self.assertEqual(len(self.store.list(active=False)),1)

    async def test_missing_or_wrong_api_secret_cannot_create_trial(self):
        for token in ('wrong','unicode-🔑'):
            result=await self.client.post('/trials/start',json={**self.payload,'token':token})
            self.assertEqual(result.status_code,401)
        with patch.dict(os.environ,{'API_TOKEN':''}):
            result=await self.client.post('/trials/start',json=self.payload)
            self.assertEqual(result.status_code,401)
        self.assertFalse(self.store.list())

    async def test_disabled_not_ready_and_paused_return_503(self):
        self.runtime.ready=False
        self.assertEqual((await self.client.post('/trials/start',json=self.payload)).status_code,503)
        self.runtime.ready=True
        self.store.pause(True,99)
        self.assertEqual((await self.client.post('/trials/start',json=self.payload)).status_code,503)
        self.bot.get_cog=lambda name:None
        self.assertEqual((await self.client.post('/trials/start',json=self.payload)).status_code,503)
        self.assertFalse(self.store.list())

    async def test_conflicting_idempotency_payload_rejected(self):
        self.assertEqual((await self.client.post('/trials/start',json=self.payload)).status_code,201)
        result=await self.client.post('/trials/start',json={**self.payload,'minutes':120})
        self.assertEqual(result.status_code,409)
        self.assertEqual(len(self.store.list()),1)

    async def test_permission_failure_and_bad_fields_do_not_open_trial(self):
        self.runtime.app_channel=AsyncMock(side_effect=RuleError('Invalid channel access'))
        self.assertEqual((await self.client.post('/trials/start',json=self.payload)).status_code,409)
        self.assertEqual((await self.client.post('/trials/start',json={**self.payload,'route':'invented'})).status_code,422)
        self.assertEqual((await self.client.post('/trials/start',json={**self.payload,'unexpected':'field'})).status_code,422)
        self.assertFalse(self.store.list())


if __name__=='__main__':
    unittest.main()
