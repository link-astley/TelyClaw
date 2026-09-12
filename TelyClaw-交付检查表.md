# TelyClaw 交付检查表

> 对照题面（TelyClaw Growth Lead | Vibe Coding Challenge）逐项核对。
> ✅ = 已做　◐ = 做了一部分　▢ = 没做（留空待补）
> 核对日期：2026-09-12（2026-09-12 更新：内容安全检查 + 九维评分 + 升温识别 已完成）　核对方式：逐条读题面 + 逐条查代码，非凭印象

---

## 一、最小验收标准（Minimum Acceptance Criteria）—— 全部已做

| # | 题面要求 | 状态 | 落在哪 |
|---|---|---|---|
| 1 | 可配置至少 5 个 X Accounts | ✅ | 预置 6 个 + 设置页增删/停用 |
| 2 | 支持至少 2 种时间窗口 | ✅ | 1h / 4h / 8h / 24h / 3d 共 5 档 |
| 3 | 可获取或导入指定周期内的 Posts | ✅ | 内置模拟数据 + 粘贴/导入 + 预留 X API |
| 4 | AI 自动识别多个 Topics 并输出 Summary | ✅ | 聚类 + DeepSeek 命名与摘要 |
| 5 | 可对 Trends 排名并解释 Ranking 原因 | ✅ | 九维热度分 + AI 排名理由 |
| 6 | 可选出最值得 TelyClaw 跟进的 Top Trends | ✅ | Top 精选 3 个，AI 推荐 + 用户可改 |
| 7 | 每个重点 Trend 生成至少 3 个 Content Angles | ✅ | 3 个角度卡片 |
| 8 | 可生成至少 1 条可直接发布的 X Post | ✅ | 每个角度 3 条，共 3 条 |
| 9 | 有基本可操作的 UI | ✅ | 4 个 Tab，全部可点击 |
| 10 | 整个 Workflow 可 End-to-End Demo | ✅ | 已实测跑通（含真实 DeepSeek 调用） |

**结论：10/10 全过，没有硬伤。**

---

## 二、核心功能细节（题面 A/B/4/5/6 节展开）

| # | 题面要求 | 状态 | 说明 |
|---|---|---|---|
| 1 | 添加 / 删除监控账号 | ✅ | 设置页 |
| 2 | 同时监控多个账号 | ✅ | 勾选卡片 |
| 3 | 自定义监控时间窗口 | ✅ | 5 档 |
| 4 | 获取指定窗口内的新内容 | ✅ | 按相对时间轴过滤 |
| 5 | 将相似 Posts 聚合为 Topic | ✅ | 两级聚类（hashtag 主信号 + 关键词共现） |
| 6 | 自动识别并命名 Topics | ✅ | DeepSeek 命名，界面标注"AI 命名" |
| 7 | 总结每个 Topic 的核心讨论内容 | ✅ | 一句话摘要 |
| 8 | **识别正在快速升温的 Topics** | ✅ | 已加「升温程度」维度（10% 权重）：最近 1/4 窗口的提及占比 ÷ 25%，小样本收缩；界面上 🔥 标记 ≥1.5× |
| 9 | 展示相关 Posts 和 Accounts 作为依据 | ✅ | 榜单卡展示相关原帖（含作者、风险标记）、覆盖账号数 |
| 10 | 自定义 Trend Opportunity Score（不要照搬） | ✅ | 自设计九维加权：互动20/账号20/提及15/新鲜度15/升温10/玩梗5/搞笑5/Drama5/未饱和5；后三项 AI 打分 |
| 11 | 排名考虑 Engagement × Independent Accounts | ✅ | 互动 20% + 账号 20%，另加未饱和度（账号数÷提及数）5% |
| 12 | 排名考虑 TelyClaw Relevance | ◐ | Top 精选那一步用了契合度（AI 判断），但**排行榜分数本身不含 relevance**，且契合度没有量化分数展示 |
| 13 | 输出 Top Opportunities 并解释原因 | ✅ | 3 个 + 契合度理由 |
| 14 | 3 个 Content Angles 数量达标 | ✅ | 3 个 |
| 15 | **Angle 类型覆盖 Hot Take / Educational / TelyClaw Product Angle** | ◐ | 现在让 AI 自选（反共识/数据拆解/实战/提问/反面案例），**缺少强制的"TelyClaw 产品角度"** —— 这是题面明确列的三类之一 |
| 16 | **内容不能只是 Copy / Rewrite / Summary 原帖** | ◐ | Prompt 里有"不要空话开头、不要编数字"，**没有这条硬约束** |
| 17 | 内容标准：Trend + TelyClaw Perspective + Original Insight | ◐ | 有账号定位作视角，但 Prompt 未明确要求"原创洞察" |
| 18 | 至少 1 条可直接发布的 X Post | ✅ | 3 条不同风格 |
| 19 | Human-in-the-loop：Edit → Approve → Publish | ✅ | 编辑框 → X 样式预览确认 → 发布 |
| 20 | **内容安全检查（7 类风险过滤）** | ✅ | AI 逐条判定并打显眼标记，话题保留由人决定； 可真排除；未执行检查时界面明说 |

---

## 三、Bonus Features（12 项，题面说不追求堆功能）

| # | Bonus 项 | 状态 | 说明 |
|---|---|---|---|
| 1 | Trend Velocity / Momentum Detection | ✅ | 已做（升温程度 10% 权重，见核心第 8 条） |
| 2 | Engagement-based Ranking | ✅ | 互动总量占 20% 权重 |
| 3 | Cross-account Topic Clustering | ✅ | 聚类本身就是跨账号的，且有"参与账号数"维度防单账号刷屏 |
| 4 | TelyClaw Brand / Product Relevance Scoring | ◐ | 有定性契合度理由，无量化分数 |
| 5 | Duplicate / Similar Content Detection | ▢ | 未做 |
| 6 | Human Approval Workflow | ◐ | 发布前有预览确认（等于 approve），但没有独立的审批状态流转/审批记录 |
| 7 | X Publishing Integration | ▢ | 接口已预留（Publisher 抽象 + X API 映射表），真实发布未实现。题面明确 MVP 不要求 |
| 8 | Scheduled Monitoring | ▢ | 未做（当时决策：手动触发，演示节奏可控） |
| 9 | Historical Trend Tracking | ▢ | 未做。目前每次检测覆盖上一次结果，看不到话题热度随时间的变化 |
| 10 | Published Content Performance Tracking | ▢ | 未做。已发布内容没有互动数据回填 |
| 11 | 根据历史表现自动优化下一轮内容 | ▢ | 依赖第 10 项，未做 |
| 12 | AI Agent 自动跑完整个 Workflow | ▢ | 未做（现在是人在点上推进） |

**题面原话：Bonus 不追求堆功能，请优先确保核心闭环真实、清晰、可演示。** 当前核心闭环已跑通，Bonus 缺失不扣硬分，但第 1 项建议补（理由见上）。

---

## 四、交付物（Deliverables）—— ⚠️ 最大的缺口在这里

| # | 交付物 | 状态 | 说明 |
|---|---|---|---|
| 1 | Working Demo | ✅ | 本地可跑，端到端已验证 |
| 2 | Source Code / GitHub Repository | ✅ | 已上线：https://github.com/link-astley/TelyClaw （公开仓库，2 次提交，28 个文件；本地与远端已校验字节级一致，已扫描无密钥） |
| 3 | 3-5 分钟 Demo Video | ▢ | 未录制 |
| 4 | 简短 README | ✅ | `README.md` 已写（521 行中文），覆盖题面要求的 8 件事 + Production 数据方案 + Mock 数据声明 |

### README 必须写清的 8 件事（题面逐条列了）

| # | 内容 | 状态 |
|---|---|---|
| 1 | Product Logic（产品逻辑） | ▢ |
| 2 | System Architecture（系统架构） | ▢ |
| 3 | Trend Detection Logic（热点识别逻辑） | ▢ |
| 4 | Opportunity Ranking Logic（机会排名逻辑） | ▢ |
| 5 | Content Generation Logic（内容生成逻辑） | ▢ |
| 6 | 使用了哪些 AI / Vibe Coding Tools | ▢ |
| 7 | 当前 MVP 有哪些限制 | ▢ |
| 8 | 如果有更多时间/资源，会怎么做 | ▢ |

### 散落在题面其他页、但也要进 README 的 2 件事

| # | 内容 | 状态 |
|---|---|---|
| A | **如果真正投入 Production，你会如何解决数据获取问题**（第 2 页"现实约束"明确要求） | ▢ |
| B | 数据是模拟的这一点，以及 Mock→真实 X API 的切换方式 | ▢ |

---

## 五、Demo 后要口头/书面回答的（不是代码，但要准备）

| # | 内容 | 状态 |
|---|---|---|
| 1 | **90 天增长问题**：如果这套系统成为 TelyClaw Growth Team 的日常工具，你怎么用它让官方账号在 90 天内实现 10x Qualified Reach？（要按 Trends→Content→Attention→Engagement→Growth 的循环讲） | ▢ |
| 2 | North Star Metric 的认同与口径：Qualified Engagement Generated from Trends（MVP 阶段用 Qualified Engagement per Trend-generated Post 作 Proxy） | ▢ |
| 3 | Supporting Metrics 的口径：Trend Detection Lead Time / Trend to Content Time（目标 <5-10 分钟）/ Trend Hit Rate / Content Acceptance Rate / Engagement Lift | ▢ |

---

## 六、缺口汇总（按"不补会丢分"的程度排序）

| 优先级 | 缺口 | 为什么急 | 补起来难不难 |
|---|---|---|---|
| 🔴 P0 | README（含 8 项说明 + Production 数据方案） | 必交项 | ✅ 已完成（2026-09-12） |
| ✅ | GitHub 远端仓库 | ✅ 已完成（2026-09-12）：https://github.com/link-astley/TelyClaw | — |
| 🔴 P0 | 3-5 分钟 Demo Video | 必交项 | 需要你录屏（我可以写逐句脚本） |
| 🟡 P1 | Content Angle 缺"TelyClaw Product Angle" | 题面明确列的三类之一，评审大概率会看 | 改一段 Prompt 即可 |
| 🟡 P1 | "不能只是转述原帖"的硬约束 | 题面加粗级别的红线 | 改一段 Prompt 即可 |
| ✅ | Trend Velocity / 快速升温识别 | 已完成（2026-09-12） | — |
| 🟢 P2 | 90 天增长问题回答 | 不写代码，但要准备 | 我可以帮你起草 |
| 🟢 P2 | 其余 Bonus（去重、定时、历史追踪、效果回流、全自动） | 题面明说不追求堆功能 | 暂缓 |
