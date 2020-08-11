#!/usr/bin/env python3.8
import os

import uvicorn

from app.main import create_app

if __name__ == '__main__':
    uvicorn.run(create_app(), host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
