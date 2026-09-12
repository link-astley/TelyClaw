"""数据模型定义"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import hashlib


# ---------------------------------------------------------------- Account

@dataclass
class Account:
    handle: str              # 用户名，不带 @
    display_name: str = ""
    followers: int = 10000
    enabled: bool = True
    note: str = ""
    added_at: str = ""

    @property
    def avatar_color(self) -> str:
        """根据用户名稳定生成一个头像底色，避免联网取图"""
        h = hashlib.md5(self.handle.encode()).hexdigest()
        return "#" + h[:6]

    @property
    def initials(self) -> str:
        base = (self.display_name or self.handle).strip()
        base = base.lstrip("@")
        return base[:2].upper()

    def to_dict(self):
        d = asdict(self)
        d["avatar_color"] = self.avatar_color
        d["initials"] = self.initials
        return d


# ---------------------------------------------------------------- Post

@dataclass
class Post:
    id: str
    author_handle: str
    author_name: str = ""
    text: str = ""
    created_at: str = ""          # ISO 格式时间字符串
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    url: str = ""
    source: str = "mock"          # mock / paste / x_api

    @property
    def engagement(self) -> int:
        """互动总量 = 点赞 + 转发 + 回复 + 引用"""
        return self.likes + self.retweets + self.replies + self.quotes

    def to_dict(self):
        d = asdict(self)
        d["engagement"] = self.engagement
        return d


# ---------------------------------------------------------------- Topic

@dataclass
class Topic:
    id: str
    label: str = ""              # 话题名（AI 命名，未接 AI 时用高频词）
    keywords: list = field(default_factory=list)
    post_ids: list = field(default_factory=list)
    summary: str = ""
    named_by_ai: bool = False

    # 四个规则维度的原始值
    post_count: int = 0
    engagement_total: int = 0
    author_count: int = 0
    freshness: float = 0.0        # 0~100
    velocity: float = 1.0         # 升温倍数，1.0 = 与均匀分布持平，>1 = 正在升温
    unsat: float = 0.0            # 未饱和度 0~100，= 账号数/提及数*100

    # AI 打的内容性三维度（0~100），AI 未参与时为 None
    meme: float = None
    funny: float = None
    drama: float = None

    # 归一化后（0~100）
    s_mention: float = 0.0
    s_engagement: float = 0.0
    s_breadth: float = 0.0
    s_freshness: float = 0.0
    s_velocity: float = 0.0
    s_unsat: float = 0.0
    s_meme: float = 0.0
    s_funny: float = 0.0
    s_drama: float = 0.0

    heat: float = 0.0            # 热度分 0~100
    rank: int = 0
    rank_reason: str = ""

    # 安全检查：话题内被标记风险的帖子数与命中的类别
    risk_count: int = 0
    risk_categories: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------- Angle

@dataclass
class Angle:
    id: str
    topic_id: str
    title: str = ""
    rationale: str = ""          # 为什么这个角度有价值
    hook: str = ""               # 开头钩子

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------- Draft

@dataclass
class Draft:
    id: str
    topic_id: str
    topic_label: str = ""
    angle_id: str = ""
    angle_title: str = ""
    style: str = ""              # 犀利观点型 / 数据清单型 / 提问互动型
    content: str = ""
    edited: bool = False
    status: str = "draft"        # draft / published
    created_at: str = ""
    published_at: str = ""

    def to_dict(self):
        d = asdict(self)
        d["length"] = len(self.content)
        d["over_limit"] = len(self.content) > 280
        return d


# ---------------------------------------------------------------- Selection

@dataclass
class Selection:
    topic_id: str
    reason: str = ""             # AI 给出的契合度理由
    recommended: bool = True     # True=AI 推荐，False=用户手动换入
