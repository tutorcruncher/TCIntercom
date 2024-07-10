import os

from fastapi import FastAPI

from tcintercom.app2.settings import Settings
from tcintercom.app2.views import views_router

settings = Settings()
app = FastAPI(debug=bool(os.getenv('DEBUG')))
app.include_router(views_router)


@app.get("/")
def index():
    return {'message': "TutorCruncher's service for managing Intercom is Online"}
