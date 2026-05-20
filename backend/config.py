import os
from dataclasses import dataclass, field


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8000
    llm_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    llm_api_url: str = "https://api.deepseek.com/v1"
    feishu_app_id: str = field(default_factory=lambda: os.getenv("FEISHU_APP_ID", ""))
    feishu_app_secret: str = field(default_factory=lambda: os.getenv("FEISHU_APP_SECRET", ""))

    # Shift pricing defaults (configurable per staff)
    morning_shift_rate: float = 80.0
    evening_shift_rate: float = 60.0
