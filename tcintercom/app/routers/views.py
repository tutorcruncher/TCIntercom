from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import FileResponse

from ..views import handle_blog_callback, handle_intercom_callback

views_router = APIRouter()


@views_router.get('/', name='index')
def index():
    return {'message': "TutorCruncher's service for managing Intercom is Online"}


@views_router.get('/robots.txt')
async def robots(request: Request):
    return FileResponse(path='tcintercom/robots.txt', media_type='text/plain')


@views_router.get('/error/', name='error')
async def raise_error(request: Request):
    raise RuntimeError('Purposeful error')


@views_router.post('/callback/', name='callback')
async def callback(request: Request):
    return await handle_intercom_callback(request)


@views_router.post('/blog-callback/', name='blog-callback')
async def blog_callback(request: Request):
    return await handle_blog_callback(request)
