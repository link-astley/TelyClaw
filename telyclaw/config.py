"""配置管理：所有可改的开关都集中在这里"""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# DeepSeek（按决策写死）
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_TIMEOUT = 30

# 评分权重：互动20 + 账号20 + 新鲜度15 + 升温10 + 玩梗5 + 搞笑5 + Drama5 + 提及15 + 未饱和5 = 100
DEFAULT_WEIGHTS = {
    "engagement": 0.20,
    "breadth": 0.20,
    "freshness": 0.15,
    "velocity": 0.10,
    "meme": 0.05,
    "funny": 0.05,
    "drama": 0.05,
    "mention": 0.15,
    "unsat": 0.05,
}

# 内容安全检查的风险类别（7 类）
RISK_CATEGORIES = [
    "政治立场与选举",
    "仇恨或歧视",
    "暴力与灾难消费",
    "色情内容",
    "针对个人的恶意攻击",
    "未经证实的严重指控",
    "明显违法或欺诈内容",
]

# 时间窗口（小时）
WINDOWS = {
    "1h": 1,
    "4h": 4,
    "8h": 8,
    "24h": 24,
    "3d": 72,
}

DEFAULT_SETTINGS = {
    "source": "mock",                 # mock / paste / x_api
    "positioning": "面向独立开发者与早期创业者的 AI 内容增长工具",
    "deepseek_api_key": "",
    "default_window": "24h",
    "default_accounts": [],
    "weights": DEFAULT_WEIGHTS,
    # 安全检查默认只打标记、不删帖；改成 true 才真正把有风险的帖子排除掉
    "exclude_risky": False,
    "x_bearer_token": "",
    "x_api_key": "",
    "x_api_secret": "",
    "x_access_token": "",
    "x_access_secret": "",
}


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Settings:
    """读写 data/settings.json"""

    PATH = DATA_DIR / "settings.json"

    @classmethod
    def load(cls) -> dict:
        data = _read_json(cls.PATH, {})
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data or {})
        merged["weights"] = cls._resolve_weights(data or {})
        return merged

    @staticmethod
    def _resolve_weights(data: dict) -> dict:
        """权重按「键集合」做版本校验。

        权重维度改过（比如四维 -> 九维）时，本地存的老权重键集合对不上，
        这时直接退回默认值，否则新公式会被旧配置静默覆盖。
        """
        saved = data.get("weights") or {}
        if set(saved) != set(DEFAULT_WEIGHTS):
            return dict(DEFAULT_WEIGHTS)
        w = dict(DEFAULT_WEIGHTS)
        w.update(saved)
        return w

    @classmethod
    def save(cls, patch: dict) -> dict:
        cur = cls.load()
        cur.update(patch or {})
        _write_json(cls.PATH, cur)
        return cur

    @classmethod
    def get(cls, key, default=None):
        return cls.load().get(key, default)


def has_api_key() -> bool:
    return bool((Settings.get("deepseek_api_key") or "").strip())
