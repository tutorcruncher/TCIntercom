import json
import logging
from typing import Optional

import jwt
import requests
from fastapi import APIRouter
from jwt import InvalidSignatureError
from starlette.requests import Request
from starlette.responses import JSONResponse

from tcintercom.app2.settings import Settings

session = requests.Session()
views_router = APIRouter()
logger = logging.getLogger('tc-intercom.views')
conf = Settings()


@views_router.get("/error/")
async def raise_error(request: Request):
    raise RuntimeError('Purposeful error')


async def intercom_request(url: str, data: Optional[dict] = None, method: str = 'GET') -> Optional[dict]:
    """
    Makes a request to Intercom, takes the url, data and method to use when making the request.
    """
    data = data or {}
    headers = {
        'Authorization': 'Bearer ' + conf.ic_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if not (method == 'POST' and not conf.ic_token):
        r = session.request(method, 'https://api.intercom.io' + url, json=data, headers=headers)
        r.raise_for_status()
        return r.json()


SUPPORT_TEMPLATE = """\
Thanks for getting in touch 😃

We try to get back to everyone within 2 working days, but most of the time it's quicker!

If you wish to upgrade your support plan, you can do that \
for only $12 by clicking <a href="https://secure.tutorcruncher.com/billing"/>here</a>! \
Please note this might take an hour to update, so just reply here saying you've changed your \
support plan and we'll check 😃

If your query is urgent, please reply with 'This is urgent' and we'll get someone to look at \
it as soon as possible."""


async def check_support_reply(item: dict):
    user_id = item['user']['id']
    user_data = await intercom_request(f'/contacts/{user_id}/')
    companies = user_data.get('companies', {}).get('data')
    if not companies:
        return 'User has no companies'
    company_data = await intercom_request(companies[0]['url'])
    support_level = company_data.get('custom_attributes', {}).get('support_plan')
    if support_level == 'No Support':
        reply_data = {
            'type': 'admin',
            'message_type': 'comment',
            'admin_id': conf.ic_bot_id,
            'body': SUPPORT_TEMPLATE,
            'assignee': conf.ic_bot_id,
        }
        await intercom_request(f"/conversations/{item['id']}/reply/", data=reply_data, method='POST')
        return 'Reply successfully posted'
    else:
        return 'Company has support'


# TODO these should be in their own router file and then all the other functions in a separate file.
@views_router.post('/callback/')
async def callback(request: Request):
    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)
    item_data = data['data']['item']
    print(item_data)
    topic = data.get('topic')
    msg = 'No action required'
    if topic == 'conversation.user.created':
        msg = await check_support_reply(item_data) or msg
    logger.info({'conversation': item_data.get('id'), 'message': msg})
    return JSONResponse({'message': msg})


@views_router.post('/blog-callback/')
async def blog_callback(request: Request):
    try:
        jwt.decode(request.headers['x-webhook-signature'], conf.netlify_key, algorithms="HS256")
    except InvalidSignatureError:
        return JSONResponse({'error': 'Invalid Signature'}, status_code=400)

    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)

    data = data['data']
    q = {'query': {'field': 'email', 'operator': '=', 'value': data['email']}}
    r = await intercom_request('/contacts/search', data=q, method='POST')

    data_to_send = {'role': 'user', 'email': data['email'], 'custom_attributes': {'blog-subscribe': True}}
    if r.get('data'):
        await intercom_request(url=f'/contacts/{r["data"][0]["id"]}', data=data_to_send, method='PUT')
        msg = 'Blog subscription added to existing user'
    else:
        await intercom_request(url='/contacts', data=data_to_send, method='POST')
        msg = 'Blog subscription added to a new user'
    return JSONResponse({'message': msg})
