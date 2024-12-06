from urllib.parse import urlparse

from arq.connections import RedisSettings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    testing: bool = False
    ic_secret_token: str = ''
    ic_client_secret: str = ''
    ic_bot_id: int = 2693259
    redis_url: str = 'redis://localhost:6379'
    tc_url: str = 'http://tutorcruncher.com'
    netlify_key: str = ''
    raven_dsn: str = ''
    logfire_token: str = ''
    log_level: str = 'INFO'
    dev_mode: bool = False

    @property
    def redis_settings(self):
        conf = urlparse(self.redis_url)
        return RedisSettings(
            host=conf.hostname, port=conf.port, password=conf.password, database=int((conf.path or '0').strip('/'))
        )

    model_config = SettingsConfigDict(env_file='.env', extra='allow')


app_settings = Settings()
