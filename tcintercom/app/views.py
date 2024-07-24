import json
import logging
from enum import Enum
from typing import Optional

import jwt
import logfire
import requests
from jwt import InvalidSignatureError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .settings import Settings

logger = logging.getLogger('tc-intercom.views')
session = requests.Session()
conf = Settings()

SUPPORT_TEMPLATE = """\
Thanks for getting in touch 😃

We try to get back to everyone within 2 working days, but most of the time it's quicker!

If you wish to upgrade your support plan, you can do that \
for only $12 by clicking <a href="https://secure.tutorcruncher.com/billing"/>here</a>! \
Please note this might take an hour to update, so just reply here saying you've changed your \
support plan and we'll check 😃

If your query is urgent, please reply with 'This is urgent' and we'll get someone to look at \
it as soon as possible."""


class SupportTag(str, Enum):
    NO_SUPPORT = 'No Support'
    CHAT_SUPPORT = 'Chat Support'
    PHONE_SUPPORT = 'Phone Support'


def intercom_request(url: str, data: Optional[dict] = None, method: str = 'GET') -> Optional[dict]:
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


async def async_intercom_request(url: str, data: Optional[dict] = None, method: str = 'GET') -> Optional[dict]:
    """
    Asynchronous version of intercom_request
    """
    return intercom_request(url, data, method)


async def check_support_reply(item: dict) -> str:
    """
    Checks the support level of the company and the bot replies with the support template if they have no support.
    """
    user_id = item['user']['id']
    user_data = await async_intercom_request(f'/contacts/{user_id}/')
    companies = user_data.get('companies', {}).get('data')
    if not companies:
        return 'User has no companies'
    company_data = await async_intercom_request(companies[0]['url'])
    support_level = company_data.get('custom_attributes', {}).get('support_plan')
    if support_level == SupportTag.NO_SUPPORT:
        reply_data = {
            'type': 'admin',
            'message_type': 'comment',
            'admin_id': conf.ic_bot_id,
            'body': SUPPORT_TEMPLATE,
            'assignee': conf.ic_bot_id,
        }
        await async_intercom_request(f"/conversations/{item['id']}/reply/", data=reply_data, method='POST')
        return 'Reply successfully posted'
    else:
        return 'Company has support'


async def handle_intercom_callback(request: Request) -> JSONResponse:
    """
    Handles the callback from Intercom and decides what actions to take based on the topic.
    """
    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)
    item_data = data['data']['item']
    topic = data.get('topic')
    msg = 'No action required'
    logfire.info('Intercom callback topic={topic}', topic=topic, data=data)
    if topic == 'conversation.user.created':
        msg = await check_support_reply(item_data) or msg
    logger.info({'conversation': item_data.get('id'), 'message': msg})
    return JSONResponse({'message': msg})


async def handle_blog_callback(request: Request) -> JSONResponse:
    """
    Handles the callback from Netlify and updates the user's Intercom profile with the blog subscription custom
    attribute, if they don't exist then we create a new user in Intercom for that email address.
    """
    try:
        jwt.decode(request.headers['x-webhook-signature'], conf.netlify_key, algorithms='HS256')
    except InvalidSignatureError:
        return JSONResponse({'error': 'Invalid Signature'}, status_code=400)

    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)

    data = data['data']
    q = {'query': {'field': 'email', 'operator': '=', 'value': data['email']}}
    r = await async_intercom_request('/contacts/search', data=q, method='POST')

    logfire.info('Blog callback', data=data)
    data_to_send = {'role': 'user', 'email': data['email'], 'custom_attributes': {'blog-subscribe': True}}
    if r.get('data'):
        await async_intercom_request(url=f'/contacts/{r["data"][0]["id"]}', data=data_to_send, method='PUT')
        msg = 'Blog subscription added to existing user'
    else:
        await async_intercom_request(url='/contacts', data=data_to_send, method='POST')
        msg = 'Blog subscription added to a new user'
    return JSONResponse({'message': msg})
