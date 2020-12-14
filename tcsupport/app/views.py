from starlette.requests import Request
from starlette.responses import Response


async def index(request: Request):
    return Response("TutorCruncher's service for managing Intercom is Online")


async def raise_error(request: Request):
    raise RuntimeError('Purposeful error')
