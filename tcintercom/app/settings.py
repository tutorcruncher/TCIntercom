from urllib.parse import urlparse

from arq.connections import RedisSettings
from pydantic import BaseSettings


class Settings(BaseSettings):
    gh_token: str = ''
    ic_token: str = ''
    ic_bot_id: int = 2693259
    kare_id: str = ''
    kare_secret: str = ''
    kare_url: str = 'https://api.eu.karehq.com'
    redis_url: str = 'redis://localhost:6379'
    tc_url: str = 'http://tutorcruncher.com'

    @property
    def redis_settings(self):
        conf = urlparse(self.redis_url)
        return RedisSettings(
            host=conf.hostname, port=conf.port, password=conf.password, database=int((conf.path or '0').strip('/'))
        )

    class Config:
        fields = {
            'gh_token': {'env': 'GH_TOKEN'},
            'ic_token': {'env': 'IC_TOKEN'},
            'kare_secret': {'env': 'KARE_SECRET'},
            'kare_id': {'env': 'KARE_ID'},
            'redis_url': {'env': 'REDIS_URL'},
            'ic_bot_id': {'env': 'IC_BOT_ID'}
        }
