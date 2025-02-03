import hashlib
import hmac
import json
import logging
from enum import Enum
from typing import Optional

import logfire
import requests
from starlette.requests import Request
from starlette.responses import JSONResponse

from tcintercom.app.settings import app_settings

logger = logging.getLogger('tc-intercom.views')
session = requests.Session()

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


async def validate_ic_webhook_signature(request: Request):
    """
    Validates the webhook signature from Intercom.

    https://developers.intercom.com/docs/references/webhooks/webhook-models#signed-notifications
    """
    if app_settings.testing:
        return
    header_signature = request.headers.get('x-hub-signature', '')
    payload = await request.body()
    assert (
        f'sha1={hmac.new(app_settings.ic_client_secret.encode(), payload, hashlib.sha1).hexdigest()}'
        == header_signature
    ), 'Unable to validate signature.'


def intercom_request(url: str, data: Optional[dict] = None, method: str = 'GET') -> Optional[dict]:
    """
    Makes a request to Intercom, takes the url, data and method to use when making the request.
    """
    data = data or {}
    headers = {
        'Authorization': 'Bearer ' + app_settings.ic_secret_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if not (method == 'POST' and not app_settings.ic_secret_token):
        try:
            r = session.request(method, 'https://api.intercom.io' + url, json=data, headers=headers)
            r.raise_for_status()
        except Exception as e:
            logger.exception(e)
            raise e
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
    if item.get('user'):
        # This is for the old apps we have that still have User added to their webhooks.
        user_id = item['user']['id']
    else:
        # This is for the newer apps that use contacts instead of user.
        user_id = item['contacts']['contacts'][0]['id']
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
            'admin_id': app_settings.ic_bot_id,
            'body': SUPPORT_TEMPLATE,
            'assignee': app_settings.ic_bot_id,
        }
        await async_intercom_request(f'/conversations/{item["id"]}/reply/', data=reply_data, method='POST')
        return 'Reply successfully posted'
    else:
        return 'Company has support'


async def handle_intercom_callback(request: Request) -> JSONResponse:
    """
    Handles the callback from Intercom and decides what actions to take based on the topic.
    """
    await validate_ic_webhook_signature(request)
    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)
    item_data = data.get('data', {}).get('item', {})
    topic = data.get('topic', None)
    msg = 'No action required'
    logfire.info('Intercom callback topic={topic}', topic=topic, data=data)
    if topic == 'conversation.user.created':
        msg = await check_support_reply(item_data) or msg
    logger.info('Conversation ID: {id} - {msg}'.format(id=item_data.get('id'), msg=msg))
    return JSONResponse({'message': msg})


async def handle_blog_callback(request: Request) -> JSONResponse:
    """
    Handles the callback from Netlify and updates the user's Intercom profile with the blog subscription custom
    attribute, if they don't exist then we create a new user in Intercom for that email address.
    """
    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)

    if not (email := data.get('email')):
        return JSONResponse({'error': 'Email address is required'}, status_code=400)

    # TODO: We should probably validate the email address here

    q = {'query': {'field': 'email', 'operator': '=', 'value': email}}
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
