"""Adapter smoke/security tests. Skipped in campaign CI without the optional bot dependency."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

HAS_DISCORD=importlib.util.find_spec('discord') is not None
if HAS_DISCORD:
    import discord
    from trial_board_bot.bot import Config, Runtime, TrialView, build_bot, private_channel
from trial_board_bot.store import RuleError, Store


@unittest.skipUnless(HAS_DISCORD,'Install requirements-trial-board.txt to test the Discord adapter')
class DiscordAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root=Path(__file__).resolve().parents[1]/'work/test-runs'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.store=Store(Path(self.temp.name)/'bot.sqlite3',clock=lambda:1800000000)
        self.cfg=Config(False,1,100,200,[300],[400])
        self.bot,self.runtime=build_bot(self.cfg,self.store)

    async def asyncTearDown(self):
        await self.bot.close()
        self.temp.cleanup()

    async def test_command_tree_and_persistent_controls_build_offline(self):
        commands={c.name:c for c in self.bot.pending_application_commands}
        self.assertEqual(set(commands),{'trial','board'})
        self.assertEqual({c.name for c in commands['trial'].subcommands},{'start','status','list','reassign','close'})
        for command in commands.values():
            self.assertTrue(command.to_dict()['options'])
        self.assertTrue(TrialView(self.runtime,1,2).is_persistent())
        self.assertTrue(TrialView(self.runtime,1,2,'application').is_persistent())
        self.assertFalse(self.bot.intents.message_content)
        self.assertFalse(self.bot.intents.members)
        self.assertFalse(self.runtime.dispatch.is_running())

    async def test_config_starts_disabled_with_unset_ids(self):
        with self.assertRaises(RuleError): Config.read('trial_board_bot/config.example.toml')

    async def test_feedback_delivery_goes_only_to_staff(self):
        self.store.pause(False,99)
        self.store.approve(10,'normal',2,99)
        self.store.availability(10,[[1800010000,1800020000]],'UTC',True)
        t=self.store.create(1,150,'normal',60,14,99)
        self.store.applicant_availability(t['id'],1,[[1800010000,1800020000]],'UTC')
        t=self.store.get(t['id'])
        start=self.store.available_slots(t['id'],10)[0][0]
        t=self.store.propose(t['id'],10,start,t['revision'])
        t=self.store.confirm(t['id'],1,t['revision'])
        self.store.clock=lambda:start+3600
        self.store.feedback(t['id'],10,'concern','Private staff-only observation @everyone')
        job=None
        while (next_job:=self.store.next_job()) is not None:
            if next_job['kind']=='feedback':
                job=next_job
                break
            self.store.finish_job(next_job,'sent',555,100)
        self.assertIsNotNone(job)
        queue,staff=SimpleNamespace(id=100,send=AsyncMock()),SimpleNamespace(id=200,send=AsyncMock())
        staff.send.return_value=SimpleNamespace(id=999)
        self.runtime.validate_channels=AsyncMock(return_value=(queue,staff))
        self.runtime.app_channel=AsyncMock()
        await self.runtime.deliver(job)
        queue.send.assert_not_awaited()
        self.runtime.app_channel.assert_not_awaited()
        staff.send.assert_awaited_once()
        kwargs=staff.send.call_args.kwargs
        self.assertFalse(kwargs['allowed_mentions'].everyone)
        self.assertIn('Private staff',kwargs['embed'].description)
        self.assertNotIn('@everyone',kwargs['embed'].description)

    async def test_channel_permission_validation_fails_closed(self):
        channel=MagicMock(spec=discord.TextChannel)
        everyone=SimpleNamespace(id=1,permissions=SimpleNamespace(administrator=False),is_default=lambda:True,is_bot_managed=lambda:False)
        volunteer=SimpleNamespace(id=400,permissions=SimpleNamespace(administrator=False),is_default=lambda:False,is_bot_managed=lambda:False)
        staff=SimpleNamespace(id=300,permissions=SimpleNamespace(administrator=False),is_default=lambda:False,is_bot_managed=lambda:False)
        me=SimpleNamespace(roles=[],id=50)
        channel.guild=SimpleNamespace(default_role=everyone,roles=[everyone,volunteer,staff],me=me)
        channel.overwrites={}
        channel.permissions_for.side_effect=lambda x:SimpleNamespace(
            view_channel=x is not everyone,send_messages=True,embed_links=True,read_message_history=True)
        private_channel(channel,{300,400})
        with self.assertRaises(RuleError): private_channel(channel,{300})
        channel.permissions_for.side_effect=lambda x:SimpleNamespace(view_channel=True)
        with self.assertRaises(RuleError): private_channel(channel,{300,400})


if __name__=='__main__':
    unittest.main()
