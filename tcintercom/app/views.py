import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
import requests
from jwt import InvalidSignatureError
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

from .settings import Settings

session = requests.Session()
logger = logging.getLogger('tc-intercom.views')

conf = Settings()


async def index(request: Request):
    return Response("TutorCruncher's service for managing Intercom is Online")


async def robots(request: Request):
    return FileResponse(path='tcintercom/robots.txt', media_type='text/plain')


async def raise_error(request: Request):
    raise RuntimeError('Purposeful error')


async def intercom_request(url: str, data: Optional[dict] = None, method: str = 'GET'):
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


async def github_request(url: str, data: dict):
    if conf.gh_token:
        headers = {'Authorization': 'Bearer ' + conf.gh_token}
        r = session.post(
            'https://api.github.com/repos/tutorcruncher/tutorcruncher.com' + url,
            json=data,
            headers=headers,
        )
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
CLOSE_CONV_TEMPLATE = """\
I'm just checking in to see how you got with the issue above?

Since we haven't heard anything for \
a week, I'm going to assume you don't need any more help and the ticket will close, but feel free to respond to \
this message to reopen it and I'll be able to get back to you soon.
"""


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


async def create_issue(part, tags):
    data = {
        'title': 'From IC: ' + ','.join(tags),
        'body': '**Created from intercom**\n\n' + part['body'],
        'labels': tags,
    }
    await github_request('/issues', data)


async def snooze_conv_for_close(conv):
    id = conv['id']
    admin_id = conv['assignee']['id'] or conf.ic_bot_id
    a_week_hence = (datetime.now() + timedelta(days=7)).timestamp()
    await intercom_request(
        f'/conversations/{id}/reply',
        data={'message_type': 'snoozed', 'snoozed_until': a_week_hence, 'admin_id': admin_id},
        method='POST',
    )


async def check_message_tags(item: dict):
    tags = [t['name'] for t in item['tags_added']['tags']]
    if any(t in ['New help article', 'Update help article'] for t in tags):
        await create_issue(item['conversation_parts']['conversation_parts'][0], tags)
        return 'Issue created with tags'
    if 'Snooze then close' in tags:
        await snooze_conv_for_close(item)
        return 'Conversation snoozed while waiting for reply'


async def close_conv(conv: dict):
    admin_id = conv['assignee']['id'] or conf.ic_bot_id
    data = {'message_type': 'close', 'admin_id': admin_id, 'type': 'admin', 'body': CLOSE_CONV_TEMPLATE}
    await intercom_request(f'/conversations/{conv["id"]}/parts', method='POST', data=data)


async def check_unsnoozed_conv(item: dict):
    tags = [t['name'] for t in item['tags']['tags']]
    if 'Snooze then close' in tags:
        # The normal item doesn't have the request info
        conv_details = await intercom_request(f'/conversations/{item["id"]}')
        conv_stats = conv_details['statistics']
        a_week_prev = (datetime.now() - timedelta(days=7)).timestamp()
        dt = max(conv_stats['last_contact_reply_at'] or 0, conv_stats['last_admin_reply_at'] or 0)
        logger.info('Checking conv %s with last reply %s against %s', item['id'], dt, a_week_prev)
        if dt < a_week_prev:
            await close_conv(item)
            return 'Conversation closed because of inactivity'


async def callback(request: Request):
    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)
    item_data = data['data']['item']
    topic = data.get('topic')
    msg = 'No action required'
    if topic == 'conversation.user.created':
        msg = await check_support_reply(item_data) or msg
    elif topic == 'conversation_part.tag.created':
        msg = await check_message_tags(item_data) or msg
    elif topic == 'conversation.admin.unsnoozed':
        msg = await check_unsnoozed_conv(item_data) or msg
    logger.info({'conversation': item_data['id'], 'message': msg})
    return JSONResponse({'message': msg})


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
