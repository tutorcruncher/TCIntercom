import json
import logging
import logging.config
import os
from typing import Optional

import requests
import uvicorn as uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

session = requests.Session()
IC_TOKEN = os.getenv('IC_TOKEN', '')
GH_TOKEN = os.getenv('GH_TOKEN', '')


logger = logging.getLogger('default')


async def index(request: Request):
    return Response("TutorCruncher's service for managing Intercom is Online")


async def intercom_request(url: str, data: Optional[dict] = None, method: str = 'GET'):
    data = data or {}
    headers = {
        'Authorization': 'Bearer ' + IC_TOKEN,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if not (method == 'POST' and not IC_TOKEN):
        r = session.request(method, 'https://api.intercom.io' + url, json=data, headers=headers)
        r.raise_for_status()
        return r.json()


async def github_request(url: str, data: dict):
    if GH_TOKEN:
        headers = {'Authorization': 'Bearer ' + GH_TOKEN}
        r = session.post(
            'https://api.github.com/repos/tutorcruncher/tutorcruncher.com' + url, json=data, headers=headers,
        )
        r.raise_for_status()
        return await r.json()


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
    user_id = item['user']['user_id']
    user_data = await intercom_request(f'/contacts/{user_id}/')
    companies = user_data.get('companies', {}).get('data')
    if not companies:
        return 'User has no companies'
    company_data = await intercom_request(companies[0]['url'])
    support_level = company_data.get('custom_attributes', {}).get('support_plan')
    admin_bot = os.getenv('BOT_ADMIN_ID', '2693259')
    if support_level == 'No Support':
        reply_data = {
            'type': 'admin',
            'message_type': 'comment',
            'admin_id': admin_bot,
            'body': SUPPORT_TEMPLATE,
            'assignee': admin_bot,
        }
        await intercom_request(f"/conversations/{item['id']}/reply/", data=reply_data, method='POST')
        return 'Reply successfully posted'
    else:
        return 'Company has support'


async def check_message_tags(item: dict):
    tags = [t['name'] for t in item['tags_added']['tags']]
    if any(t in ['New help article', 'Update help article'] for t in tags):
        part = item['conversation_parts']['conversation_parts'][0]
        data = {
            'title': 'From IC: ' + ','.join(tags),
            'body': '**Created from intercom**\n\n' + part['body'],
            'labels': tags,
        }
        await github_request('/issues/', data)
        return 'Issue created with tags'
    return 'No action required'


async def callback(request: Request):
    try:
        data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)
    item_data = data['data']['item']
    topic = data.get('topic')
    msg = 'No action required'
    if topic == 'conversation.user.created':
        msg = await check_support_reply(item_data)
    elif topic == 'conversation_part.tag.created':
        msg = await check_message_tags(item_data)
    logger.info(msg)
    return JSONResponse({'message': msg})


def setup_logging():
    log_level = 'DEBUG' if os.getenv('DEBUG') else 'INFO'
    raven_dsn = os.getenv('RAVEN_DSN')
    config = {
        'version': 1,
        'handlers': {
            'default': {'level': log_level, 'class': 'logging.StreamHandler'},
            'sentry': {
                'level': 'WARNING',
                'class': 'raven.handlers.logging.SentryHandler',
                'dsn': raven_dsn,
                'release': os.getenv('COMMIT', None),
            },
        },
        'loggers': {
            'default': {'handlers': ['default', 'sentry'], 'level': log_level},
            'uvicorn.error': {'handlers': ['sentry'], 'level': 'ERROR'},
        },
    }
    logging.config.dictConfig(config)


app = Starlette(
    debug=bool(os.getenv('DEBUG')), routes=[Route('/', index), Route('/callback/', callback, methods=['POST'])]
)


if __name__ == '__main__':
    setup_logging()
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
