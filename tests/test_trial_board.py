"""Async backend client contract: no local trial database."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import aiohttp
from trial_board_bot.client import BackendClient, BackendUnavailable, RuleError

class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_actor_roles_and_request_identity_reach_backend(self):
        transport=AsyncMock(return_value={'id':17})
        actor=SimpleNamespace(id=99,roles=[SimpleNamespace(id=300)])
        result=await BackendClient(1,transport=transport).call('create',actor,applicant=1,channel=150,request_id='discord:123')
        self.assertEqual(result,{'id':17})
        payload=transport.call_args.args[0]
        self.assertEqual(payload['actor'],{'id':99,'role_ids':[300]})
        self.assertEqual(payload['data']['request_id'],'discord:123')
        self.assertEqual(payload['guild_id'],1)

    async def test_worker_does_not_impersonate_staff(self):
        transport=AsyncMock(return_value=None)
        await BackendClient(1,transport=transport).call('dispatch',worker='test')
        self.assertIsNone(transport.call_args.args[0]['actor'])

    async def test_url_and_credentials_fail_closed(self):
        for url in ('http://example.com','https://user:pass@example.com','https://example.com?key=secret'):
            with self.assertRaises(RuleError):BackendClient(1,url=url,api_key='one',trial_key='two')
        with self.assertRaises(RuleError):BackendClient(1,url='https://example.com',api_key='',trial_key='two')
        BackendClient(1,url='http://127.0.0.1:5000',api_key='one',trial_key='two')

    async def test_timeout_does_not_retry_or_leak_secrets(self):
        client=BackendClient(1,url='https://example.com',api_key='secret-one',trial_key='secret-two')
        with patch.object(aiohttp.ClientSession,'post',side_effect=asyncio.TimeoutError('secret-one')) as post:
            with self.assertRaises(BackendUnavailable) as raised:await client.call('confirm',number=2,revision=3)
            self.assertEqual(post.call_count,1)
            self.assertNotIn('secret-one',str(raised.exception))
            self.assertFalse(post.call_args.kwargs['allow_redirects'])

    async def test_real_http_transport_and_conflict_response(self):
        from aiohttp import web
        seen=[]
        async def endpoint(request):
            seen.append((dict(request.headers),await request.json()))
            if seen[-1][1]['action']=='bad':return web.json_response({'error':'Only the applicant can confirm.'},status=409)
            return web.json_response({'result':{'paused':True}})
        app=web.Application();app.router.add_post('/trial-board/actions',endpoint)
        runner=web.AppRunner(app);await runner.setup()
        site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        try:
            port=site._server.sockets[0].getsockname()[1]
            client=BackendClient(1,url=f'http://127.0.0.1:{port}',api_key='one',trial_key='two')
            self.assertEqual(await client.call('bootstrap'),{'paused':True})
            self.assertEqual(seen[0][0]['X-API-Key'],'one')
            self.assertEqual(seen[0][0]['X-Trial-Board-Key'],'two')
            with self.assertRaisesRegex(RuleError,'Only the applicant'):await client.call('bad')
        finally:await runner.cleanup()

if __name__=='__main__':unittest.main()
