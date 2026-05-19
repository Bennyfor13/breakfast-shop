from dataclasses import dataclass, field


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8000
    llm_api_key: str = ""
    llm_api_url: str = "https://api.deepseek.com/v1"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""

    # Shift pricing defaults (configurable per staff)
    morning_shift_rate: float = 80.0
    evening_shift_rate: float = 60.0
