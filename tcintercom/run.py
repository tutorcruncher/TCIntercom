import logging
import os
import sys
from pathlib import Path

import uvicorn

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from tcintercom.app.logs import setup_logging
from tcintercom.app.main import create_app

logger = logging.getLogger('tc-intercom.run')


def web():
    setup_logging()
    port = int(os.getenv('PORT', 8000))
    logger.info('starting uvicorn on port %d', port)
    uvicorn.run(create_app(), host='0.0.0.0', port=port)


def main():
    command = sys.argv[1]
    if command == 'web':
        web()
    else:
        logger.error(f'Invalid command {command}')


if __name__ == '__main__':
    main()  # pragma: no cover
