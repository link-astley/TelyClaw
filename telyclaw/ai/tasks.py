"""AI 任务编排

每个任务失败时抛出 ai.client.AIError，由上层决定如何提示。
解析失败会自动重试一次；仍然失败才抛错。
**绝不返回预写内容冒充 AI 输出。**
"""

from ai import prompts
from ai.client import AIError, chat, parse_json_safely
from config import RISK_CATEGORIES

SAFETY_BATCH = 50          # 一次请求判定的帖子数，超了就分批


def _call(prompt_messages, api_key, retry_on_parse=True, **kw):
    """调用一次；解析失败自动重试一次"""
    content = chat(prompt_messages, api_key, **kw)
    try:
        return parse_json_safely(content)
    except AIError:
        if not retry_on_parse:
            raise
        content = chat(prompt_messages, api_key, **kw)
        return parse_json_safely(content)


def _repr_posts(posts, n=4):
    """取代表帖子，压缩成简短结构发给模型"""
    out = []
    for p in posts[:n]:
        out.append({
            "author": p.author_handle,
            "text": p.text[:220],
            "likes": p.likes,
            "retweets": p.retweets,
            "replies": p.replies,
        })
    return out


def _score(item, key):
    """取 AI 打的 0~100 分；缺失或非法时返回 None（表示 AI 没给出这一维）"""
    try:
        v = float(item.get(key))
    except (TypeError, ValueError):
        return None
    if v != v:
        return None
    return round(max(0.0, min(100.0, v)), 1)


# ------------------------------------------------------------------ 0. 内容安全检查
def check_safety(posts: list, api_key: str) -> dict:
    """批量判定窗口内帖子的内容安全风险。

    返回 {post_id: {"risky": bool, "categories": [...], "reason": "..."}}
    只做「标记」，不删帖 —— 是否跟进由人决定。
    失败时抛 AIError，由上层标成"未执行安全检查"。
    """
    flags = {}
    for i in range(0, len(posts), SAFETY_BATCH):
        chunk = posts[i:i + SAFETY_BATCH]
        payload = [{
            "post_id": p.id,
            "author": p.author_handle,
            "text": p.text[:300],
        } for p in chunk]

        data = _call(prompts.safety_check(payload, RISK_CATEGORIES), api_key,
                     response_format_json=True, temperature=0)

        for item in (data or {}).get("flags", []):
            pid = str(item.get("post_id", "")).strip()
            if not pid:
                continue
            cats = [c for c in (item.get("categories") or []) if c in RISK_CATEGORIES]
            risky = bool(item.get("risky")) or bool(cats)
            flags[pid] = {
                "risky": risky,
                "categories": cats,
                "reason": (item.get("reason") or "").strip()[:60],
            }

    if not flags:
        raise AIError("parse", "模型没有返回有效的安全检查结果")
    return flags


# ------------------------------------------------------------------ 1. 话题命名 + 摘要
def label_topics(topics, clusters_by_id, positioning, api_key):
    payload = []
    for t in topics:
        c = clusters_by_id.get(t.id, {})
        posts = c.get("posts", [])
        payload.append({
            "group_id": t.id,
            "high_freq_words": [k for k in t.keywords],
            "post_count": t.post_count,
            "author_count": t.author_count,
            "sample_posts": _repr_posts(posts),
        })

    data = _call(prompts.topic_summary(payload, positioning), api_key,
                 response_format_json=True)

    mapping = {}
    for item in (data or {}).get("topics", []):
        gid = str(item.get("group_id", ""))
        if gid:
            mapping[gid] = item

    for t in topics:
        item = mapping.get(t.id)
        if not item:
            continue
        name = (item.get("name") or "").strip()
        summary = (item.get("summary") or "").strip()
        if name:
            t.label = name
            t.named_by_ai = True
        if summary:
            t.summary = summary
        # 内容性三维度（玩梗 / 搞笑 / Drama）：AI 给的才算，没给就保持 None
        for key in ("meme", "funny", "drama"):
            v = _score(item, key)
            if v is not None:
                setattr(t, key, v)
    return topics


# ------------------------------------------------------------------ 2. 排名理由
def add_rank_reasons(topics, api_key):
    payload = [{
        "topic_id": t.id,
        "rank": t.rank,
        "name": t.label,
        "summary": t.summary,
        "heat": t.heat,
        "mention_count": t.post_count,
        "author_count": t.author_count,
        "engagement_total": t.engagement_total,
        "freshness": t.freshness,
        "velocity_倍数": t.velocity,
        "unsat_未饱和度": t.unsat,
        "meme_玩梗": t.meme,
        "funny_搞笑": t.funny,
        "drama_争论": t.drama,
        "risk_count": t.risk_count,
    } for t in topics]

    data = _call(prompts.rank_reason(payload), api_key, response_format_json=True)

    mapping = {}
    for item in (data or {}).get("reasons", []):
        tid = str(item.get("topic_id", ""))
        if tid:
            mapping[tid] = (item.get("reason") or "").strip()

    for t in topics:
        r = mapping.get(t.id)
        if r:
            t.rank_reason = r
    return topics


# ------------------------------------------------------------------ 3. Top 精选
def pick_top(topics, positioning, api_key, top_n=3):
    """
    返回 [{"topic_id":..., "reason":..., "recommended":True}, ...]
    失败时抛 AIError，由上层降级为"按热度取前 N"
    """
    payload = [{
        "topic_id": t.id,
        "rank": t.rank,
        "name": t.label,
        "summary": t.summary,
        "heat": t.heat,
        "mention_count": t.post_count,
        "author_count": t.author_count,
        "keywords": t.keywords,
        "risk_count": t.risk_count,
    } for t in topics]

    data = _call(prompts.top_selection(payload, positioning, top_n), api_key,
                 response_format_json=True)

    valid = {t.id for t in topics}
    picks, seen = [], set()
    for item in (data or {}).get("picks", []):
        tid = str(item.get("topic_id", ""))
        if tid in valid and tid not in seen:
            seen.add(tid)
            picks.append({
                "topic_id": tid,
                "reason": (item.get("reason") or "").strip(),
                "recommended": True,
            })
    if not picks:
        raise AIError("parse", "模型没有返回有效的推荐")
    return picks[:top_n]


# ------------------------------------------------------------------ 4. 内容角度
def gen_angles(topic, posts, positioning, api_key):
    payload = {
        "topic_name": topic.label,
        "summary": topic.summary,
        "keywords": topic.keywords,
        "mention_count": topic.post_count,
        "author_count": topic.author_count,
        "sample_posts": _repr_posts(posts, 5),
    }
    data = _call(prompts.content_angles(payload, positioning), api_key,
                 response_format_json=True)

    ANGLE_TYPE = {
        "hot_take": ("Hot Take", "反共识 / 有立场"),
        "educational": ("Educational", "讲清楚这件事"),
        "product": ("TelyClaw Product Angle", "产品角度"),
    }
    TYPE_ALIAS = {
        "hot_take": "hot_take", "hottake": "hot_take", "hot take": "hot_take",
        "take": "hot_take", "反共识": "hot_take", "观点": "hot_take",
        "educational": "educational", "education": "educational",
        "edu": "educational", "科普": "educational", "教育": "educational",
        "product": "product", "telyclaw": "product", "telyclaw product angle": "product",
        "product angle": "product", "产品": "product", "产品角度": "product",
    }
    ORDER = ["hot_take", "educational", "product"]

    angles = []
    for i, item in enumerate((data or {}).get("angles", [])[:3]):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        raw = (item.get("type") or "").strip().lower()
        atype = TYPE_ALIAS.get(raw, TYPE_ALIAS.get(raw.replace("-", " ").replace("_", " ")))
        # 模型没按约定给 type 时，按返回顺序兜底，保证三类齐全
        if atype not in ANGLE_TYPE and i < len(ORDER):
            atype = ORDER[i]
        label, hint = ANGLE_TYPE.get(atype, ("角度", ""))
        angles.append({
            "id": f"{topic.id}_a{i}",
            "topic_id": topic.id,
            "type": atype or f"other{i}",
            "type_label": label,
            "type_hint": hint,
            "title": title,
            "rationale": (item.get("rationale") or "").strip(),
            "hook": (item.get("hook") or "").strip(),
        })
    if not angles:
        raise AIError("parse", "模型没有返回有效的角度")
    return angles


# ------------------------------------------------------------------ 5. 写稿
def gen_posts(topic, angle, posts, positioning, api_key):
    payload = {
        "topic_name": topic.label,
        "topic_summary": topic.summary,
        "angle_type": angle.get("type", ""),
        "angle_type_label": angle.get("type_label", ""),
        "angle_title": angle.get("title", ""),
        "angle_rationale": angle.get("rationale", ""),
        "angle_hook": angle.get("hook", ""),
        "sample_posts": _repr_posts(posts, 5),
    }

    def _ask():
        return _call(prompts.write_posts(payload, positioning), api_key,
                     response_format_json=True, temperature=0.9)

    STYLE_NAME = {
        "opinion": "犀利观点型",
        "listicle": "数据清单型",
        "question": "提问互动型",
        "观点型": "犀利观点型",
        "清单型": "数据清单型",
        "提问型": "提问互动型",
    }

    def _parse(data):
        out = []
        for i, item in enumerate((data or {}).get("posts", [])[:3]):
            content = (item.get("content") or "").strip()
            if not content:
                continue
            style_raw = (item.get("style") or "").strip()
            out.append({
                "style": STYLE_NAME.get(style_raw, STYLE_NAME.get(style_raw.lower(), style_raw or f"方案 {i+1}")),
                "content": content,
                "value_add": (item.get("value_add") or "").strip(),
            })
        return out

    out = _parse(_ask())
    # 产品角度必须真的带出产品；没有就再要一次（仍是真实 AI 输出，不用预写内容顶替）
    if (angle.get("type") == "product") and out and not any(
            "telyclaw" in o["content"].lower() for o in out):
        retry = _parse(_ask())
        if retry:
            out = retry
    if not out:
        raise AIError("parse", "模型没有返回可用的帖子")
    return out
