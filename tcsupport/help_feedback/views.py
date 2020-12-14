import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from tcsupport.app.settings import Settings

logger = logging.getLogger('tc-support.help-ratings.views')
conf = Settings()


async def submit_feedback(request: Request):
    origin = request.headers.get('Origin') or request.headers.get('Referer')
    if not origin or not origin.startswith(conf.tc_url):
        return JSONResponse(
            {'error': f'The current Origin, {origin}, does not match the allowed domains'}, status_code=403
        )
    try:
        feedback_data = json.loads(await request.body())
    except ValueError:
        return JSONResponse({'error': 'Invalid JSON'}, status_code=400)
    logger.info('Processing feedback from help page...')
    await request.app.redis.enqueue_job('process_feedback', feedback_data=feedback_data)
    return Response('OK')
