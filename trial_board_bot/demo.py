"""Offline transport demonstration. Real workflow rules are tested in the backend."""
import asyncio
from types import SimpleNamespace
from .client import BackendClient

async def demo():
    async def transport(payload):
        assert payload['action']=='create' and payload['actor']['role_ids']==[300]
        print('Discord action forwarded to backend with stable request ID:',payload['data']['request_id'])
        return {'id':1,'status':'availability'}
    client=BackendClient(1,transport=transport)
    result=await client.call('create',SimpleNamespace(id=99,roles=[SimpleNamespace(id=300)]),applicant=1,channel=150,request_id='discord:synthetic-demo')
    print('Backend response rendered for Discord:',result['status'])
    print('Offline only: no Discord login, network request, local trial DB or messages.')

def main():asyncio.run(demo())
if __name__=='__main__':main()
