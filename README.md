# 智效进化论：微信公众号 AI 发布框架

一个面向普通读者的安全优先内容运营 Agent：寻找 AI 对工作、钱包、安全、健康、家庭与生活选择的真实影响，
完成选题、调研、故事化写作、审查修订和视觉制作，最终导出本地 Markdown/HTML 草稿。
技术内容保留为深度栏目，但不再是默认受众入口。

Agent 模式严格 `draft-only`，不会实例化微信客户端。原有人工审批后的草稿箱上传命令仍保留，但不会被 Agent 自动调用。

## 快速开始

要求 Python 3.11+（当前项目按 Python 3.13 验证）。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config/account.example.yaml config/account.yaml
cp .env.example .env
pytest
```

程序启动时会自动读取项目根目录的 `.env`；系统环境变量优先，不会被 `.env` 覆盖。

## 内容运营 Agent

Agent 使用有界状态机，允许的动作固定为：发现、初选、来源全文抓取、全文后重定稿、证据契约重建、人工确认选题、调研、内容规划、写作、审查、修订、质量门禁、发布前主编审查、视觉规划、资产渲染、多模态视觉审查、导出和停止。正文内视觉规划只读取审核定稿后的文章，并且锚点必须逐字对应最终二/三级标题。模型负责内容决策，程序控制最大步骤、最多修订次数和停止条件。

选题阶段不是单纯生成标题，而是先输出 provisional `topic-brief.json`，随后抓取所选官方 URL 的全文，
生成 `source-document-<signal_id>.json`，并依据全文重新确定标题、结论与可复制资产，再重建
`evidence-contract.json`。每条核心结论必须绑定
能够在官方全文中逐字定位的 quote；选题整体与引文不一致时，`topic_supported=false` 并自动换下一个候选。
无法抓取的 URL、返回人机验证的来源域名和证据不足的信号也会自动排除。只有官方 Release 时，
实测、教程、故障复盘和横评会自动降级为版本解读/迁移清单，无法形成价值时直接停止。
常规选题还必须通过大众门禁：普通读者适配分不低于 75，标题以工作、钱、安全、健康、
家庭或生活后果而非工具/版本开场，前置知识不超过 2 项，并明确非该工具用户可复用的价值。
内容组合按 35% 工作与收入、25% 钱/消费/诈骗、25% 健康/家庭/教育/情绪/生活、
15% 技术深度控制。

质量门禁通过后，发布前主编会结合文章、资料卡、带原文引文的证据契约、内容计划和官方全文检查事实边界与发布质量；素材渲染后，视觉审稿人会结合尺寸检查结果和实际图片检查封面承诺、信息增量、可读性与视觉一致性。两项评分默认均不得低于 8 分。

```bash
# 查看官方来源信号，不生成文章
wechat-ai-publisher agent discover

# 自动生成本地草稿
wechat-ai-publisher agent run --draft-only

# 不访问网络和模型的完整演练
wechat-ai-publisher agent run --draft-only --demo

# 查看待确认选题并批准后续写作
wechat-ai-publisher agent topic --run-id <run_id>
wechat-ai-publisher agent approve-topic --run-id <run_id> --actor <确认人>
wechat-ai-publisher agent resume --run-id <run_id>

# 拒绝当前选题；随后恢复任务会自动改选下一个候选
wechat-ai-publisher agent reject-topic --run-id <run_id> --actor <确认人> --note <原因>
wechat-ai-publisher agent resume --run-id <run_id>

# 查看或恢复其他任务
wechat-ai-publisher agent status --run-id <run_id>
wechat-ai-publisher agent resume --run-id <run_id>
```

每一步都会写入 `runtime/agent-<run_id>/agent-state.json`。最终选题通过全文和逐字证据审计后，
任务会以 `awaiting_approval` 暂停，并生成 `topic-approval.json`；批准前不会产生调研和写作模型费用。
网络或模型失败时，`resume` 从失败动作继续，不重复已经完成的抓取和模型调用。成功草稿写入
`articles/drafts/`。可通过 `agent.require_topic_approval=false` 显式关闭该节点。

`--demo` 产物会标记为 `publication_status=demo`，只用于流程与视觉验收；即使门禁通过，也不能调用真实微信草稿接口。

来源在 `config/sources.yaml` 配置。默认同时启用海外官方源（OpenAI、Google AI）与国内
科技/社会源（量子位、雷峰网、极客公园、36氪、爱范儿、IT之家、Solidot、中国新闻网社会），
优先寻找贴近中国读者的工作、钱、安全、健康、家庭和生活影响。少数派、InfoQ、美团技术等
默认关闭；Google Workspace、Microsoft、Zapier、Spring Blog 及开发工具 GitHub Release
也默认关闭，仅在规划办公或技术深度栏目时启用。外部正文始终按不可信数据处理，不能改变
Agent 指令。正文抓取只允许公开 HTTP/HTTPS URL，
拒绝私有网络地址、异常重定向、超大响应和人机验证页；大小与最低正文长度可在
`config/sources.yaml` 中调整。

一次完整运行通常包含选题、研究、规划、写作和审查等多次模型请求；实际耗时与费用取决于模型。`agent.max_steps`、`max_revisions` 和阶段超时在 `config/account.yaml` 调整。

## 视觉系统

默认主题为 `config/themes/professional-minimal.yaml`，使用深蓝 + 青绿色专业极简风格。正文 HTML 全部采用微信兼容的内联样式，不依赖外部 CSS、JavaScript、SVG、flex/grid 或 webfont。

Agent 会为每篇文章规划封面，并按需补充正文视觉节点（教程/清单类优先；新闻解读默认可仅封面）：

- 900×383 PNG 封面；
- 必要时的步骤流程、迁移清单等 HTML 信息组件；
- 可分享的检查清单 PNG（仅在确有清单资产时）；
- `visual-manifest.json`，记录图片用途、生成方式、模型、提示词和版权说明。
  新闻解读默认不加概念插画，也不把正文再摘要成重复的“核心结论卡”。

概念插画已接入阿里云原生 DashScope 接口，模型为
`qwen-image-2.0-pro-2026-06-22`。该模型不支持 OpenAI compatible-mode，
因此使用 `/api/v1/services/aigc/multimodal-generation/generation` 独立调用，并默认复用
`OPENAI_API_KEY`。密钥未配置、超时、额度或内容安全失败时自动降级为 Pillow 固定模板，不阻塞草稿生成。

可单独重渲染现有 Markdown：

```bash
wechat-ai-publisher rerender articles/drafts/example.md \
  --category 版本解读 \
  --output-dir articles/drafts/visual-preview
```

输出包含 Markdown、主题 HTML、封面、正文图片和视觉资产清单。真实上传微信前，本地图片仍会经过现有上传逻辑替换为微信图片 URL。

## 手工选题流水线

先编辑 `topics/topic-pool.yaml`。只要选题声明了 `required_evidence`，就必须提供真实的 `verification_records`；没有证据时，流水线会在资料卡阶段停止，不允许模型补造。

```bash
# 不访问网络，验证项目接线（示例选题需先补充 verification_records）
wechat-ai-publisher generate --demo --topic java-ai-unit-test

# 调用 OpenAI 兼容接口
wechat-ai-publisher generate --topic java-ai-unit-test

# 根据上一步输出的 job_id 生成 HTML
wechat-ai-publisher render --job <job_id>

# 质量门禁通过后，只生成本地预览
wechat-ai-publisher publish --job <job_id> --dry-run
```

## 接入 OpenAI 兼容模型

配置项在 `config/account.yaml`：

- `model.model`：模型名称，当前配置为 `qwen3.7-max`。
- `model.base_url`：默认兼容接口地址，当前配置为阿里云 MaaS 地址。
- `model.api_key_env`：密钥环境变量名，默认 `OPENAI_API_KEY`。
- `model.base_url_env`：可覆盖默认地址的环境变量名，默认 `OPENAI_BASE_URL`。
- `model.temperature`：技术内容建议保持在 0.2～0.4。

适配器使用兼容面更广的 Chat Completions 接口，并要求模型按 JSON Schema 返回结构化结果。不同供应商若不支持该接口，需要在 `providers/` 增加独立适配器。

## 写入微信草稿箱

1. 在公众号后台确认 `media/uploadimg`、`material/add_material`、`draft/add` 权限。
2. 设置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`。
3. 将 `config/account.yaml` 中 `publish.dry_run` 改为 `false`。
4. 人工审核后执行；Agent 终稿会从视觉清单自动读取封面，也可用 `--cover` 覆盖：

```bash
wechat-ai-publisher publish \
  --job <job_id> \
  --approved
```

真实上传同时满足以下条件才会执行：质量门禁通过、配置关闭 dry-run、提供 `--approved`、视觉清单或参数指定的封面存在、微信凭据完整。任务目录已有成功的 `publish-result.json` 时会直接返回原结果，避免重复创建草稿。

发布配置默认 `publish.open_comment=true`（草稿开启留言，便于互动信号），`publish.max_articles_per_day=1`（运营建议一天一条主推，避免拆散推荐评估）。写作规范与质量门禁已对齐推荐分发信号：开篇 3 秒留存、短段落完读、文末真实讨论问题、禁止机械求赞。

## 获取发布后数据

认证公众号可使用微信“获取发表内容发表详细数据”接口。配置
`WECHAT_APP_ID`、`WECHAT_APP_SECRET` 后执行：

```bash
# 拉取指定发表日期的数据；微信最多返回到昨天
wechat-ai-publisher analytics fetch --date 2026-07-30

# 拉取最近 30 个发表日期，并保存到 runtime/analytics/
wechat-ai-publisher analytics fetch --days 30

# 汇总已经拉取到本地的数据
wechat-ai-publisher analytics report --days 30
```

报告包含阅读人数、分享、点赞、在看、收藏、留言、阅读后关注和赞赏金额等指标。
详细接口仅支持 2025-11-01 及之后发表的内容，每篇文章最多统计发表后 30 天；数据可能延迟，
应保留接口返回的 `is_delay` 标记。未认证或没有“群发与通知”权限的公众号无法调用。

## 目录

```text
config/                 账号、来源、模型、提示词和风格规范
topics/                 选题池
research/               可人工维护的研究资料
articles/               草稿、审稿和已发布内容
assets/                 封面与正文图片
templates/              微信 HTML 预览模板
runtime/agent-<run_id>/ Agent 状态、来源、选题、审稿与门禁产物
src/wechat_ai_publisher 业务代码
tests/                  单元测试和 dry-run 端到端测试
.github/workflows/      GitHub Actions 生成与审批发布
workflows/              旧版工作流模板
```

每个任务都有唯一 ID。Agent 的 `agent-state.json` 记录逐步状态、模型、提示词版本、耗时和产物；证据不足、修订超限或质量门禁失败时会停止，不会导出为可发布草稿。

## GitHub Actions

工作流分成三个安全边界：

- `.github/workflows/generate.yml` 先完成全文选题与证据审计并暂停，通过 `topic-approval` Environment 人工批准后，再在新的 GitHub hosted job 中继续生成、审稿和渲染。
- `.github/workflows/publish.yml` 只允许手动触发。指定生成工作流的 `run ID` 后，经 `wechat-draft` Environment 人工审批，在固定 IP 的 self-hosted runner 创建微信草稿。

仓库设置：

1. 在 Repository Secrets 配置 `OPENAI_API_KEY`；自定义兼容服务时再配置 `OPENAI_BASE_URL`。
2. 新建 GitHub Environment `topic-approval`，设置至少一名 required reviewer；候选生成后先在工作流 Summary 查看标题、读者问题、核心结论、可复制资产和官方来源，再批准继续写作。该 Environment 不需要保存密钥。
3. 新建 GitHub Environment `wechat-draft`，设置至少一名 required reviewer，并只在该 Environment 中保存 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`。
4. 为本仓库注册 self-hosted runner，添加 `wechat-publisher` 标签。runner 应使用独立低权限系统账号和固定出口 IP，并把该 IP 加入公众号后台白名单；机器上预先安装 Python 3.11+（`python3`/`pip` 在 PATH 中可用），发布工作流不再联网下载解释器。发布机无需 sudo：若缺少中文字体，工作流会把文泉驿微米黑下载到用户目录并在上传前重绘封面。
5. 手动运行一次 `Generate WeChat Article`，先批准选题；完成后下载 `content-agent-<run_id>`，审阅 HTML、`quality-gate.json`、主编审查和视觉审查结果。
6. 运行 `Publish WeChat Draft`，输入上一步页面 URL 中的 GitHub `run ID`，再由 `wechat-draft` Environment reviewer 批准发布 Job。

生成 Artifact 必须恰好包含一个 `ready_to_publish` Manifest；发布工作流不会按修改时间猜测“最新文章”。任务包内路径均为相对路径，可在两类 runner 之间迁移。发布收据保留 7 天，同一任务再次执行会读取 `publish-result.json`，不会重复创建草稿。

首次接入先使用测试文章验收图片、排版和公众号接口权限，确认无误后再保留每周一北京时间 09:00 的定时生成。不要在 GitHub hosted runner 上放置微信密钥；其动态出口 IP 不适合作为公众号白名单地址。

## 当前边界

- 未接入飞书多维表格审批和机器人通知。
- 自动调研仅限配置的官方 RSS/Atom 和 GitHub Release；未接入开放式全网搜索。
- 未自动编译文章中的任意代码，也不会把官方发布说明等同于真实项目验证。
- 外部生图只用于无人物、无商标的概念插画；运行结果和产品界面仍必须使用真实截图。
- 未实现自动群发；发布后指标可由 `analytics fetch` 手工或定时拉取。
- 外部 API 测试均使用 mock，首次真实接入必须用测试文章完成公众号后台验收。

