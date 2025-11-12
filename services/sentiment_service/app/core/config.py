from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
        # 将其定义为一个字符串
        TWITTER_BEARER_TOKENS: str

        # 新增一个属性，它会自动将上面的字符串按逗号分割成列表
        @property
        def twitter_token_list(self) -> List[str]:
            return [token.strip() for token in self.TWITTER_BEARER_TOKENS.split(',')]

        class Config:
            env_file = ".env"
            env_file_encoding = 'utf-8'

@lru_cache()
def get_settings():
        return Settings()