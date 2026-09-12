"""检测流水线编排

一次"立即检测"的完整流程：
    取数 -> 安全检查 -> 抽词 -> 粗聚类 -> 打分排序
          -> (AI 命名/摘要 + 玩梗/搞笑/Drama 打分)
          -> 重新打分排序 -> (AI 排名理由) -> (AI 精选)

设计要点：AI 只是"锦上添花"的几步。AI 不可用时，取数/聚类/打分/榜单照常产出，
页面不会因为拿不到 AI 结果就空掉。
内容性三维度由 AI 打分，所以拿到 AI 结果后要**再算一次分**，
否则这 15% 权重等于没用。
"""

from datetime import datetime, timedelta

from config import WINDOWS, Settings
from core.cluster import build_coarse_clusters
from core.scoring import build_topics, score_topics
from sources.mock_source import MockSource
from sources.paste_source import PasteSource
from sources.x_api_source import XApiSource

WINDOW_LABEL = {"1h": "过去 1 小时", "4h": "过去 4 小时", "8h": "过去 8 小时",
                "24h": "过去 24 小时", "3d": "过去 3 天"}

TOP_N = 3


def get_source(name: str = None, seed: int = 0, paste_raw: str = ""):
    """按配置取对应的取数实现（换真实 X API 只改这里）"""
    s = Settings.load()
    name = name or s.get("source", "mock")
    if name == "x_api":
        return XApiSource()
    if name == "paste":
        return PasteSource(paste_raw or s.get("paste_raw", ""))
    return MockSource(seed=seed or s.get("mock_seed", 0))


def run_scan(handles: list, window: str = "24h", source_name: str = None,
             seed: int = 0, paste_raw: str = "", use_ai: bool = True) -> dict:
    window = window if window in WINDOWS else "24h"
    hours = WINDOWS[window]
    now = datetime.now()
    since = now - timedelta(hours=hours)

    settings = Settings.load()
    api_key = (settings.get("deepseek_api_key") or "").strip()
    positioning = settings.get("positioning", "")

    result = {
        "ok": True,
        "window": window,
        "window_label": WINDOW_LABEL.get(window, window),
        "window_hours": hours,
        "generated_at": now.isoformat(timespec="seconds"),
        "handles": handles,
        "post_count": 0,
        "topics": [],
        "posts_by_topic": {},
        "selection": [],
        "ai": {"ok": True, "errors": []},
        "notice": "",
    }

    # 安全检查状态：skip=没开 AI / ok=已检查 / failed=调用失败 / unchecked=没执行
    result["safety"] = {
        "state": "unchecked",
        "checked": False,
        "checked_count": 0,
        "risky_post_count": 0,
        "risky_topic_count": 0,
        "message": "未执行安全检查",
    }

    # ---------------------------------------------------------- 1. 取数
    source = get_source(source_name, seed, paste_raw)
    avail, msg = source.available()
    if not avail:
        result["ok"] = False
        result["notice"] = msg
        return result

    try:
        posts = source.fetch(handles, since, now)
    except NotImplementedError as e:
        result["ok"] = False
        result["notice"] = str(e)
        return result
    except Exception as e:
        result["ok"] = False
        result["notice"] = f"取数失败：{e}"
        return result

    result["post_count"] = len(posts)
    if not posts:
        result["notice"] = f"{result['window_label']}内没有抓到任何帖子，换个长一点的窗口试试"
        return result

    # ---------------------------------------------------------- 1.5 内容安全检查（AI）
    # 只做标记、不删帖；话题保留，由人决定要不要跟进
    risk_by_post = {}
    if use_ai and api_key:
        try:
            from ai import tasks
            risk_by_post = tasks.check_safety(posts, api_key)
            result["safety"].update({
                "state": "ok", "checked": True,
                "checked_count": len(posts),
                "risky_post_count": sum(1 for v in risk_by_post.values() if v["risky"]),
                "message": "",
            })
        except Exception as e:
            result["safety"].update({
                "state": "failed",
                "message": "安全检查未执行：" + (getattr(e, "message", None) or str(e)),
            })
            result["ai"]["ok"] = False
            result["ai"]["errors"].append(_err_payload(e))
    elif not api_key:
        result["safety"]["message"] = "未执行安全检查（没填 AI 密钥）"
    else:
        result["safety"]["state"] = "skip"
        result["safety"]["message"] = "未执行安全检查（本次未启用 AI）"

    # 真要排除就把有风险的帖子拿掉（默认只标记不排除）
    if settings.get("exclude_risky", False) and risk_by_post:
        posts = [p for p in posts if not risk_by_post.get(p.id, {}).get("risky")]
        result["post_count"] = len(posts)
        if not posts:
            result["notice"] = "窗口内的帖子全部被判定为有风险，已全部排除"
            return result

    # ---------------------------------------------------------- 2~4. 聚类 + 打分 + 排序
    clusters = build_coarse_clusters(posts)
    topics = build_topics(clusters, now, hours)
    topics = score_topics(topics, settings.get("weights", {}))

    clusters_by_id = {c["cluster_id"]: c for c in clusters}

    def _post_dict(p):
        d = p.to_dict()
        r = risk_by_post.get(p.id)
        d["risk"] = r or ({"risky": False, "categories": [], "reason": ""}
                          if result["safety"]["checked"] else None)
        return d

    posts_by_topic = {
        c["cluster_id"]: [_post_dict(p) for p in sorted(
            c["posts"], key=lambda x: -x.engagement)[:8]]
        for c in clusters
    }
    result["posts_by_topic"] = posts_by_topic

    # 把风险汇总到话题上
    for c in clusters:
        cats, n = set(), 0
        for p in c["posts"]:
            info = risk_by_post.get(p.id)
            if info and info["risky"]:
                n += 1
                cats.update(info["categories"])
        for t in topics:
            if t.id == c["cluster_id"]:
                t.risk_count = n
                t.risk_categories = sorted(cats)
    if result["safety"]["checked"]:
        result["safety"]["risky_topic_count"] = sum(1 for t in topics if t.risk_count)

    # ---------------------------------------------------------- 5. AI：命名 + 摘要 + 内容性打分
    if use_ai:
        if not api_key:
            from ai.client import AIError
            result["ai"]["ok"] = False
            result["ai"]["errors"].append(_err_payload(AIError("no_key")))
        else:
            try:
                from ai import tasks
                topics = tasks.label_topics(topics, clusters_by_id, positioning, api_key)
                # 拿到玩梗/搞笑/Drama 之后必须重算，否则这 15% 权重不生效
                topics = score_topics(topics, settings.get("weights", {}))
                result["ai"]["content_dims"] = any(
                    t.meme is not None for t in topics)
            except Exception as e:
                result["ai"]["ok"] = False
                result["ai"]["errors"].append(_err_payload(e))

    # ---------------------------------------------------------- 6. AI：排名理由
    if use_ai and api_key:
        try:
            from ai import tasks
            topics = tasks.add_rank_reasons(topics, api_key)
        except Exception as e:
            result["ai"]["ok"] = False
            result["ai"]["errors"].append(_err_payload(e))

    # ---------------------------------------------------------- 7. AI：Top 精选
    if use_ai and api_key:
        try:
            from ai import tasks
            result["selection"] = tasks.pick_top(topics, positioning, api_key, TOP_N)
        except Exception as e:
            result["ai"]["ok"] = False
            result["ai"]["errors"].append(_err_payload(e))
            result["selection"] = _fallback_selection(topics)
    else:
        result["selection"] = _fallback_selection(topics)

    # 同一类错误只提示一次，避免界面上刷出一排重复的横幅
    seen, uniq = set(), []
    for e in result["ai"]["errors"]:
        if e["code"] in seen:
            continue
        seen.add(e["code"])
        uniq.append(e)
    result["ai"]["errors"] = uniq

    # 排名理由缺失时给一个可读的兜底文案（这是"解释"，不是"AI 输出"）
    for t in topics:
        if not t.rank_reason:
            t.rank_reason = _rule_reason(t)

    result["topics"] = [t.to_dict() for t in topics]
    return result


# ------------------------------------------------------------------ 兜底文案
def _err_payload(e) -> dict:
    code = getattr(e, "code", "unknown")
    from ai.client import AIError
    msg = getattr(e, "message", None) or AIError.CODES.get(code, AIError.CODES["unknown"])
    return {
        "code": code,
        "message": msg,
        "retryable": bool(getattr(e, "retryable", True)),
        "detail": str(getattr(e, "detail", ""))[:200],
    }


def _fallback_selection(topics) -> list:
    """AI 不可用时按热度取前 N（明确标注不是 AI 推荐）"""
    return [{
        "topic_id": t.id,
        "reason": f"AI 未参与推荐，按热度分取第 {i+1} 名（{t.label}，热度 {t.heat}）",
        "recommended": False,
    } for i, t in enumerate(topics[:TOP_N])]


def _rule_reason(t) -> str:
    """规则生成的排名说明（明确是统计口径，不是 AI 判断）"""
    vel = f"{t.velocity:.2f}×" if t.velocity >= 1 else f"{t.velocity:.2f}×"
    return (
        f"共 {t.post_count} 条提及、覆盖 {t.author_count} 个账号、"
        f"互动总量 {t.engagement_total}、新鲜度 {t.freshness}、升温 {vel}、"
        f"未饱和 {t.unsat}，加权后热度 {t.heat}"
        f"（AI 未参与，此处为统计口径说明；玩梗/搞笑/Drama 未打分，按中性值处理）"
    )
