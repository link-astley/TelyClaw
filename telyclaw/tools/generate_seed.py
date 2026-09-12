"""生成模拟帖子数据 data/seed_posts.json

两条硬约束（产品文档 2.2 / 任务清单 1.7 + 2.11）：
1. 时间戳只记"距现在多少分钟"的相对偏移，绝不写死绝对日期
2. 最小窗口（1 小时）内必须能聚出 >= 3 个话题，因此 0~60 分钟内刻意铺 6 个话题簇

设计：每个话题只配 1 个专属 hashtag，保证聚类信号干净、话题数稳定落在 6~12 之间。
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "seed_posts.json"

ACCOUNTS = [
    {"handle": "sama", "display_name": "Sam Altman", "followers": 1850000},
    {"handle": "karpathy", "display_name": "Andrej Karpathy", "followers": 920000},
    {"handle": "ylecun", "display_name": "Yann LeCun", "followers": 780000},
    {"handle": "paulg", "display_name": "Paul Graham", "followers": 1650000},
    {"handle": "naval", "display_name": "Naval", "followers": 2100000},
    {"handle": "levelsio", "display_name": "Pieter Levels", "followers": 610000},
]

# 演示风险识别用的虚构账号（不是真人，专门用来让安全检查能演示出效果）
DEMO_RISK_ACCOUNTS = [
    {"handle": "dailyrant_err", "display_name": "Daily Rant（示例号）", "followers": 2400},
    {"handle": "hot_take_247", "display_name": "Hot Take Bot（示例号）", "followers": 1800},
    {"handle": "thefeed_anon", "display_name": "Anon Feed（示例号）", "followers": 3200},
]

# 刻意混入的风险内容：只挂在上面三个虚构账号名下，不用真实 KOL 的名义
# 时间偏移都 > 60 分钟，保证 1 小时窗口仍然是干净的
RISKY_POSTS = [
    # 政治立场与选举
    (95, "dailyrant_err",
     "Anyone still on the fence about this election is either lying or not paying attention. "
     "There is only one side to be on. #Election2028"),
    (150, "hot_take_247",
     "The 'glitch' in three counties last night wasn't a glitch. Wake up before it's too late. #Election2028"),
    # 未经证实的严重指控 / 针对个人的恶意攻击
    (320, "thefeed_anon",
     "That founder didn't 'step down for health reasons'. Everyone in the valley knows the "
     "runway was fake and the numbers were cooked. #StartupFraud"),
    (640, "thefeed_anon",
     "I'll just say it: he's been quietly running a Ponzi with user deposits for two years. "
     "Mark my words. #StartupFraud"),
    # 明显违法或欺诈内容（混进正常话题里，演示"话题内混入风险帖"）
    (210, "hot_take_247",
     "DM me if you want in on the pre-IPO allocation. Guaranteed 3x in 90 days, "
     "I've done this 40 times. #AICoding"),
]

TOPICS = {
    "ai-coding": {
        "hashtag": "#AICoding",
        "authors": ["karpathy", "levelsio", "sama"],
        "texts": [
            "The best part of AI coding isn't autocomplete, it's that you stop being afraid to start a new file.",
            "Hot take: most devs still write code in their head first, then ask the model to type it. That's not AI coding, that's dictation.",
            "Spent the weekend refactoring a 4-year-old codebase with an AI pair. Deleted 3k lines. Tests still green. Genuinely unsettling.",
            "The skill that matters now isn't syntax, it's taste — knowing which of the 5 generated versions is actually the right one.",
            "Every time someone says models can't do real work I watch a junior ship a full feature in an afternoon.",
            "Pair programming with a model is weirdly similar to pairing with a very fast, very confident intern.",
            "Unpopular opinion: the bottleneck was never typing speed. It was knowing what to build. AI coding just exposed that.",
            "If your AI workflow is copy-paste into a chat window, you're leaving most of the leverage on the table.",
        ],
    },
    "open-models": {
        "hashtag": "#OpenWeights",
        "authors": ["ylecun", "karpathy", "sama"],
        "texts": [
            "Open weights are why the ecosystem moves fast. Every lab that closed up slowed the whole field down.",
            "The gap between open weight models and frontier closed models went from about 18 months to maybe 6. Nobody is pricing that in.",
            "You can fine-tune a small open model on your own data in an afternoon now. That used to be a research project.",
            "People keep asking which open model to use. Wrong question. Ask which one you can actually afford to run 10M times.",
            "If intelligence becomes a commodity, the moat moves to distribution and data. Open weights accelerates exactly that.",
            "Fine-tuning beats prompting the moment you have 500 real examples. Every single time.",
            "The real story of this year isn't model quality, it's that open weights caught up while everyone watched the leaderboard.",
            "Downloading a 70B model to a laptop and having it work offline still feels like a magic trick to me.",
        ],
    },
    "inference-cost": {
        "hashtag": "#InferenceCost",
        "authors": ["sama", "ylecun", "karpathy"],
        "texts": [
            "Inference cost per token dropped another 40% this quarter. Apps that looked unprofitable at last year's prices suddenly work.",
            "Everyone optimizes model quality. Almost nobody optimizes inference cost, and that's where the margin actually lives.",
            "A generation of startups will be built purely because GPU prices fell. Not because the models got smarter.",
            "Latency is a product feature. 200ms feels like a tool; 3 seconds feels like a form submission.",
            "Fun exercise: take your AI feature's monthly token bill and divide by active users. That's your real pricing floor.",
            "The boring truth: most inference cost wins come from shorter prompts, not smaller models.",
            "We're going to look back at today's GPU prices the way we look at 1998 bandwidth prices.",
            "Caching, batching and distillation beat model shopping. Every time I've measured it.",
        ],
    },
    "ai-agents": {
        "hashtag": "#AIAgents",
        "authors": ["sama", "karpathy", "levelsio"],
        "texts": [
            "An agent that can't be trusted with a rollback is a demo, not a product.",
            "Tool calling quietly became the USB-C of agents. Nobody agreed to it, everybody shipped it.",
            "The hard part of agents isn't reasoning, it's knowing when to stop and ask a human.",
            "Every agent demo works on the happy path. The money is in the 40 edge cases nobody films.",
            "Agents need permissions, audit logs and undo. Basically everything we already learned from CI/CD.",
            "I trust agents for research, I don't trust them for writes. That line will move, slowly.",
            "An agent is a model plus tools plus memory plus a very short leash. Ship with the leash first.",
            "The first useful agents won't look like employees. They'll look like cron jobs with judgment.",
        ],
    },
    "indie-hackers": {
        "hashtag": "#IndieHackers",
        "authors": ["levelsio", "naval", "paulg"],
        "texts": [
            "Shipped solo to 12k MRR in 14 months. No team, no funding, no plan. Just a problem I had myself.",
            "The best distribution strategy is still: build something a small group of people is desperate for.",
            "Every founder I know who raised money too early now optimizes for investors instead of users.",
            "You don't need a cofounder to start. You need a cofounder to keep going when it stops being fun.",
            "Bootstrapped means every bad decision costs you personally. Brutal teacher, excellent product discipline.",
            "MRR is a lagging indicator. The leading indicator is how many users would be angry if you shut down tomorrow.",
            "Being small is a strategy, not a stage.",
            "Charge from day one. Free users will tell you they love it and then leave.",
        ],
    },
    "ai-funding": {
        "hashtag": "#AIFunding",
        "authors": ["paulg", "naval", "sama"],
        "texts": [
            "Seed rounds for AI tooling are back to 2021 multiples, but this time with real revenue attached. Different animal.",
            "Raising money is not an accomplishment. It's a decision to sell part of your future optionality.",
            "The best time to raise is when you don't need to. Everyone knows this and everyone ignores it.",
            "Valuations are a story about the future agreed upon by two parties with opposite incentives.",
            "Most AI startups raising right now are selling a wrapper. Some of them will become the real thing. Hard to tell which.",
            "If your pitch deck has a moat slide, you probably don't have a moat.",
            "Watch what founders do with the money, not what they say in the announcement.",
            "The unglamorous truth: most good companies could have been built for a tenth of the raise.",
        ],
    },
    "dev-tools": {
        "hashtag": "#DevTools",
        "authors": ["karpathy", "levelsio", "paulg"],
        "texts": [
            "Developer experience is a growth channel. Every minute saved in setup is a minute spent telling a friend.",
            "The best dev tools feel like they were built by someone who was personally annoyed. Because they were.",
            "Build time under 10 seconds or you've quietly capped how fast your team can think.",
            "Nobody churns from a tool because it lacked a feature. They churn because it made them feel stupid.",
            "Rewrote our CLI in Rust. Cold start went from 800ms to 40ms. Users noticed immediately.",
            "Docs are a product surface. If your quickstart is 6 pages, your quickstart is your churn page.",
            "Every great dev tool I love had one opinionated default that 20% of people hated.",
            "If I need a config file before hello world, I'm already halfway out the door.",
        ],
    },
    "ai-safety": {
        "hashtag": "#AISafety",
        "authors": ["ylecun", "sama", "paulg"],
        "texts": [
            "The safety conversation keeps skipping the boring part: eval suites that actually reflect production traffic.",
            "Regulation written about today's models will be wrong about tomorrow's. Write it about capabilities, not architectures.",
            "Every serious incident I've reviewed had the same root cause: nobody owned the failure path.",
            "Alignment is mostly a product problem. If you can't specify what you want, you can't check you got it.",
            "We should regulate deployment contexts, not model weights. Same model, wildly different risk per use case.",
            "Red teaming that produces a slide deck instead of a patch is theater.",
            "The best safety work I've seen looks exactly like good QA work. Boring, systematic, unglamorous.",
        ],
    },
    "remote-work": {
        "hashtag": "#RemoteWork",
        "authors": ["levelsio", "naval", "paulg"],
        "texts": [
            "Async by default isn't a perk, it's the only way small teams outpace big ones.",
            "Every meeting that could have been a doc is a tax on your best people's attention.",
            "Remote didn't kill culture. It exposed teams that never had one beyond free lunch.",
            "The hardest part of distributed work is not timezones, it's writing things down properly.",
            "Hire people who write well. In a remote team, writing is the operating system.",
            "If your process depends on everyone being online at once, it will break at the worst moment.",
            "Three years fully distributed: I'd take a great async writer over a great in-person talker any day.",
        ],
    },
    "growth": {
        "hashtag": "#GrowthMarketing",
        "authors": ["levelsio", "naval", "paulg"],
        "texts": [
            "Growth is not a department. It's what happens when the product is genuinely worth telling a friend about.",
            "The cheapest acquisition channel is still a founder who talks to users every single day.",
            "Retention fixes everything. A leaky bucket makes every acquisition win temporary.",
            "Most growth teams optimize the signup page when the real drop-off is in the first 5 minutes of use.",
            "Write for one specific person. If it could apply to anyone, it will move nobody.",
            "Word of mouth is engineered, not lucky: find the moment users feel smart, then make it shareable.",
            "A/B tests are for edges. Strategy is for slopes. Don't test your way out of a positioning problem.",
        ],
    },
}

# (起始分钟, 结束分钟, [(话题, 条数), ...])
# 0~60 分钟刻意铺 6 个话题（每个 2 条），保证最小窗口也有 6 个话题簇
SCHEDULE = [
    (3, 58, [("ai-coding", 2), ("open-models", 2), ("ai-agents", 2),
             ("inference-cost", 2), ("ai-safety", 2), ("ai-funding", 2)]),
    (65, 235, [("ai-coding", 2), ("open-models", 2), ("ai-agents", 2), ("inference-cost", 2),
               ("indie-hackers", 2), ("ai-funding", 2), ("dev-tools", 2), ("growth", 2)]),
    (245, 470, [("inference-cost", 2), ("ai-agents", 2), ("dev-tools", 2), ("indie-hackers", 2),
                ("ai-funding", 1), ("remote-work", 2), ("ai-safety", 2), ("growth", 1)]),
    (485, 1430, [("ai-coding", 2), ("open-models", 2), ("inference-cost", 2), ("ai-agents", 2),
                 ("indie-hackers", 2), ("ai-funding", 2), ("dev-tools", 2),
                 ("ai-safety", 2), ("remote-work", 2), ("growth", 2)]),
    (1450, 4280, [("ai-coding", 3), ("open-models", 3), ("inference-cost", 3), ("ai-agents", 3),
                  ("indie-hackers", 3), ("ai-funding", 2), ("dev-tools", 2),
                  ("ai-safety", 2), ("remote-work", 2), ("growth", 2)]),
]


def build():
    rnd = random.Random(20260910)
    posts = []
    idx = 0
    counters = {k: 0 for k in TOPICS}

    for start, end, plan in SCHEDULE:
        total = sum(n for _, n in plan)
        span = end - start
        slots = sorted(start + int(span * (i + 0.5) / total) + rnd.randint(-3, 3)
                       for i in range(total))
        queue = []
        for topic, n in plan:
            queue.extend([topic] * n)
        rnd.shuffle(queue)

        for offset, topic in zip(slots, queue):
            t = TOPICS[topic]
            author = t["authors"][counters[topic] % len(t["authors"])]
            text = t["texts"][counters[topic] % len(t["texts"])]
            # 每条都带上本话题专属的 hashtag，保证聚类信号干净
            if t["hashtag"].lower() not in text.lower():
                text = f"{text} {t['hashtag']}"
            counters[topic] += 1
            idx += 1

            recency_factor = 1.0 if offset < 240 else (1.6 if offset < 1440 else 2.2)
            base = int(rnd.randint(40, 260) * recency_factor)

            posts.append({
                "id": f"p{idx:03d}",
                "author_handle": author,
                "text": text,
                "topic": topic,
                "offset_minutes": max(1, offset),
                "base_likes": base,
                "base_retweets": int(base * rnd.uniform(0.12, 0.30)),
                "base_replies": int(base * rnd.uniform(0.08, 0.22)),
                "base_quotes": int(base * rnd.uniform(0.02, 0.08)),
            })

    # 追加刻意混入的风险内容
    for offset, author, text in RISKY_POSTS:
        idx += 1
        base = int(rnd.randint(40, 260) * (1.0 if offset < 240 else 1.6))
        posts.append({
            "id": f"p{idx:03d}",
            "author_handle": author,
            "text": text,
            "topic": "risky-demo",
            "offset_minutes": offset,
            "base_likes": base,
            "base_retweets": int(base * rnd.uniform(0.12, 0.30)),
            "base_replies": int(base * rnd.uniform(0.08, 0.22)),
            "base_quotes": int(base * rnd.uniform(0.02, 0.08)),
        })

    posts.sort(key=lambda x: x["offset_minutes"])

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"accounts": ACCOUNTS + DEMO_RISK_ACCOUNTS, "posts": posts},
                  f, ensure_ascii=False, indent=2)
    print(f"生成 {len(posts)} 条帖子（含 {len(RISKY_POSTS)} 条演示用风险内容） -> {OUT}")
    return posts


if __name__ == "__main__":
    build()
