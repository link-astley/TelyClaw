"""热度分计算（九维加权）

    互动 20% + 账号 20% + 新鲜度 15% + 升温 10%
    + 玩梗 5% + 搞笑 5% + Drama 5% + 提及 15% + 未饱和 5% = 100%

其中：
- 互动 / 账号 / 提及 / 新鲜度 / 升温 / 未饱和：规则计算，永远有值
- 玩梗 / 搞笑 / Drama：AI 打分，AI 未参与时取中性值 50
  （所有话题取值相同 → 归一化后都一样 → 该维度对排序无影响）

口径红线：每个维度都在"当前这一次检测、当前这个窗口内"做归一化，
因此不同窗口之间的分数不可比。切换窗口时整张榜单会重新计算。
"""

import math
from datetime import datetime, timedelta

from core.models import Topic

NEUTRAL = 50.0          # AI 未参与时内容性三维度的中性值

WEIGHT_KEYS = ["engagement", "breadth", "freshness", "velocity",
               "meme", "funny", "drama", "mention", "unsat"]
WEIGHT_DEFAULTS = {"engagement": .20, "breadth": .20, "freshness": .15, "velocity": .10,
                   "meme": .05, "funny": .05, "drama": .05, "mention": .15, "unsat": .05}

# 归一化字段 -> 权重键
PAIRS = {
    "s_engagement": "engagement", "s_breadth": "breadth", "s_freshness": "freshness",
    "s_velocity": "velocity", "s_meme": "meme", "s_funny": "funny",
    "s_drama": "drama", "s_mention": "mention", "s_unsat": "unsat",
}


# ------------------------------------------------------------------ 原始值
def compute_raw(topic_posts: list, cluster: dict, now: datetime, window_hours: float) -> dict:
    post_count = len(topic_posts)
    engagement_total = sum(p.engagement for p in topic_posts)
    author_count = len({p.author_handle for p in topic_posts})

    # 新鲜度：按互动量加权的平均新鲜度，衰减速度 τ = 窗口长度 / 3
    tau = max(window_hours / 3.0, 0.25)
    num = den = 0.0
    parsed = []
    for p in topic_posts:
        try:
            t = datetime.fromisoformat(p.created_at)
        except Exception:
            continue
        parsed.append(t)
        dt_hours = max((now - t).total_seconds() / 3600.0, 0.0)
        w = max(p.engagement, 1)          # 互动为 0 的帖子也给最小权重
        num += w * math.exp(-dt_hours / tau)
        den += w
    freshness = (num / den) if den else 0.0

    # 升温程度：最近 1/4 窗口内的提及占比 ÷ 均匀分布预期（25%）
    #   例：24h 窗口里 60% 的帖子集中在最近 6 小时 → 0.6 / 0.25 = 2.4 倍
    #   小样本时向 1.0 收缩，避免 2 条帖子就被判成"暴涨"
    cut = now - timedelta(hours=window_hours / 4.0)
    recent = sum(1 for t in parsed if t >= cut)
    if post_count:
        ratio = (recent / post_count) / 0.25
        shrink = min(1.0, post_count / 6.0)
        velocity = 1.0 + (ratio - 1.0) * shrink
    else:
        velocity = 1.0
    velocity = max(0.0, min(4.0, velocity))

    # 未饱和机会：账号数 ÷ 提及数
    #   人多帖少 = 话题刚扩散开、还没被消费完；人少帖多 = 少数账号在刷屏
    unsat = (author_count / post_count * 100) if post_count else 0.0

    return {
        "post_count": post_count,
        "engagement_total": engagement_total,
        "author_count": author_count,
        "freshness": round(freshness * 100, 1),     # 0~100
        "velocity": round(velocity, 2),
        "unsat": round(unsat, 1),
    }


# ------------------------------------------------------------------ 归一化
def _minmax(values: list) -> list:
    """归一化到 0~100；全部相等时统一给 100（这样该维度对排序没有影响）"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [100.0] * len(values)
    return [(v - lo) / (hi - lo) * 100.0 for v in values]


def _v(t, name):
    """AI 打的内容性分数；AI 未参与时取中性值"""
    v = getattr(t, name, None)
    return NEUTRAL if v is None else v


def score_topics(topics: list, weights: dict) -> list:
    """对一批 Topic 计算各维度归一化分与热度分，并排名"""
    if not topics:
        return []

    scores = {
        "s_mention": _minmax([t.post_count for t in topics]),
        "s_engagement": _minmax([t.engagement_total for t in topics]),
        "s_breadth": _minmax([t.author_count for t in topics]),
        "s_freshness": _minmax([t.freshness for t in topics]),
        "s_velocity": _minmax([t.velocity for t in topics]),
        "s_unsat": _minmax([t.unsat for t in topics]),
        "s_meme": _minmax([_v(t, "meme") for t in topics]),
        "s_funny": _minmax([_v(t, "funny") for t in topics]),
        "s_drama": _minmax([_v(t, "drama") for t in topics]),
    }

    w = weights or {}
    wt = {k: float(w.get(k, WEIGHT_DEFAULTS[k])) for k in WEIGHT_KEYS}
    total_w = sum(wt.values()) or 1.0

    for i, t in enumerate(topics):
        for attr, arr in scores.items():
            setattr(t, attr, round(arr[i], 1))
        t.heat = round(sum(scores[a][i] * wt[k] for a, k in PAIRS.items()) / total_w, 1)

    topics.sort(key=lambda x: (-x.heat, -x.engagement_total))
    for i, t in enumerate(topics):
        t.rank = i + 1
    return topics


def build_topics(clusters: list, now: datetime, window_hours: float) -> list:
    """把粗簇转成 Topic 对象（含全部规则维度），话题名暂时用高频标签"""
    out = []
    for c in clusters:
        members = c["posts"]
        raw = compute_raw(members, c, now, window_hours)
        tag = c.get("label_hint") or (c["tag_freq"][0][0] if c["tag_freq"] else (c["tags"][0] if c["tags"] else "未命名"))
        out.append(Topic(
            id=c["cluster_id"],
            label=tag.lstrip("#"),
            keywords=[t for t, _ in c["tag_freq"][:6]],
            post_ids=c["post_ids"],
            post_count=raw["post_count"],
            engagement_total=raw["engagement_total"],
            author_count=raw["author_count"],
            freshness=raw["freshness"],
            velocity=raw["velocity"],
            unsat=raw["unsat"],
        ))
    return out
