"""Prompt 模板

所有 Prompt 都强制要求返回固定结构的 JSON，并在解析失败时重试一次。
"""

DEMO_NOTICE = "（说明：以下数据为演示用的模拟内容，不代表真实用户的言论。）"

# 产品简介：只在「生成内容角度 / 写稿」时用，让模型知道 TelyClaw 是什么
TELYCLAW_BRIEF = (
    "TelyClaw 是一个「X 热点雷达」：它监控用户指定的一批 X 账号，"
    "在选定时间窗口内抓取他们的发帖，自动聚出正在被讨论的话题，"
    "按热度打分排名，再用 AI 生成可直接发布的内容。"
    "目标用户是做增长和内容运营的人，"
    "核心场景是「比别人更早发现值得跟进的热点，并且更快写出能发的帖子」。"
)


# ------------------------------------------------------------------ 0. 内容安全检查
def safety_check(posts_payload: list, categories: list) -> list:
    """批量判定一批帖子是否命中风险类别

    只标"明确命中"的，正常的技术争论 / 产品吐槽 / 商业批评不算风险。
    """
    cat_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(categories))
    sys_msg = (
        "你是一个内容安全审核助手。用户会给你一批社交媒体帖子，"
        "请你逐条判断它们是否属于下列风险类别之一：\n"
        f"{cat_list}\n"
        "要求：\n"
        "1. 只把「明确命中」的判为有风险。正常的技术争论、产品吐槽、商业批评、"
        "行业分歧都不算风险，不要过度敏感\n"
        "2. risky 填 true 或 false；categories 只能从上面 7 个类别里原样选取（数组，可为空）\n"
        "3. reason 用中文一句话说明为什么算风险，不超过 25 字；无风险时留空\n"
        "4. 每一条帖子都必须出现在结果里，包括没有风险的（risky=false、categories=[]、reason=\"\"）\n"
        "5. 严格返回 JSON：{\"flags\":[{\"post_id\":\"p1\",\"risky\":false,\"categories\":[],\"reason\":\"\"}]}\n"
        "6. 不要返回任何 JSON 之外的内容"
    )
    user = (
        f"{DEMO_NOTICE}\n\n"
        f"以下是 {len(posts_payload)} 条帖子：\n"
        + json_dumps(posts_payload)
    )
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user},
    ]


# ------------------------------------------------------------------ 1. 识别话题 + 摘要
def topic_summary(clusters_payload: list, positioning: str) -> list:
    sys_msg = (
        "你是一个社交媒体的热点分析助手。用户会给你若干组「关键词相近的帖子」，"
        "请你判断它们各自在讲什么，并给出话题名和一句话摘要。\n"
        "要求：\n"
        "1. 话题名用中文，6~14 个字，要具体，不要写「科技动态」这种空话\n"
        "2. 摘要用中文一句话，30~50 字，说清这件事是什么、争论点在哪\n"
        "3. 如果两个组其实在讲同一件事，就在 merge_with 里填上对方组号（数组，可为空）\n"
        "4. 额外给三个 0~100 的整数分，用于评估这个话题的内容传播潜力：\n"
        "   meme  = 玩梗潜力：这个话题容不容易被做成梗、段子、二创\n"
        "   funny = 搞笑度：内容本身有没有幽默、反差、荒诞感\n"
        "   drama = 争论程度：观点分歧和火药味有多强（越强越容易引发回复和转发）\n"
        "   打分要有区分度，不要全部给 50；三个分之间互不相同也可以\n"
        "5. 严格返回 JSON：{\"topics\":[{\"group_id\":\"g0\",\"name\":\"...\",\"summary\":\"...\",\"merge_with\":[],\"meme\":70,\"funny\":40,\"drama\":85}]}\n"
        "6. 不要返回任何 JSON 之外的内容"
    )
    user = (
        f"用户账号定位：{positioning}\n\n"
        f"{DEMO_NOTICE}\n\n"
        f"以下是 {len(clusters_payload)} 组帖子：\n"
        + json_dumps(clusters_payload)
    )
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user},
    ]


# ------------------------------------------------------------------ 2. 排名理由
def rank_reason(rank_payload: list) -> list:
    sys_msg = (
        "你是一个热点排行榜的编辑。用户会给你已经排好序的话题及其各项数据，"
        "请你为每个话题写一句「为什么排在这个位置」的理由。\n"
        "要求：\n"
        "1. 理由必须用上具体的数字（提及条数、账号数、互动量、新鲜度里的具体值）\n"
        "2. 中文，30~55 字，口语化，不要写成数据报告\n"
        "3. 排第一的要说清「凭什么第一」；排后面的可以点出它的短板\n"
        "4. 严格返回 JSON：{\"reasons\":[{\"topic_id\":\"c0\",\"reason\":\"...\"}]}\n"
        "5. 不要返回任何 JSON 之外的内容"
    )
    user = DEMO_NOTICE + "\n\n" + json_dumps(rank_payload)
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user},
    ]


# ------------------------------------------------------------------ 3. Top 精选
def top_selection(select_payload: list, positioning: str, top_n: int = 3) -> list:
    sys_msg = (
        "你是一个内容策略顾问。用户会给你一个热点榜单和「这个账号是做什么的」，"
        f"请你从中挑出最值得该账号跟进的 {top_n} 个热点。\n"
        "要求：\n"
        "1. 不能只看热度，要看和用户账号定位的契合度\n"
        "2. reason 用中文，25~45 字，说明「为什么值得这个账号跟进」，要提到定位里的具体人群或场景\n"
        "3. risk_count 大于 0 的话题一律不要选（内容有风险，交给人工判断）\n"
        "4. 严格返回 JSON：{\"picks\":[{\"topic_id\":\"c0\",\"reason\":\"...\"}]}\n"
        "5. 不要返回任何 JSON 之外的内容"
    )
    user = (
        f"账号定位：{positioning}\n\n"
        f"{DEMO_NOTICE}\n\n"
        "热点榜单：\n" + json_dumps(select_payload)
    )
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user},
    ]


# ------------------------------------------------------------------ 4. 内容角度
def content_angles(topic_payload: dict, positioning: str) -> list:
    sys_msg = (
        "你是一个社交媒体的内容策划。用户会给你一个热点话题和账号定位，"
        "请你给出 3 个内容切入角度。\n"
        "要求：\n"
        "1. 必须返回且只返回 3 个角度，type 固定为下列三种，各一个，顺序也按这个来：\n"
        "   hot_take = Hot Take：反共识，有明确立场，说别人没说或不愿说的\n"
        "   educational = Educational：把这个话题讲清楚，做科普或拆解，给读者信息增量\n"
        "   product = TelyClaw Product Angle：用这个热点当切入点，讲它印证了什么痛点、"
        "TelyClaw 在什么场景下能解决。要像在聊行业，自然带出产品；"
        "不要写成广告，不要罗列功能，不要出现「快来试用」这类话术\n"
        "2. title 中文，8~16 字；rationale 中文 20~40 字，说清这个角度为什么有价值\n"
        "3. hook 是一条英文的开头钩子（一句话，不超过 20 个词），要能抓人\n"
        "4. 三个角度之间的切入点必须明显不同，不要互相重复\n"
        "5. 严格返回 JSON："
        "{\"angles\":[{\"type\":\"hot_take\",\"title\":\"...\",\"rationale\":\"...\",\"hook\":\"...\"}]}\n"
        "6. 不要返回任何 JSON 之外的内容"
    )
    user = (
        f"账号定位：{positioning}\n\n"
        f"TelyClaw 产品简介：{TELYCLAW_BRIEF}\n\n"
        f"{DEMO_NOTICE}\n\n"
        "热点话题：\n" + json_dumps(topic_payload)
    )
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user},
    ]


# ------------------------------------------------------------------ 5. 写稿
def write_posts(draft_payload: dict, positioning: str) -> list:
    is_product = (draft_payload.get("angle_type") or "").strip().lower() == "product"
    special = (
        "本次特别要求：切入角度是 product（TelyClaw Product Angle）。"
        "3 条里至少 1 条必须出现「TelyClaw」这个词，要自然带出——"
        "用它当例子、或用它解决的问题来收尾都行。"
        "一条都没出现 TelyClaw 的，本次任务判为不合格。\n"
        if is_product else ""
    )
    sys_msg = (
        "你是一个 X（原 Twitter）上的内容写手。请根据给定的热点、切入角度和账号定位，"
        "写出 3 条可以直接发布的帖子，风格必须明显不同。\n"
        "三种风格：\n"
        "- opinion：犀利观点型，有明确立场，一开头就抛结论\n"
        "- listicle：数据清单型，用编号列出要点，信息密度高\n"
        "- question：提问互动型，以一个问题开头，引导别人回复\n"
        "红线（最重要）：\n"
        f"{special}"
        "- 绝不能只是转述、改写或总结原帖。每条帖子都必须给出原帖里没有的东西："
        "一个明确立场、一个分析框架、一条可执行的建议，或一个反常识的追问。\n"
        "  自检标准：如果读者只看原帖就能得到这条帖子的全部信息，那这条就不合格。\n"
        "- 不要编造具体数字和引用\n"
        "- 不要写「In today's fast-paced world」「As we all know」这类空话开头\n"
        "其余要求：\n"
        "1. 用英文写（X 上科技圈以英文为主）\n"
        "2. 每条控制在 260 字符以内（X 上限 280，留 20 给发布前微调）；宁可短，不要超\n"
        "3. 可以带 1 个 hashtag，最多 1 个\n"
        "4. 提不提产品以「红线」里的要求为准；提到时不要硬广、不要罗列功能\n"
        "5. value_add 用中文一句话（不超过 25 字）说明这条帖子相对原帖新增了什么，"
        "供人工快速判断它到底有没有加东西\n"
        "6. 严格返回 JSON："
        "{\"posts\":[{\"style\":\"opinion\",\"content\":\"...\",\"value_add\":\"...\"}]}\n"
        "7. 不要返回任何 JSON 之外的内容"
    )
    user = (
        f"账号定位：{positioning}\n\n"
        f"TelyClaw 产品简介：{TELYCLAW_BRIEF}\n\n"
        f"{DEMO_NOTICE}\n\n"
        "任务：\n" + json_dumps(draft_payload)
    )
    return [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user},
    ]


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=1)
