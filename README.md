# 技术周报自动生成器

每周一自动抓取 **GitHub Trending** 和 **Hacker News**，用 DeepSeek 做结构化分析，生成一份带「深读卡片」的中文技术周报，直接写进 Obsidian vault 并自动提交。

适合想维护个人技术雷达、又不想每周手动翻榜单的人。

---

## 效果

生成的报告长这样（节选）：

```markdown
> [!example] **[anthropics/skills](https://github.com/anthropics/skills)** · `Agent` · 🔥 10
> 📝 **Python**　⭐ **195,462**　📈 **+6,077 stars this week**
>
> **是什么**　Anthropic 公开的 Claude Agent Skills 实现仓库，用 SKILL.md 把指令、脚本和资源
> 组织成一个个技能文件夹，让 Claude 在特定任务中按需动态加载……
>
> **什么时候用**　如果你在 Claude Code、Claude.ai 或 API 上构建需要稳定复现专业流程的 Agent，
> 比如按公司品牌规范生成文档，就应该先把这里的技能当作模板改写。
>
> **比什么好**　相比 LangChain 的 Tool 与 Chain 抽象，Skills 用文件夹加 Markdown 指令承载
> 流程知识，模型按需加载而不是把全部工具描述塞进上下文。代价是它依赖 Claude 自身的加载机制。
>
> **上手成本**　只需要一个能运行 Claude Code 或调用 API 的环境，克隆仓库后把技能目录放到约定路径即可
```

报告结构：

```
🎯 本周必看             5 行索引
## 🧩 结构化摘要        数据概览 + 全部条目卡片（GitHub 11 张 + HN 10 张，一条不落）
## 🔥 技术趋势分析      3-4 条趋势，带历史联动判断
## 📈 项目趋势变化      本周条目相对历史的上榜次数与升降
## ✅ 本周行动          可勾选的任务清单
📦 原始数据            折叠区，保留抓取原文和链接
```

## 特性

- **重要度打分有依据**：把语言、总 Star、本周增长、HN 分数与评论数一起喂给模型，评分规则绑定增长信号，不是凭描述瞎猜
- **深读结合 README**：对前 5 个项目抓取 README 正文作为素材，输出「是什么 / 什么时候用 / 比什么好 / 上手成本」四个槽位，并强制要求点名竞品，避免「更轻量、更灵活」这类空话
- **跨周记忆**：把每周结果存进 `Knowledge/projects.json`，下次运行能判断「第 3 次上榜」「重要度从 6 升到 8」
- **失败降级**：README 抓不到、深读失败、模型输出不合规时自动退回普通卡片，报告照常产出
- **Obsidian 原生**：YAML frontmatter 带统计字段，可被 Dataview 查询；卡片用 callout 语法，配套一份 CSS 片段

## 快速开始

### 1. 建仓库

**方式 A：Fork（最省事）**

点页面右上角 `Fork`。注意：**fork 出来的仓库 Actions 默认关闭**，需要打开 `Actions` 标签页，
点一次「I understand my workflows, go ahead and enable them」。

**方式 B：推到自己的空仓库**

在 GitHub 新建一个空仓库（**不要**勾选 README / .gitignore / license），然后：

```bash
git clone https://github.com/JumpBear777/weekly-tech-digest.git
cd weekly-tech-digest
git remote set-url origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 2. 配置 API Key

`Settings → Secrets and variables → Actions → New repository secret`

- Name：`DEEPSEEK_API_KEY`
- Secret：在 [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) 创建的 key

工作流会先调用 `/models` 验证密钥，401 会直接给出可读的失败原因，不会静默失败。

### 3. 跑一次

`Actions → Weekly Report → Run workflow`。

默认每周一 08:00 UTC（北京时间 16:00）自动运行，改 `.github/workflows/weekly.yml` 里的 cron 即可调整。

## 本地运行

```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY=sk-xxx        # Windows: set DEEPSEEK_API_KEY=sk-xxx
python scripts/generate_report.py
```

默认输出到**当前目录**下的 `Weekly/` 和 `Knowledge/`（目录不存在会自动创建）。
想直接写进 Obsidian vault，用 `OBSIDIAN_VAULT` 指向 vault 根目录。

> 国内网络装依赖可能很慢，可以加镜像：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 配置

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 必填，DeepSeek 平台的 API key | — |
| `OBSIDIAN_VAULT` | 输出根目录，报告写到 `<VAULT>/Weekly/`，记忆写到 `<VAULT>/Knowledge/` | 当前目录 |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-v4-flash` |

代码里的可调参数：

| 位置 | 参数 | 说明 |
|---|---|---|
| `generate_report.py` | `DEEP_DIVE_COUNT` | 深读条数，默认 5 |
| `hacker_news.py` | `get_hn_top(limit=10)` | 抓多少条 HN |
| `github_trending.py` | `?since=weekly` | 榜单时间窗口（daily / weekly / monthly） |

## 工作流程

```
抓取 GitHub Trending ─┐
                     ├→ Step1 结构化（分类 / 重要度 / 描述 / 理由）
抓取 Hacker News ────┘         ↓
                     Step1.5 深读（前 5 个项目抓 README，输出四个槽位）
                              ↓
                     Step2 趋势分析（结合记忆库判断持续火热 / 升温 / 降温）
                              ↓
                     Step3 行动清单（importance ≥ 7 的前 3 个项目）
                              ↓
                     Step4 趋势变化表 + Step5 写入记忆库
                              ↓
                     生成 Markdown → 提交 → push
```

## 费用

每次运行调用 3 次 API：

1. 结构化分析（全部条目，约 21 条）
2. 深读（5 个项目 + README 摘录）
3. 趋势分析

建议先用你自己的 key 试跑一次，看账单页的实际消耗。抓取部分（GitHub / HN / raw.githubusercontent.com）不计费。

## 接入 Obsidian

周报是在 **GitHub 的服务器上**生成的（`runs-on: ubuntu-latest`），你的电脑不参与执行，也不用一直开着。
你的电脑只负责把结果拉下来看。两种接法，选一种：

### 方式 A：仓库即 vault（推荐）

1. 把仓库克隆到本地任意目录：

   ```bash
   git clone https://github.com/<你的用户名>/<仓库名>.git "D:\Notes\TechDigest"
   ```

2. Obsidian →「打开文件夹作为仓库」→ 选中这个目录
3. 装插件：设置 → 第三方插件 → 关闭安全模式 → 浏览，安装
   - **Obsidian Git**（必需）：定时拉取周报
   - **Dataview**（可选）：首页看板
4. 配置 Obsidian Git：设置 → Git
   - `Auto pull interval` 填 `60`（分钟）
   - `Auto pull on boot` 打开
   - 首次 pull/push 会弹窗要账号：用户名填 GitHub 用户名，**密码必须填 Personal Access Token，不是登录密码**
     - 生成 PAT：GitHub `Settings → Developer settings → Personal access tokens → Fine-grained tokens`，
       勾选该仓库的 `Contents: Read and write`
5. 启用样式（可选）：把 `assets/weekly-report.css` 复制到 `.obsidian/snippets/`，
   设置 → 外观 → CSS 代码片段 → 刷新 → 打开 `weekly-report`
6. 启用看板（可选）：把 `assets/dashboard.md` 复制到 vault 根目录，改名为 `Home.md`

> **网络提示**：Obsidian Git 用的是内嵌的 isomorphic-git，**不读系统 git 的 `http.proxy` 配置**。
> 如果你的网络需要代理才能连 GitHub，Obsidian 里可能会一直超时——
> 这时可以用下面的方式 B，由你在终端手动 `git pull`（终端的 git 是能用代理配置的）。

### 方式 B：已有 vault，本地生成

不想把仓库当 vault，就让脚本直接写进你现有的 vault：

```bash
pip install -r requirements.txt
export OBSIDIAN_VAULT="D:/Notes/MyVault"    # Windows: set OBSIDIAN_VAULT=D:\Notes\MyVault
export DEEPSEEK_API_KEY=sk-xxx
python scripts/generate_report.py
```

报告和记忆会直接写进 `<你的 vault>/Weekly/` 和 `<你的 vault>/Knowledge/`。
这种方式不需要 GitHub Actions，也不用配 PAT——但需要你在自己的电脑上执行，而不是在 GitHub 上。

## Obsidian 样式（可选）

仓库自带 `assets/weekly-report.css`：

1. 复制到 `<你的 vault>/.obsidian/snippets/`
2. 设置 → 外观 → CSS 代码片段 → 刷新 → 打开 `weekly-report`

报告 frontmatter 里带 `cssclasses: [weekly-report]`，所以样式只作用于周报，不影响其他笔记。
文件开头有几个间距变量，想更松或更紧直接改数。

## 已知限制

- **star-history 图表**：报告里的 Star 趋势图来自 `api.star-history.com`，需要能访问外网，加载失败时会显示破图（不影响文字内容）
- **README 抓取**：走 `raw.githubusercontent.com`，个别仓库取不到（默认分支命名特殊、没有 README），此时该条自动退回普通卡片
- **周号用 ISO 周**（`datetime.isocalendar()`），与你本地其他按 `%U` 命名的文件可能差一周
- **HN 不做过滤**：抓的是 HN 首页前 10 条，可能混入非技术话题

## 目录结构

```
.github/workflows/weekly.yml   定时任务
scripts/
  generate_report.py           主流程与报告组装
  ai_summary.py                DeepSeek 调用与提示词
  github_trending.py           抓 GitHub Trending
  hacker_news.py               抓 HN（含分数 / 评论数）
  readme_fetch.py              抓 README 供深读
assets/weekly-report.css       Obsidian 样式片段
assets/dashboard.md            Dataview 看板模板（可选）
Weekly/                        输出的周报（运行后生成）
Knowledge/                     跨周记忆与项目索引（运行后生成）
```

## 运行在哪里？

| 场景 | 在哪执行 | 需要什么 |
|---|---|---|
| GitHub Actions（默认） | **GitHub 的服务器**（Ubuntu），你的电脑关机也照跑 | 仓库 secret `DEEPSEEK_API_KEY` |
| 本地运行 | 你自己的电脑 | Python 3.11+、依赖、环境变量里的 key |

Actions 跑完会把报告 commit 回仓库，Obsidian 那边靠 Obsidian Git 插件定时 pull 下来，
所以你的电脑上不需要装 Python，也不需要配置 key。

## 依赖

- Python 3.11+
- `requests`、`beautifulsoup4`
- DeepSeek API key

## License

MIT
