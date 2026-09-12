"""话题粗聚类（确定性算法，不调 AI）

两级策略：
  一级：如果帖子里有足够多的 #话题标签，就用 hashtag 作为主信号聚类。
        标签本身就是作者给出的"这条在讲什么"，信号最干净、结果最可预期。
  二级：否则退回关键词共现聚类（粘贴导入的帖子往往没有标签）。

用确定性算法而不是 LLM，是为了保证"同一个输入永远得到同一个结果"——
演示时刷新页面榜单不会乱跳。话题的命名与摘要则交给 AI（见 ai/tasks.py）。
"""

from collections import Counter, defaultdict

from core.keywords import ACRONYM_KEEP, extract_tags

MERGE_THRESHOLD = 0.5       # 一级：两个 hashtag 共现重合度超过这个值就并成一个话题
COVERAGE_THRESHOLD = 0.75   # 二级：新标签被已有簇覆盖的比例，防止通用词把话题粘在一起
CONTAIN_THRESHOLD = 0.7     # 二级：一个簇 70% 以上的帖子都在更大的簇里，就丢掉
MIN_CLUSTER_POSTS = 2
MAX_TOPICS = 12
MAX_SEEDS = 40


def _tag_score(tag: str, df: int) -> float:
    s = float(df)
    if tag.startswith("#"):
        s *= 3.0
    if " " in tag:
        s *= 1.8
    if tag in ACRONYM_KEEP:
        s *= 1.4
    return s


# ------------------------------------------------------------------ 主入口
def build_coarse_clusters(posts: list, max_topics: int = MAX_TOPICS) -> list:
    if not posts:
        return []

    post_tags = {p.id: extract_tags(p.text) for p in posts}

    clusters = _hashtag_clusters(posts, post_tags)
    tier = 1
    if clusters is None:
        clusters = _keyword_clusters(posts, post_tags)
        tier = 2

    clusters = [c for c in clusters if len(c["posts"]) >= MIN_CLUSTER_POSTS]
    clusters = _dedupe(clusters)
    clusters.sort(key=lambda c: (-len(c["posts"]), c["tags"][0]))
    clusters = _cap(clusters, max_topics)

    post_by_id = {p.id: p for p in posts}
    out = []
    for i, c in enumerate(clusters):
        members = [post_by_id[pid] for pid in sorted(c["posts"]) if pid in post_by_id]
        if len(members) < MIN_CLUSTER_POSTS:
            continue
        freq = Counter()
        for m in members:
            for t in post_tags.get(m.id, ()):
                if t in c["tags"]:
                    freq[t] += 1
        label_tag = max(c["tags"], key=lambda t: (_tag_score(t, freq.get(t, 0)), t))
        out.append({
            "cluster_id": f"c{i}",
            "label_hint": label_tag,
            "tier": tier,
            "tags": c["tags"],
            "post_ids": sorted(c["posts"]),
            "posts": members,
            "tag_freq": freq.most_common(8),
        })
    return out


# ------------------------------------------------------------------ 一级：hashtag
def _hashtag_clusters(posts: list, post_tags: dict):
    """返回 None 表示 hashtag 信号不够，应该退回二级"""
    tag_posts = defaultdict(set)
    for pid, tags in post_tags.items():
        for t in tags:
            if t.startswith("#"):
                tag_posts[t].add(pid)

    hashtags = [t for t, ids in tag_posts.items() if len(ids) >= MIN_CLUSTER_POSTS]
    if len(hashtags) < 3:
        return None

    covered = set()
    for t in hashtags:
        covered |= tag_posts[t]
    if len(covered) < 0.5 * len(posts):
        return None

    clusters = []
    for t in sorted(hashtags, key=lambda x: (-len(tag_posts[x]), x)):
        ids = tag_posts[t]
        best, best_ov = None, 0.0
        for c in clusters:
            inter = len(ids & c["posts"])
            if not inter:
                continue
            ov = inter / min(len(ids), len(c["posts"]))
            if ov > best_ov:
                best, best_ov = c, ov
        if best is not None and best_ov >= MERGE_THRESHOLD:
            best["tags"].append(t)
            best["posts"] |= ids
        else:
            clusters.append({"tags": [t], "posts": set(ids)})

    # 把没有命中任何 hashtag 的帖子，按关键词重合度补进最像的那个簇
    for pid, tags in post_tags.items():
        if any(pid in c["posts"] for c in clusters):
            continue
        best_i, best_score = -1, 0.0
        for i, c in enumerate(clusters):
            inter = len(tags & set(c["tags"]))
            if inter > best_score:
                best_i, best_score = i, inter
        if best_i >= 0 and best_score > 0:
            clusters[best_i]["posts"].add(pid)

    return clusters


# ------------------------------------------------------------------ 二级：关键词共现
def _keyword_clusters(posts: list, post_tags: dict):
    n = len(posts)
    df = Counter()
    for tags in post_tags.values():
        for t in tags:
            df[t] += 1

    df_cap = max(3, int(n * 0.6))
    seeds = [t for t in df if MIN_CLUSTER_POSTS <= df[t] <= df_cap]
    if not seeds:
        seeds = [t for t in df if df[t] >= MIN_CLUSTER_POSTS]
    if not seeds:
        return []

    seeds.sort(key=lambda t: (-_tag_score(t, df[t]), t))
    seeds = seeds[:MAX_SEEDS]
    tag_posts = {t: {pid for pid, tags in post_tags.items() if t in tags} for t in seeds}

    clusters = []
    for tag in seeds:
        ids = tag_posts[tag]
        best, best_cov = None, 0.0
        for c in clusters:
            inter = len(ids & c["posts"])
            if not inter:
                continue
            cov = inter / len(ids)          # 新标签的帖子被已有簇覆盖的比例
            if cov > best_cov:
                best, best_cov = c, cov
        if best is not None and best_cov >= COVERAGE_THRESHOLD:
            best["tags"].append(tag)
            best["posts"] |= ids
        else:
            clusters.append({"tags": [tag], "posts": set(ids)})

    # 每条帖子归到最匹配的一个簇
    assigned = [set() for _ in clusters]
    for pid, tags in post_tags.items():
        best_i, best_score = -1, 0.0
        for i, c in enumerate(clusters):
            inter = len(tags & set(c["tags"]))
            if not inter:
                continue
            score = inter + 0.05 * len(c["posts"])
            if score > best_score:
                best_i, best_score = i, score
        if best_i >= 0:
            assigned[best_i].add(pid)
    for c, a in zip(clusters, assigned):
        c["posts"] = a

    return clusters


# ------------------------------------------------------------------ 后处理
def _dedupe(clusters: list) -> list:
    """丢掉被更大的簇高度包含的重复簇"""
    clusters = sorted(clusters, key=lambda c: (-len(c["posts"]), c["tags"][0]))
    keep = []
    for c in clusters:
        dup = False
        for k in keep:
            inter = len(c["posts"] & k["posts"])
            if len(c["posts"]) and inter / len(c["posts"]) >= CONTAIN_THRESHOLD:
                dup = True
                break
        if not dup:
            keep.append(c)
    return keep


def _cap(clusters: list, max_topics: int) -> list:
    if len(clusters) <= max_topics:
        return clusters
    keep, rest = clusters[:max_topics], clusters[max_topics:]
    for c in rest:
        best, best_ov = None, 0.0
        for k in keep:
            inter = len(c["posts"] & k["posts"])
            if not inter:
                continue
            ov = inter / min(len(c["posts"]), len(k["posts"]))
            if ov > best_ov:
                best, best_ov = k, ov
        if best is not None and best_ov >= 0.3:
            best["tags"].extend(c["tags"])
            best["posts"] |= c["posts"]
    return sorted(keep, key=lambda c: (-len(c["posts"]), c["tags"][0]))
