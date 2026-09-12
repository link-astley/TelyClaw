"""粘贴/导入数据源

支持两种格式，自动识别：
1) JSON 数组：[{"author":"sama","text":"...","created_at":"2026-09-10T12:00:00","likes":10,...}]
   created_at 也接受 "2h"、"30m"、"3d" 这类相对写法
2) 纯文本：每行一条，竖线分隔
   用户名 | 正文 | 2h | 128
   最后两个字段（相对时间、互动数）可省略，省略时按"刚刚"和 0 处理
"""

import json
import re
from datetime import datetime, timedelta

from core.models import Post
from sources.base import PostSource

RELATIVE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$", re.I)

UNIT_MINUTES = {
    "m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1,
    "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60,
    "d": 1440, "day": 1440, "days": 1440,
}


def parse_when(value, default_minutes: int = 0) -> datetime:
    """把 '2h' / '30m' / '3d' / ISO 字符串 解析成时间"""
    now = datetime.now()
    if value in (None, ""):
        return now - timedelta(minutes=default_minutes)
    s = str(value).strip()
    m = RELATIVE_RE.match(s)
    if m:
        return now - timedelta(minutes=float(m.group(1)) * UNIT_MINUTES[m.group(2).lower()])
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return now - timedelta(minutes=default_minutes)


class PasteSource(PostSource):
    name = "paste"

    def __init__(self, raw: str = ""):
        self.raw = raw or ""

    # ------------------------------------------------------------ 解析
    def parse(self, raw: str = None) -> list:
        text = (raw if raw is not None else self.raw).strip()
        if not text:
            return []

        # 尝试 JSON
        if text.lstrip().startswith("["):
            return self._parse_json(text)
        if text.lstrip().startswith("{"):
            return self._parse_json("[" + text + "]")
        return self._parse_text(text)

    def _mk(self, i, author, content, when, likes, rts, replies):
        created = parse_when(when, default_minutes=i)
        return Post(
            id=f"imp_{i}_{abs(hash((author, content))) % 100000}",
            author_handle=str(author).lstrip("@") or "unknown",
            author_name=str(author).lstrip("@") or "unknown",
            text=str(content).strip(),
            created_at=created.isoformat(timespec="seconds"),
            likes=int(likes or 0),
            retweets=int(rts or 0),
            replies=int(replies or 0),
            quotes=0,
            url="",
            source="paste",
        )

    def _parse_json(self, text: str) -> list:
        try:
            data = json.loads(text)
        except Exception as e:
            raise ValueError(f"JSON 解析失败：{e}")
        out = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            out.append(self._mk(
                i,
                item.get("author") or item.get("author_handle") or item.get("handle") or "unknown",
                item.get("text") or item.get("content") or "",
                item.get("created_at") or item.get("time") or "",
                item.get("likes", 0),
                item.get("retweets", 0),
                item.get("replies", 0),
            ))
        return out

    def _parse_text(self, text: str) -> list:
        out = []
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            author = parts[0]
            content = parts[1] if len(parts) > 1 else ""
            when = parts[2] if len(parts) > 2 else ""
            likes = parts[3] if len(parts) > 3 else 0
            if not content:
                continue
            out.append(self._mk(i, author, content, when, likes, 0, 0))
        return out

    # ------------------------------------------------------------ 取数
    def fetch(self, handles: list, since: datetime, until: datetime) -> list:
        posts = self.parse()
        wanted = {h.lower().lstrip("@") for h in (handles or [])}
        out = []
        for p in posts:
            if wanted and p.author_handle.lower() not in wanted:
                continue
            try:
                t = datetime.fromisoformat(p.created_at)
            except Exception:
                continue
            if since <= t <= until:
                out.append(p)
        out.sort(key=lambda x: x.created_at, reverse=True)
        return out
