"""Authenticated, idempotent website handoff. Does not guess when an app was accepted."""
import hmac
import os
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from .store import RuleError


class TrialStartRequest(BaseModel):
    # Stabilibot does not pin Pydantic's major version; support both versions
    # accepted by its existing FastAPI requirement.
    class Config:
        extra='forbid'
    token: str = Field(min_length=1,max_length=512)
    request_id: str = Field(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_.:-]+$')
    applicant_id: int = Field(gt=0)
    application_channel_id: int = Field(gt=0)
    route: Literal['normal','efficient'] = 'normal'
    minutes: int = Field(default=60,ge=30,le=240)


def add_trial_routes(router:APIRouter,bot):
    @router.post('/trials/start')
    async def start_trial(payload:TrialStartRequest,response:Response):
        expected=os.getenv('API_TOKEN','')
        if not expected or not hmac.compare_digest(payload.token.encode(),expected.encode()):
            response.status_code=401
            return {'error':'Invalid token'}
        runtime=bot.get_cog('TrialBoard')
        if runtime is None or not runtime.loaded or not runtime.ready:
            response.status_code=503
            return {'error':'Trial coordination is disabled or not ready'}
        if runtime.store.paused():
            response.status_code=503
            return {'error':'Trial coordination is paused'}
        try:
            await runtime.validate_channels()
            guild=bot.get_guild(runtime.cfg.guild_id)
            member=guild.get_member(payload.applicant_id) or await guild.fetch_member(payload.applicant_id)
            if member.bot or payload.application_channel_id in (runtime.cfg.queue_channel_id,runtime.cfg.staff_channel_id):
                raise RuleError('Choose a human applicant and their separate private application channel.')
            await runtime.app_channel({'channel':payload.application_channel_id,'applicant':member.id,'owner':None})
            trial=runtime.store.create(member.id,payload.application_channel_id,payload.route,
                payload.minutes,runtime.cfg.trial_days,0,external_key=payload.request_id)
        except RuleError as error:
            response.status_code=409
            return {'error':str(error)}
        except Exception:
            response.status_code=503
            return {'error':'Could not validate Discord access; no successful trial handoff recorded'}
        response.status_code=200 if trial['replayed'] else 201
        return {'trial_id':trial['id'],'status':trial['status'],'replayed':trial['replayed']}
