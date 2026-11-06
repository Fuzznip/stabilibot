"""Async Discord transport for the backend-owned trial workflow. No local DB."""
import os
from urllib.parse import urlparse
import aiohttp


class RuleError(ValueError):
    pass


class BackendUnavailable(RuleError):
    pass


class BackendClient:
    def __init__(self, guild_id, url=None, api_key=None, trial_key=None, transport=None):
        self.guild_id = guild_id
        self.url = (url if url is not None else os.getenv('BACKEND_URL', '')).rstrip('/')
        self.api_key = api_key if api_key is not None else os.getenv('BACKEND_API_KEY', '')
        self.trial_key = trial_key if trial_key is not None else os.getenv('TRIAL_BOARD_API_KEY', '')
        self.transport = transport
        if transport is None:
            parsed = urlparse(self.url)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or
                (parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'))):
                raise RuleError('Set BACKEND_URL to an HTTPS backend URL (HTTP is allowed only for localhost tests).')
            if not self.api_key or not self.trial_key:
                raise RuleError('Set BACKEND_API_KEY and TRIAL_BOARD_API_KEY in the hosting secret store.')

    async def call(self, action, member=None, **data):
        actor = None if member is None else {'id': member.id, 'role_ids': [r.id for r in member.roles]}
        payload = {'guild_id': self.guild_id, 'action': action, 'data': data, 'actor': actor}
        if self.transport is not None:
            return await self.transport(payload)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post(self.url + '/trial-board/actions', json=payload,
                    headers={'X-API-Key': self.api_key, 'X-Trial-Board-Key': self.trial_key},
                    allow_redirects=False) as response:
                    if response.status == 409:
                        body = await response.json()
                        raise RuleError(body.get('error', 'Trial state changed. Check status before retrying.'))
                    if response.status != 200:
                        raise BackendUnavailable('Trial backend unavailable. Check /board status before retrying.')
                    body = await response.json()
                    if not isinstance(body, dict) or 'result' not in body:
                        raise BackendUnavailable('Unexpected trial backend response.')
                    return body['result']
        except RuleError:
            raise
        except Exception:
            # A timeout may follow a committed write. Do not retry mutations or
            # log response bodies, actor data, notes, keys or request headers.
            raise BackendUnavailable('Trial backend did not confirm the action. Check status before retrying.') from None
