"""真实 X (Twitter) API 数据源 —— 预留，本次不实现请求逻辑

接口与返回结构都已定义好，填入凭证后即可启用。
需要预留的配置项写在 config.DEFAULT_SETTINGS 里。

真实接入时需要用到的 X API v2 能力对照：
    用户名 -> 用户 ID   GET /2/users/by/username/{username}
    批量取用户          GET /2/users?usernames=a,b,c   （一次最多 100 个）
    取某用户推文        GET /2/users/{id}/tweets       （带 start_time / end_time 过滤）
    发推               POST /2/tweets                 （发布层用）
"""

from datetime import datetime

from config import Settings
from core.models import Post
from sources.base import PostSource


class XApiSource(PostSource):
    name = "x_api"

    def available(self) -> tuple:
        s = Settings.load()
        if not (s.get("x_bearer_token") or "").strip():
            return False, "尚未接入真实 X 数据：需要在设置页填入 X 的访问凭证"
        return True, ""

    def fetch(self, handles: list, since: datetime, until: datetime) -> list:
        ok, msg = self.available()
        if not ok:
            raise NotImplementedError(msg)

        # ---- 以下是真实接入时要填的逻辑（示意，未启用）----
        # 1. 用 GET /2/users/by/username/{h} 把用户名换成 user_id（注意缓存，避免重复请求）
        # 2. 用 GET /2/users/{id}/tweets?start_time=...&end_time=...&tweet.fields=...
        #    取回 public_metrics（like_count / retweet_count / reply_count / quote_count）
        # 3. 把返回体映射成 core.models.Post
        #
        # resp = requests.get(
        #     f"{BASE}/users/by/username/{handle}",
        #     headers={"Authorization": f"Bearer {token}"},
        # )
        # ...
        raise NotImplementedError(
            "X API 接口已预留但尚未实现。当前请使用内置模拟数据或粘贴导入。"
        )

    # 供未来实现使用的字段映射参考
    @staticmethod
    def map_tweet(tweet: dict, handle: str) -> Post:
        m = tweet.get("public_metrics", {}) or {}
        return Post(
            id=str(tweet.get("id", "")),
            author_handle=handle,
            text=tweet.get("text", ""),
            created_at=tweet.get("created_at", ""),
            likes=m.get("like_count", 0),
            retweets=m.get("retweet_count", 0),
            replies=m.get("reply_count", 0),
            quotes=m.get("quote_count", 0),
            url=f"https://x.com/{handle}/status/{tweet.get('id', '')}",
            source="x_api",
        )
