"""Discord UI and transport regression tests, with a mocked backend."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,MagicMock
import discord
from trial_board_bot.bot import Config,TrialView,AvailabilityModal,build_bot,private_channel
from trial_board_bot.client import BackendUnavailable,RuleError

class DiscordAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cfg=Config(False,1,100,200,[300],[400])
        self.client=SimpleNamespace(call=AsyncMock())
        self.bot,self.runtime=build_bot(self.cfg,self.client)
    async def asyncTearDown(self):
        if self.bot.get_cog('TrialBoard'):self.bot.remove_cog('TrialBoard')
        await self.bot.close()
    async def test_commands_and_persistent_buttons_without_database(self):
        commands={c.name:c for c in self.bot.pending_application_commands}
        self.assertEqual(set(commands),{'trial','board'})
        self.assertEqual({c.name for c in commands['trial'].subcommands},{'start','status','list','reassign','close'})
        self.assertTrue(TrialView(self.runtime,1,2).is_persistent())
        self.assertTrue(TrialView(self.runtime,1,2,'application').is_persistent())
        self.assertFalse(self.runtime.dispatch.is_running())
        self.assertFalse(hasattr(self.runtime,'store'))
    async def test_example_config_fails_until_ids_set(self):
        with self.assertRaises(RuleError):Config.read('trial_board_bot/config.example.toml')
    async def test_backend_records_rehydrate_buttons(self):
        self.client.call.return_value={'config':dict(guild_id=1,queue_channel_id=100,staff_channel_id=200,staff_role_ids=[300],volunteer_role_ids=[400],shared_pool=True),
            'views':[{'trial':7,'revision':2,'kind':'card'},{'trial':7,'revision':3,'kind':'application'}]}
        await self.runtime.restore()
        self.assertTrue(self.runtime.ready);self.assertEqual(len(self.runtime.controls),2)
        self.assertTrue(all(v.is_persistent() for v in self.runtime.controls))
        self.assertEqual(self.runtime.controls[0].children[0].custom_id,'trial:7:2:pick')
    async def test_configuration_mismatch_stops_transport(self):
        self.client.call.return_value={'config':dict(guild_id=999),'views':[]}
        with self.assertRaises(RuleError):await self.runtime.restore()
        self.assertFalse(self.runtime.ready)
    async def test_feedback_goes_only_to_staff(self):
        queue=SimpleNamespace(id=100,send=AsyncMock());staff=SimpleNamespace(id=200,send=AsyncMock(return_value=SimpleNamespace(id=999)))
        self.runtime.validate_channels=AsyncMock(return_value=(queue,staff));self.runtime.app_channel=AsyncMock()
        t=dict(id=1,revision=3,applicant=1,channel=150,board='normal',status='review',owner=10,duration=3600,deadline=1800000000,start=1799900000,end=1799903600,windows='[]',card=None)
        context={'trial':t,'job':dict(id=9,trial=1,kind='feedback',data=json.dumps({'feedback':1})),
            'feedback':dict(author=10,notes='Private staff-only observation @everyone',recommendation='concern')}
        self.assertEqual(await self.runtime.deliver(context),(999,200))
        queue.send.assert_not_awaited();self.runtime.app_channel.assert_not_awaited()
        kwargs=staff.send.call_args.kwargs
        self.assertFalse(kwargs['allowed_mentions'].everyone);self.assertNotIn('@everyone',kwargs['embed'].description)
    async def test_lost_ack_never_resends_or_overwrites_sent_with_uncertain(self):
        self.runtime.ready=True;self.runtime.validate_channels=AsyncMock();self.runtime.deliver=AsyncMock(return_value=(999,100))
        async def backend(action,member=None,**data):
            if action=='dispatch':return {'job':{'id':1,'claim_token':'claim'}}
            if action=='ack':raise BackendUnavailable('Receipt response lost')
        self.client.call.side_effect=backend
        await self.runtime.dispatch.coro(self.runtime)
        self.runtime.deliver.assert_awaited_once()
        self.assertEqual([c.kwargs['status'] for c in self.client.call.call_args_list if c.args[0]=='ack'],['sent'])
    async def test_modal_opens_without_remote_call(self):
        self.runtime.guard=AsyncMock()
        interaction=SimpleNamespace(user=SimpleNamespace(id=1,roles=[]),response=SimpleNamespace(send_modal=AsyncMock()))
        await TrialView(self.runtime,7,2,'application').handle(interaction,'availability')
        interaction.response.send_modal.assert_awaited_once();self.client.call.assert_not_awaited()
        modal=interaction.response.send_modal.call_args.args[0]
        self.assertIsInstance(modal,AvailabilityModal);self.assertEqual(modal.revision,2)
    async def test_private_channel_validation_fails_closed(self):
        channel=MagicMock(spec=discord.TextChannel)
        everyone=SimpleNamespace(id=1,permissions=SimpleNamespace(administrator=False),is_default=lambda:True,is_bot_managed=lambda:False)
        volunteer=SimpleNamespace(id=400,permissions=SimpleNamespace(administrator=False),is_default=lambda:False,is_bot_managed=lambda:False)
        staff=SimpleNamespace(id=300,permissions=SimpleNamespace(administrator=False),is_default=lambda:False,is_bot_managed=lambda:False)
        me=SimpleNamespace(roles=[],id=50);channel.guild=SimpleNamespace(default_role=everyone,roles=[everyone,volunteer,staff],me=me);channel.overwrites={}
        channel.permissions_for.side_effect=lambda who:SimpleNamespace(view_channel=who is not everyone,send_messages=True,embed_links=True,read_message_history=True)
        private_channel(channel,{300,400})
        with self.assertRaises(RuleError):private_channel(channel,{300})
        channel.permissions_for.side_effect=lambda who:SimpleNamespace(view_channel=True)
        with self.assertRaises(RuleError):private_channel(channel,{300,400})

if __name__=='__main__':unittest.main()
