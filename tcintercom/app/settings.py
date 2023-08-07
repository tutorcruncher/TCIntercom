from urllib.parse import urlparse

from arq.connections import RedisSettings
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gh_token: str = ''
    ic_token: str = ''
    ic_bot_id: int = 2693259
    redis_url: str = 'redis://localhost:6379'
    tc_url: str = 'http://tutorcruncher.com'
    netlify_key: str = ''

    @property
    def redis_settings(self):
        conf = urlparse(self.redis_url)
        return RedisSettings(
            host=conf.hostname, port=conf.port, password=conf.password, database=int((conf.path or '0').strip('/'))
        )

    class ConfigDict:
        fields = {
            'gh_token': {'env': 'GH_TOKEN'},
            'ic_token': {'env': 'IC_TOKEN'},
            'redis_url': {'env': 'REDIS_URL'},
            'ic_bot_id': {'env': 'IC_BOT_ID'},
            'netlify_key': {'env': 'NETLIFY_KEY'},
        }
