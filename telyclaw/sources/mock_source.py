"""模拟数据源（默认）

关键设计：种子文件里只记"距现在多少分钟"的相对偏移，这里才换算成真实时间。
这样无论你什么时候演示，任何时间窗口都查得到数据。
"""

import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from config import DATA_DIR
from core.models import Post
from sources.base import PostSource

SEED_PATH = DATA_DIR / "seed_posts.json"


def _load_seed():
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class MockSource(PostSource):
    name = "mock"

    def __init__(self, seed: int = 0):
        # seed 变化 => 互动数与措辞重新抖动（"换一批数据"）
        self.seed = int(seed or 0)
        self._seed_data = _load_seed()
        self._accounts = {a["handle"]: a for a in self._seed_data.get("accounts", [])}

    # ------------------------------------------------------------ 抖动
    def _jitter(self, key: str, spread: float = 0.35) -> float:
        """由 (帖子id + 全局seed) 稳定推导出的抖动系数，同一 seed 下结果可复现"""
        h = hashlib.md5(f"{key}|{self.seed}".encode()).hexdigest()
        r = int(h[:8], 16) / 0xFFFFFFFF          # 0~1
        return 1.0 + (r - 0.5) * 2 * spread       # 1±spread

    # ------------------------------------------------------------ 取数
    def fetch(self, handles: list, since: datetime, until: datetime) -> list:
        wanted = {h.lower().lstrip("@") for h in (handles or [])}
        now = datetime.now()
        out = []

        for p in self._seed_data.get("posts", []):
            author = p["author_handle"]
            if wanted and author.lower() not in wanted:
                continue

            created = now - timedelta(minutes=p["offset_minutes"])
            if not (since <= created <= until):
                continue

            j = self._jitter(p["id"])
            acc = self._accounts.get(author, {})
            out.append(Post(
                id=p["id"],
                author_handle=author,
                author_name=acc.get("display_name", author),
                text=p["text"],
                created_at=created.isoformat(timespec="seconds"),
                likes=max(1, int(p["base_likes"] * j)),
                retweets=max(0, int(p["base_retweets"] * j)),
                replies=max(0, int(p["base_replies"] * j)),
                quotes=max(0, int(p["base_quotes"] * j)),
                url=f"https://x.com/{author}/status/{p['id']}",
                source="mock",
            ))

        out.sort(key=lambda x: x.created_at, reverse=True)
        return out

    def all_accounts(self) -> list:
        return list(self._seed_data.get("accounts", []))
