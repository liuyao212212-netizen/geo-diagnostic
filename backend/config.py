"""
系统配置管理 — 纯 stdlib 实现，避免 pydantic-settings 的二进制依赖问题
"""
import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent

class Settings:
    def __init__(self):
        # 应用配置
        self.APP_NAME = os.getenv("APP_NAME", "GEO 品牌诊断系统")
        self.DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

        # 数据库
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'geo_diagnostic.db'}"
        )
        self.DB_PATH = BASE_DIR / "geo_diagnostic.db"

        # 千问 DashScope
        self.DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
        self.DASHSCOPE_BASE_URL = os.getenv(
            "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "qwen-plus")

        # DeepSeek
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
        self.DEEPSEEK_BASE_URL = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        )
        self.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        # 火山引擎（豆包）
        self.VOLCENGINE_API_KEY = os.getenv("VOLCENGINE_API_KEY")
        self.VOLCENGINE_ENDPOINT_ID = os.getenv("VOLCENGINE_ENDPOINT_ID")
        self.VOLCENGINE_BASE_URL = os.getenv(
            "VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        )
        self.VOLCENGINE_MODEL = os.getenv("VOLCENGINE_MODEL", "doubao-pro-4k")

        # 查询配置
        self.QUERY_DELAY_MIN = float(os.getenv("QUERY_DELAY_MIN", "3.0"))
        self.QUERY_DELAY_MAX = float(os.getenv("QUERY_DELAY_MAX", "10.0"))
        self.QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", "60"))
        self.MAX_CONCURRENT_QUERIES = int(os.getenv("MAX_CONCURRENT_QUERIES", "3"))


settings = Settings()
