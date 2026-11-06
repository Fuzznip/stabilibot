"""Discord adapter for the trial workflow; import does not log in or send messages."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import tomllib
import uuid

import discord
from discord.ext import commands, tasks

from .store import RuleError, Store, parse_windows

log = logging.getLogger(__name__)


@dataclass
class Config:
    enabled: bool
    guild_id: int
    queue_channel_id: int
    staff_channel_id: int
    staff_role_ids: list[int]
    volunteer_role_ids: list[int]
    database: str = 'private/trial-board.sqlite3'
    shared_pool: bool = True
    offer_limit: int = 3
    trial_days: int = 14

    @classmethod
    def read(cls, path):
        with open(path, 'rb') as f:
            cfg = cls(**tomllib.load(f))
        ids = [cfg.guild_id,cfg.queue_channel_id,cfg.staff_channel_id,*cfg.staff_role_ids,*cfg.volunteer_role_ids]
        if not cfg.staff_role_ids or not cfg.volunteer_role_ids or any(type(i) is not int or i <= 0 for i in ids):
            raise RuleError('Set real guild, channel and role IDs in your private config.')
        if cfg.queue_channel_id == cfg.staff_channel_id or set(cfg.staff_role_ids) & set(cfg.volunteer_role_ids):
            raise RuleError('Staff feedback must have a separate channel and staff roles.')
        if not 1 <= cfg.offer_limit <= 5 or not 1 <= cfg.trial_days <= 30:
            raise RuleError('offer_limit must be 1–5; trial_days must be 1–30.')
        database=Path(cfg.database).resolve()
        private_root=Path('private').resolve()
        if database == private_root or not database.is_relative_to(private_root):
            raise RuleError('Keep the database under private/ (outside Git).')
        return cfg


def stamp(value):
    return f'<t:{value}:f>'


def safe(text):
    return discord.utils.escape_mentions(discord.utils.escape_markdown(text))


def private_channel(channel, roles, users=()):
    """Fail closed on accidental access. Administrators always have Discord access."""
    if not isinstance(channel, discord.TextChannel):
        raise RuleError('Use private server text channels, not DMs or threads.')
    if channel.permissions_for(channel.guild.default_role).view_channel:
        raise RuleError('This channel is visible to @everyone. Fix permissions before continuing.')
    for role in channel.guild.roles:
        if role.is_default() or role.permissions.administrator:
            continue
        if channel.permissions_for(role).view_channel and role.id not in roles:
            # The bot's managed role is permitted, but no unrelated bot/app roles.
            me = channel.guild.me
            if not me or not role.is_bot_managed() or getattr(role.tags,'bot_id',None) != me.id:
                raise RuleError('An unapproved role can view this channel. Review channel permissions.')
    for target, overwrite in channel.overwrites.items():
        if isinstance(target, discord.Member) and overwrite.view_channel is True:
            if target.id not in users and target != channel.guild.me and not target.guild_permissions.administrator:
                if not {r.id for r in target.roles} & set(roles):
                    raise RuleError('An unapproved member override can view this channel.')
    me = channel.guild.me
    if me is None:
        raise RuleError('Bot member is unavailable.')
    permissions = channel.permissions_for(me)
    if not all((permissions.view_channel, permissions.send_messages,
                permissions.embed_links, permissions.read_message_history)):
        raise RuleError('Bot needs View Channel, Send Messages, Embed Links and Read Message History.')


async def reply(interaction, text):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
    else:
        await interaction.response.send_message(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


class AvailabilityModal(discord.ui.Modal):
    def __init__(self, runtime, trial=None):
        super().__init__(title='When can you pot?', timeout=600)
        self.runtime, self.trial = runtime, trial
        self.zone = discord.ui.InputText(label='Timezone', placeholder='America/New_York', max_length=64)
        self.windows = discord.ui.InputText(
            label='Available windows (one per line)', style=discord.InputTextStyle.long,
            placeholder='2026-11-08 18:00 / 2026-11-08 21:00', max_length=1000)
        self.add_item(self.zone)
        self.add_item(self.windows)

    async def callback(self, interaction):
        try:
            await self.runtime.guard(interaction, volunteer=self.trial is None)
            windows = parse_windows(self.windows.value, self.zone.value, self.runtime.store.now())
            if self.trial is None:
                self.runtime.store.availability(interaction.user.id, windows, self.zone.value.strip(), True)
            else:
                self.runtime.store.applicant_availability(self.trial, interaction.user.id, windows, self.zone.value.strip())
            await reply(interaction, 'Availability saved. The bot will use these windows to find a time.')
        except RuleError as e:
            await reply(interaction, str(e))


class FeedbackModal(discord.ui.Modal):
    def __init__(self, runtime, trial):
        super().__init__(title='Private staff feedback', timeout=600)
        self.runtime, self.trial = runtime, trial
        self.decision = discord.ui.InputText(label='recommend / more_time / concern', max_length=20)
        self.notes = discord.ui.InputText(label='Communication, effort, participation and fit',
                                        style=discord.InputTextStyle.long, min_length=5,max_length=1800)
        self.add_item(self.decision)
        self.add_item(self.notes)

    async def callback(self, interaction):
        try:
            await self.runtime.guard(interaction, volunteer=True)
            self.runtime.store.feedback(self.trial, interaction.user.id,
                                        self.decision.value.strip().lower(),self.notes.value)
            await reply(interaction, 'Saved for staff review. This does not admit or promote anyone.')
        except RuleError as e:
            await reply(interaction, str(e))


class SlotSelect(discord.ui.Select):
    def __init__(self, runtime, trial, user, revision, slots):
        self.runtime,self.trial,self.user,self.revision = runtime,trial,user,revision
        options = [discord.SelectOption(label=datetime.fromtimestamp(s,timezone.utc).strftime('%a %d %b %H:%M UTC'),
                                        description=f'{(e-s)//60} minutes', value=str(s)) for s,e in slots]
        super().__init__(placeholder='Choose a proposed start time (UTC)',options=options)

    async def callback(self, interaction):
        try:
            await self.runtime.guard(interaction,volunteer=True)
            if interaction.user.id != self.user:
                raise RuleError('Open your own slot picker.')
            t = self.runtime.store.propose(self.trial,self.user,int(self.values[0]),self.revision)
            await reply(interaction,f"Offered {stamp(t['start'])}. Waiting for the applicant to confirm.")
        except RuleError as e:
            await reply(interaction,str(e))


class TrialView(discord.ui.View):
    def __init__(self, runtime, trial, revision, kind='board'):
        super().__init__(timeout=None)
        self.runtime,self.trial,self.revision = runtime,trial,revision
        actions = [('Pick a time','pick'),('Submit feedback','feedback'),('Reschedule','reschedule')] if kind == 'board' else [
            ('Set availability','availability'),('Confirm time','confirm'),('Reschedule','reschedule')]
        for label,action in actions:
            button = discord.ui.Button(label=label,custom_id=f'trial:{trial}:{revision}:{action}',
                                       style=discord.ButtonStyle.primary if action in ('pick','confirm') else discord.ButtonStyle.secondary)
            async def callback(interaction, action=action):
                await self.handle(interaction,action)
            button.callback = callback
            self.add_item(button)

    async def handle(self, interaction, action):
        try:
            await self.runtime.guard(interaction,volunteer=action in ('pick','feedback'))
            t = self.runtime.store.get(self.trial)
            if action != 'feedback' and self.revision != t['revision']:
                raise RuleError('This card is old. Use /trial status for the current controls.')
            if action == 'pick':
                slots = self.runtime.store.available_slots(self.trial,interaction.user.id)
                if not slots:
                    raise RuleError('No matching slots, or you are at capacity. Update /board availability or ask staff.')
                view = discord.ui.View(timeout=300)
                view.add_item(SlotSelect(self.runtime,self.trial,interaction.user.id,t['revision'],slots))
                await interaction.response.send_message('Choose a time. It is booked only after the applicant confirms.',view=view,ephemeral=True)
            elif action == 'feedback':
                if t['owner'] != interaction.user.id or t['status'] != 'booked' or self.runtime.store.now() < t['start']:
                    raise RuleError('Feedback is available to the assigned voucher after the session starts.')
                await interaction.response.send_modal(FeedbackModal(self.runtime,self.trial))
            elif action == 'availability':
                if interaction.user.id != t['applicant'] or t['status'] not in ('open','availability'):
                    raise RuleError('Only the applicant can set availability on an unbooked trial.')
                await interaction.response.send_modal(AvailabilityModal(self.runtime,self.trial))
            elif action == 'confirm':
                t = self.runtime.store.confirm(self.trial,interaction.user.id,self.revision)
                await reply(interaction,f"Confirmed for {stamp(t['start'])}.")
            elif action == 'reschedule':
                self.runtime.store.reopen(self.trial,interaction.user.id,self.runtime.is_staff(interaction.user),self.revision)
                await reply(interaction,'Booking released. Please set fresh applicant availability.')
        except RuleError as e:
            await reply(interaction,str(e))

    async def on_error(self, error, item, interaction):
        # Never log interaction payloads, notes, tokens or applicant names.
        log.error('Trial control failed: %s',type(error).__name__)
        await reply(interaction,'That action could not be completed. Check /trial status before trying again.')


class Runtime(commands.Cog, name='TrialBoard'):
    def __init__(self, bot, cfg, store, standalone=False):
        self.bot,self.cfg,self.store = bot,cfg,store
        self.worker = str(uuid.uuid4())
        self.ready = False
        self.standalone = standalone
        self.loaded = True
        self.command_groups = []
        self.controls = []

    def cog_unload(self):
        self.loaded = False
        if self.dispatch.is_running():
            self.dispatch.cancel()
        for group in self.command_groups:
            self.bot.remove_application_command(group)
        for view in self.controls:
            view.stop()
        self.controls.clear()

    def is_staff(self, member):
        return isinstance(member,discord.Member) and bool({r.id for r in member.roles} & set(self.cfg.staff_role_ids))

    def is_volunteer(self, member):
        v = self.store.volunteer(member.id)
        return isinstance(member,discord.Member) and v and v['approved'] and bool(
            {r.id for r in member.roles} & set(self.cfg.volunteer_role_ids))

    async def validate_channels(self):
        guild = self.bot.get_guild(self.cfg.guild_id)
        if guild is None:
            raise RuleError('The configured server is unavailable.')
        for ident in self.cfg.staff_role_ids + self.cfg.volunteer_role_ids:
            if guild.get_role(ident) is None:
                raise RuleError('A configured staff or volunteer role is missing.')
        queue = guild.get_channel(self.cfg.queue_channel_id)
        staff = guild.get_channel(self.cfg.staff_channel_id)
        private_channel(queue,set(self.cfg.staff_role_ids+self.cfg.volunteer_role_ids))
        private_channel(staff,set(self.cfg.staff_role_ids))
        return queue,staff

    async def guard(self, interaction, staff=False, volunteer=False):
        if not self.loaded:
            raise RuleError('Trial coordination is unloaded. Ask staff to review its configuration.')
        if not interaction.guild or interaction.guild.id != self.cfg.guild_id:
            raise RuleError('Use this command in the configured server.')
        await self.validate_channels()
        if staff and not self.is_staff(interaction.user):
            raise RuleError('This action is for configured staff roles only.')
        if volunteer and not self.is_volunteer(interaction.user):
            raise RuleError('You need staff approval and the volunteer Discord role first.')

    async def app_channel(self,t):
        channel = self.bot.get_channel(t['channel']) or await self.bot.fetch_channel(t['channel'])
        if not isinstance(channel,discord.TextChannel) or channel.guild.id != self.cfg.guild_id:
            raise RuleError('Application channel must be a text channel in the configured server.')
        private_channel(channel,set(self.cfg.staff_role_ids),{t['applicant'],t['owner']})
        member = channel.guild.get_member(t['applicant']) or await channel.guild.fetch_member(t['applicant'])
        if not channel.permissions_for(member).view_channel:
            raise RuleError('The applicant cannot view their application channel.')
        return channel

    def view(self,t,kind='board'):
        view = TrialView(self,t['id'],t['revision'],kind)
        self.controls = [v for v in self.controls if not v.is_finished()]
        self.controls.append(view)
        return view

    def card(self,t):
        embed = discord.Embed(title=f"Trial #{t['id']} · {t['status'].replace('_',' ')}",color=0xa32935)
        embed.add_field(name='Applicant',value=f"<@{t['applicant']}>")
        embed.add_field(name='Application',value=f"<#{t['channel']}>")
        embed.add_field(name='Pool',value='Shared' if self.cfg.shared_pool else t['board'].title())
        embed.add_field(name='Voucher',value=f"<@{t['owner']}>" if t['owner'] else 'Unassigned')
        embed.add_field(name='Session length',value=f"{t['duration']//60} minutes")
        embed.add_field(name='Trial deadline',value=stamp(t['deadline']))
        if t['start']:
            embed.add_field(name='Proposed time' if t['status']=='proposed' else 'Session time',
                            value=f"{stamp(t['start'])} – <t:{t['end']}:t>",inline=False)
        windows=json.loads(t['windows'])
        if windows:
            embed.add_field(name='Applicant availability',value='\n'.join(
                f"{stamp(s)} – <t:{e}:t>" for s,e in windows),inline=False)
        embed.set_footer(text=f"Trial {t['id']} · staff decides admission")
        return embed

    @commands.Cog.listener()
    async def on_ready(self):
        if self.ready:
            return
        try:
            await self.validate_channels()
        except RuleError as e:
            log.error('Startup channel validation failed: %s',e)
            self.store.pause(True,0)
            if self.standalone:
                await self.bot.close()
            return
        # Rehydrate controls from durable records; no chat/history scanning.
        with self.store.db() as db:
            rows = db.execute("SELECT trial,revision,kind FROM jobs WHERE status='sent' AND kind IN ('card','application')").fetchall()
        for r in rows:
            view=TrialView(self,r['trial'],r['revision'],'board' if r['kind']=='card' else 'application')
            self.controls.append(view)
            self.bot.add_view(view)
        self.ready=True
        self.dispatch.start()
        log.info('Trial bot ready; workflow paused=%s',self.store.paused())

    @tasks.loop(seconds=30)
    async def dispatch(self):
        if not self.store.acquire_worker(self.worker):
            return
        try:
            await self.validate_channels()
            self.store.tick(self.cfg.offer_limit)
            for _ in range(12):
                if not self.store.acquire_worker(self.worker):
                    break
                job=self.store.next_job()
                if job is None:
                    break
                try:
                    message,channel=await asyncio.wait_for(self.deliver(job),timeout=60)
                    self.store.finish_job(job,'sent',message,channel)
                except RuleError:
                    self.store.finish_job(job,'failed',error='Permission or workflow validation failed')
                except (discord.Forbidden,discord.NotFound):
                    self.store.finish_job(job,'failed',error='Discord permission or destination failure')
                except Exception as e:
                    # Timeout could follow an accepted Discord send. Never send twice blindly.
                    self.store.finish_job(job,'uncertain',error=type(e).__name__)
                    log.error('Delivery %s needs reconciliation (%s)',job['id'],type(e).__name__)
        except RuleError:
            self.store.pause(True,0)
            log.error('Channel permissions changed; trial workflow paused.')
        except Exception as e:
            log.error('Dispatcher failed (%s); will recheck state next cycle',type(e).__name__)

    async def deliver(self,job):
        t=self.store.get(job['trial'])
        queue,staff=await self.validate_channels()
        data=json.loads(job['data'])
        mentions=[]
        embed=self.card(t)
        view=None
        if job['kind']=='card':
            channel=queue
            view=self.view(t) if t['status'] not in ('closed','cancelled') else None
            embed.set_footer(text=f"Trial {t['id']} · delivery {job['id']}")
            if t['card']:
                msg=await channel.fetch_message(t['card'])
                await msg.edit(embed=embed,view=view,allowed_mentions=discord.AllowedMentions.none())
                return msg.id,channel.id
        elif job['kind']=='offer':
            channel=queue
            members=[]
            for user in data['users']:
                try:
                    member=await queue.guild.fetch_member(user)
                except discord.NotFound:
                    continue
                if self.is_volunteer(member) and self.store.available_slots(t['id'],user):
                    members.append(user)
            mentions=members
            embed.description='A trial has a matching time window. Open the trial card and pick a time if you can help.'
            if not members:
                return None,channel.id
        elif job['kind']=='feedback':
            channel=staff
            feedback=self.store.feedback_record(data['feedback'])
            embed=discord.Embed(title=f"Private feedback · trial #{t['id']}",color=0xa32935,
                                description=safe(feedback['notes']))
            embed.add_field(name='Applicant',value=f"<@{t['applicant']}>")
            embed.add_field(name='Voucher',value=f"<@{feedback['author']}>")
            embed.add_field(name='Recommendation',value=feedback['recommendation'].replace('_',' '))
        elif job['kind']=='owner':
            channel=queue
            mentions=[data.get('user') or t['owner']]
            embed.description={
                'waiting':'Your proposed time is waiting for the applicant to confirm.',
                'booked':'The applicant confirmed your session. Use /trial status to see the booking.',
                'reminder':'Your trial session is coming up. Use /trial status if you need to reschedule.',
                'rescheduled':'This booking was released for rescheduling. You are no longer assigned.'
            }[data['event']]
        elif job['kind']=='staff':
            channel=staff
            embed.description={
                'unclaimed':'No one has taken this trial. Staff should check available windows and assign help.',
                'availability_missing':'Applicant availability is still missing. Staff should follow up.',
                'deadline':'Trial deadline reached. Staff review required; no automatic rejection or promotion.',
                'feedback_due':'The session time passed and feedback is missing. Staff should check what happened.',
                'closed':f"Staff recorded the outcome: {t['outcome']}. No Discord roles were changed."
            }[data['event']]
        else:
            channel=await self.app_channel(t)
            # Volunteers need not have access to private applicant channels.
            # Their confirmations/reminders are delivered to the board separately.
            mentions=[t['applicant']]
            view=self.view(t,'application')
            embed.description='Your trial session is coming up.' if job['kind']=='reminder' else {
                'availability':'Please add 2–3 possible windows and your timezone using Set availability. Staff can help if the form is unclear.',
                'confirm':'A volunteer offered this time. Confirm it or reschedule. It is not booked until you confirm.',
                'booked':'Both sides have agreed on this time. Please use Reschedule if it no longer works.',
                'expired':'The proposed time was not confirmed. The trial is back in the queue. Use /trial status to see current controls.'
            }[data['event']]
        embed.set_footer(text=f"Trial {t['id']} · delivery {job['id']}")
        content=' '.join(f'<@{u}>' for u in mentions) or None
        msg=await channel.send(content,embed=embed,view=view,
                               allowed_mentions=discord.AllowedMentions(everyone=False,roles=False,
                                   users=[discord.Object(id=u) for u in mentions],replied_user=False))
        return msg.id,channel.id


def attach_to_bot(bot, cfg, store, standalone=False):
    """Install on an existing bot without replacing events, intents or command sync.

    Commands are owned by the returned cog and removed by cog_unload. Local
    error handlers let Stabilibot retain its existing global error handler.
    """
    names={c.name for c in [*bot.pending_application_commands,*bot.application_commands]}
    if names & {'trial','board'} or bot.get_cog('TrialBoard') is not None:
        raise RuleError('Trial commands or the TrialBoard cog are already installed.')
    runtime=Runtime(bot,cfg,store,standalone=standalone)
    trial=discord.SlashCommandGroup('trial','Arrange and review clan trials',guild_ids=[cfg.guild_id])
    board=discord.SlashCommandGroup('board','Manage trial volunteers',guild_ids=[cfg.guild_id])

    async def command_guard(ctx,staff=False,volunteer=False):
        await runtime.guard(ctx.interaction,staff,volunteer)

    @trial.command(name='start',description='Staff: start a trial in an existing private application channel')
    async def start(ctx, applicant:discord.Member, application:discord.TextChannel,
                    route:discord.Option(str,choices=['normal','efficient'])='normal',minutes:int=60):
        await command_guard(ctx,staff=True)
        await ctx.defer(ephemeral=True)
        if applicant.bot or application.id in (cfg.queue_channel_id,cfg.staff_channel_id):
            raise RuleError('Choose a human applicant and their separate application channel.')
        await runtime.app_channel({'channel':application.id,'applicant':applicant.id,'owner':None})
        t=store.create(applicant.id,application.id,route,minutes,cfg.trial_days,ctx.author.id)
        await ctx.respond(f"Trial #{t['id']} opened. Availability request queued.",ephemeral=True)

    @trial.command(name='status',description='See an accessible trial and its current controls')
    async def status(ctx, number:int):
        await command_guard(ctx)
        t=store.get(number)
        is_board=runtime.is_volunteer(ctx.author) or runtime.is_staff(ctx.author)
        if ctx.author.id not in (t['applicant'],t['owner']) and not is_board:
            raise RuleError('You cannot view this trial.')
        kind='application' if ctx.author.id==t['applicant'] else 'board'
        view=runtime.view(t,kind) if t['status'] not in ('closed','cancelled') else None
        await ctx.respond(embed=runtime.card(t),view=view,ephemeral=True)

    @trial.command(name='list',description='Staff/volunteers: see current trial queue')
    async def listing(ctx):
        await command_guard(ctx)
        if not runtime.is_staff(ctx.author) and not runtime.is_volunteer(ctx.author):
            raise RuleError('This queue is for approved volunteers and staff.')
        rows=store.list()[:30]
        text='\n'.join(f"#{t['id']} · <@{t['applicant']}> · {t['status']}" for t in rows) or 'No open trials.'
        await ctx.respond(text+'\nUse /trial status for details.',ephemeral=True)

    @trial.command(name='reassign',description='Staff: release a booking and ask for fresh applicant availability')
    async def reassign(ctx,number:int):
        await command_guard(ctx,staff=True)
        store.reopen(number,ctx.author.id,staff=True)
        await ctx.respond('Trial reopened. Fresh availability request queued.',ephemeral=True)

    @trial.command(name='close',description='Staff: record an outcome; does not change Discord roles')
    async def close(ctx,number:int,outcome:discord.Option(str,choices=['accepted','declined','withdrawn'])):
        await command_guard(ctx,staff=True)
        store.close(number,ctx.author.id,outcome)
        await ctx.respond('Outcome recorded. No membership/rank roles changed.',ephemeral=True)

    @board.command(name='approve',description='Staff: approve a volunteer; they must opt in separately')
    async def approve(ctx,member:discord.Member,route:discord.Option(str,choices=['normal','efficient'])='normal',capacity:int=2):
        await command_guard(ctx,staff=True)
        if member.bot:
            raise RuleError('Choose a human volunteer.')
        store.approve(member.id,route,capacity,ctx.author.id)
        await ctx.respond('Approved in the bot. Staff must grant the configured volunteer role; the volunteer then uses /board availability to opt in.',ephemeral=True)

    @board.command(name='remove',description='Staff: stop new assignments; existing bookings remain visible')
    async def remove(ctx,member:discord.Member):
        await command_guard(ctx,staff=True)
        store.disable(member.id,ctx.author.id)
        await ctx.respond('Removed from matching. Review /trial list and reassign any existing bookings.',ephemeral=True)

    @board.command(name='availability',description='Approved volunteers: opt in and set your next available dates')
    async def availability(ctx):
        await command_guard(ctx,volunteer=True)
        await ctx.send_modal(AvailabilityModal(runtime))

    @board.command(name='away',description='Approved volunteers: pause new assignments')
    async def away(ctx):
        await command_guard(ctx,volunteer=True)
        v=store.volunteer(ctx.author.id)
        store.availability(ctx.author.id,json.loads(v['windows']),v['zone'],False)
        await ctx.respond('Paused new assignments. Existing bookings still need you or a staff reassignment.',ephemeral=True)

    @board.command(name='pause',description='Staff: pause assignments and outgoing workflow messages')
    async def pause(ctx):
        await command_guard(ctx,staff=True)
        store.pause(True,ctx.author.id)
        await ctx.respond('Trial coordination paused.',ephemeral=True)

    @board.command(name='resume',description='Staff: resume the approved trial-coordination workflow')
    async def resume(ctx):
        await command_guard(ctx,staff=True)
        store.pause(False,ctx.author.id)
        await ctx.respond('Trial coordination resumed.',ephemeral=True)

    @board.command(name='status',description='Staff: view pause state and unresolved deliveries')
    async def health(ctx):
        await command_guard(ctx,staff=True)
        issues=store.issues()
        text=f'Paused: {store.paused()} · Unresolved deliveries: {len(issues)}\n'
        text+='\n'.join(f"Delivery {j['id']} · trial {j['trial']} · {j['kind']} · {j['status']}" for j in issues[:25])
        await ctx.respond(text[:1900],ephemeral=True)

    @board.command(name='recover',description='Staff: reconcile a failed/uncertain delivery after inspecting Discord')
    async def recover(ctx,delivery:int,action:discord.Option(str,choices=['found','retry']),message_id:str=''):
        await command_guard(ctx,staff=True)
        await ctx.defer(ephemeral=True)
        job=store.job(delivery)
        if job['status'] not in ('failed','uncertain'):
            raise RuleError('Only unresolved deliveries can be reconciled.')
        if action=='retry':
            store.finish_job(job,'pending')
            await ctx.respond('Queued again. This action assumes staff verified no message was delivered.',ephemeral=True)
            return
        t=store.get(job['trial'])
        dest=cfg.queue_channel_id if job['kind'] in ('card','offer','owner') else cfg.staff_channel_id if job['kind'] in ('staff','feedback') else t['channel']
        channel=bot.get_channel(dest) or await bot.fetch_channel(dest)
        try:
            msg=await channel.fetch_message(int(message_id))
        except ValueError:
            raise RuleError('Provide the Discord message ID.')
        marker=f"Trial {t['id']} · delivery {delivery}"
        if msg.author.id != bot.user.id or not any(e.footer.text==marker for e in msg.embeds):
            raise RuleError('That message is not the expected bot delivery.')
        store.finish_job(job,'sent',msg.id,channel.id)
        await ctx.respond('Receipt reconciled; no message resent.',ephemeral=True)

    async def trial_command_error(ctx,error):
        original=getattr(error,'original',error)
        if isinstance(original,RuleError):
            await reply(ctx.interaction,str(original))
        else:
            log.error('Command failed (%s)',type(original).__name__)
            await reply(ctx.interaction,'The action could not be completed. Check current status before retrying.')

    runtime.command_groups=[trial,board]
    for group in runtime.command_groups:
        for command in group.subcommands:
            command.error(trial_command_error)
        bot.add_application_command(group)
    try:
        bot.add_cog(runtime)
    except Exception:
        runtime.cog_unload()
        raise
    return runtime


def build_bot(cfg, store):
    # Standalone mode uses the same cog; no second implementation to maintain.
    intents=discord.Intents.none()
    intents.guilds=True
    bot=discord.Bot(intents=intents,auto_sync_commands=False,
                    allowed_mentions=discord.AllowedMentions.none())
    return bot,attach_to_bot(bot,cfg,store,standalone=True)
