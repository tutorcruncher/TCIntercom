import hashlib
import hmac
import json
import logging
from typing import Optional

import logfire
import requests
from starlette.requests import Request
from starlette.responses import JSONResponse

from tcintercom.app.settings import app_settings

logger = logging.getLogger('tc-intercom.views')
session = requests.Session()


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


async def handle_intercom_callback(request: Request) -> JSONResponse:
    """
    Handles the callback from Intercom and logs the topic.
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
