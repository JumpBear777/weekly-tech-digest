# from datetime import datetime

# import os

# # 确保 Weekly 目录存在
# os.makedirs("Weekly", exist_ok=True)

# week = datetime.now().strftime("%Y-W%U")

# content = f"""# Weekly Report

# 生成时间：

# {datetime.now()}

# 这是自动生成的测试文件。
# """

# with open(f"Weekly/{week}.md", "w", encoding="utf-8") as f:
#     f.write(content)

# print("report generated")



# from datetime import datetime
# from github_trending import get_trending

# week = datetime.now().strftime("%Y-W%U")

# repos = get_trending()

# content = f"""# Weekly Report

# 生成时间：
# {datetime.now()}

# ## GitHub Trending

# """

# for r in repos:
#     content += f"""
# ### {r['name']}

# {r['desc']}
# """

# with open(f"Weekly/{week}.md", "w", encoding="utf-8") as f:
#     f.write(content)

# print("done")





from datetime import datetime
from github_trending import get_trending
from hacker_news import get_hn_top
from ai_summary import explain_projects, analyze_trends, generate_learning_tasks, deep_dive
from readme_fetch import fetch_readme
import os
import json
import re
from collections import Counter

# ============================================================
# 输出路径
# ============================================================
# 默认写到当前目录（Weekly/ 与 Knowledge/ 会自动创建，CI 下即为仓库根目录）。
# 想直接写进 Obsidian vault，设置环境变量 OBSIDIAN_VAULT 指向 vault 根目录。
VAULT_PATH = os.environ.get("OBSIDIAN_VAULT") or "."

# ============================================================
# 内存函数
# ============================================================

def clean_id(item_id):
    """去掉 [GitHub] / [HN] 前缀。

    分区标题已经标明来源；带前缀的卡片标题会变成 `[[HN] xxx](url)`，
    Obsidian 会把开头的 `[[` 当成 wiki 链接开始解析。
    注意：本脚本是顶层顺序执行的，这个函数必须在主流程之前定义。
    """
    return re.sub(r'^\[(?:GitHub|HN)\]\s*', '', str(item_id))


def save_project_memory(structured_data, week):
    """将本周结构化数据追加到 Knowledge/projects.json 中"""
    knowledge_dir = os.path.join(VAULT_PATH, "Knowledge")
    memory_path = os.path.join(knowledge_dir, "projects.json")
    os.makedirs(knowledge_dir, exist_ok=True)

    # 读取现有记忆
    memory = {}
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    memory = json.loads(content)
        except json.JSONDecodeError:
            print("   ⚠️ 记忆文件损坏，将重新创建")
            memory = {}

    # 追加本周数据
    for item in structured_data:
        proj_id = item.get("id")
        if not proj_id:
            continue
        records = memory.setdefault(proj_id, [])
        record = {
            "week": week,
            "name": item.get("name"),
            "category": item.get("category"),
            "importance": item.get("importance"),
            "reason": item.get("reason"),
        }
        # 同一项目同一周只保留最新一次。原先无脑 append，重跑一次就多一条，
        # 会让 detect_trend_changes 拿同周的两条记录比较，趋势恒为「稳定」。
        for i, old in enumerate(records):
            if old.get("week") == week:
                records[i] = record
                break
        else:
            records.append(record)

    # 写回文件
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def get_trend_summary(memory, structured, current_week, lookback_weeks=3):
    """只输出「本周条目」的历史出场情况。

    原实现把整个记忆库（几百个项目）平铺进提示词，一是浪费 token，
    二是模型会在写「本周最值得关注」时误引几周前就下榜的项目。
    模型真正需要的历史，只有本周这些条目自己上过几次榜。
    """
    if not memory:
        return "暂无历史数据。"

    summary_lines = []
    for item in structured:
        proj_id = item.get("id")
        if not proj_id:
            continue
        history = [r for r in memory.get(proj_id, []) if str(r.get("week")) < current_week]
        if not history:
            continue
        last = history[-1]
        summary_lines.append(
            f"- {proj_id}：历史上榜 {len(history)} 次，"
            f"最近一次 {last['week']} 重要度 {last['importance']}"
        )
    if not summary_lines:
        return "本周条目均为首次上榜，无历史数据。"
    return "\n".join(summary_lines)


def detect_trend_changes(memory, current_week, structured, lookback_weeks=3):
    """只输出「本周条目相对历史」的变化。

    原实现遍历整个记忆库，几百个项目全部平铺，一张表能占掉整份报告一半篇幅，
    而其中绝大多数是几周前就下榜的内容。这里改为只对本周条目做对比。
    """
    if not memory:
        return "暂无历史数据，本周条目均为首次记录。"

    rows = []
    for item in structured:
        proj_id = item.get("id")
        if not proj_id:
            continue
        imp = item.get("importance", 0)
        hist = [r for r in memory.get(proj_id, []) if str(r.get("week")) < current_week]
        if not hist:
            rows.append((proj_id, imp, 1, "🆕 首次上榜"))
            continue
        prev = hist[-1].get("importance", 0)
        delta = imp - prev
        if delta > 0:
            trend = f"🔥 +{delta}"
        elif delta < 0:
            trend = f"📉 {delta}"
        else:
            trend = "➡️ 持平"
        rows.append((proj_id, imp, len(hist) + 1, trend))

    if not rows:
        return "本周没有可对比的条目。"

    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    table = "| 项目 | 本周重要度 | 累计上榜 | 较上期 |\n|------|-----------|---------|--------|\n"
    for pid, imp, times, trend in rows:
        table += f"| {clean_id(pid)} | {imp} | {times} 次 | {trend} |\n"
    return table


# ============================================================
# 主流程
# ============================================================

# 用 ISO 周号（周一为一周起点），与 Obsidian 周期笔记 / Dataview 的惯例一致。
# 历史文件（2026-W41 及更早）是按旧的 %U 命名的，不重命名，只从本期开始切换。
_iso = datetime.now().isocalendar()
week = f"{_iso.year}-W{_iso.week:02d}"
week_display = datetime.now().strftime("%Y年%m月%d日 %A")  # 中文星期
# 英文星期转中文
weekday_map = {
    "Monday": "星期一", "Tuesday": "星期二", "Wednesday": "星期三",
    "Thursday": "星期四", "Friday": "星期五", "Saturday": "星期六", "Sunday": "星期日"
}
for en, cn in weekday_map.items():
    week_display = week_display.replace(en, cn)

print("📥 获取 GitHub Trending...")
github_raw = get_trending()
print(f"   获取到 {len(github_raw)} 个仓库")

print("📥 获取 Hacker News 热门...")
hn_raw = get_hn_top(limit=10)
print(f"   获取到 {len(hn_raw)} 个帖子")

# 统一数据结构并标注来源，保留链接信息
github_repos = []
github_lookup = {}  # full_name → 原始数据，供卡片展示用
for r in github_raw:
    full_name = r.get('full_name', r['name'])
    repo_data = {
        "name": f"[GitHub] {r['name']}",
        "desc": r['desc'],
        "full_name": full_name,
        "url": f"https://github.com/{full_name}",
        "language": r.get("language", ""),
        "stars": r.get("stars", 0),
        "forks": r.get("forks", 0),
        "growth": r.get("growth", ""),
    }
    github_repos.append(repo_data)
    github_lookup[full_name] = repo_data

hn_raw_items = []
hn_lookup = {}  # full_name → 热度 / 讨论链接，供卡片展示用
for r in hn_raw:
    full_name = f"[HN] {r['name']}"
    hn_url = r.get("hn_url") or f"https://news.ycombinator.com/item?id={r.get('id', '')}"
    item = {
        "name": full_name,
        "desc": r['desc'],
        "full_name": full_name,
        "url": r.get("url") or r['desc'],
        "hn_url": hn_url,
        "score": r.get("score", 0),
        "comments": r.get("comments", 0),
    }
    hn_raw_items.append(item)
    hn_lookup[full_name] = item

all_repos = github_repos + hn_raw_items

# 原始数据区域（也加上链接）
# 整篇文档只能有一个一级标题（# Weekly AI Report），这里统一从三级开始
raw_section = ""
raw_section += "### GitHub Trending\n\n"
for r in github_repos:
    meta_parts = []
    if r.get("language"):
        meta_parts.append(r["language"])
    if r.get("stars"):
        meta_parts.append(f"⭐ {r['stars']:,}")
    if r.get("growth"):
        meta_parts.append(r["growth"])
    meta = "　".join(meta_parts)
    raw_section += f"#### [{r['full_name']}]({r['url']})\n"
    if meta:
        raw_section += f"{meta}\n\n"
    raw_section += f"{r['desc']}\n\n"
raw_section += "### Hacker News 热门\n\n"
for r in hn_raw_items:
    raw_section += f"#### [{clean_id(r['name'])}]({r['url']})\n{r['desc']}\n\n"
# ============================================================
# AI 流水线
# ============================================================

# Step1: 结构化
print("🧠 Step1: 结构化分析...")
try:
    structured = explain_projects(all_repos)
    if not structured or len(structured) == 0:
        raise ValueError("Step1 返回空数据")
    print(f"   ✅ 成功获取 {len(structured)} 个结构化条目")
except Exception as e:
    print(f"❌ Step1 失败: {e}")
    exit(1)

# Step1.5: 深读（只对最值得动手的几个 GitHub 项目抓 README）
# 不把 HN 讨论帖放进深读：它没有 README，讨论帖也不存在「使用场景/选型优势」
DEEP_DIVE_COUNT = 5
print(f"🔍 Step1.5: 深读 {DEEP_DIVE_COUNT} 个项目...")
top_items = sorted(
    [it for it in structured if str(it.get("name", "")).startswith("[GitHub]")],
    key=lambda x: x.get("importance", 0),
    reverse=True,
)[:DEEP_DIVE_COUNT]
deep_materials = {}
for item in top_items:
    item_id = item.get("id", "")
    readme = fetch_readme(item_id)
    if readme:
        deep_materials[item_id] = readme
    print(f"   📄 {item_id}: README {len(readme)} 字符" if readme else f"   📄 {item_id}: 无 README")

deep_info = {}
try:
    deep_info = deep_dive(top_items, deep_materials)
    print(f"   ✅ 深读完成 {len(deep_info)} 条")
except Exception as e:
    print(f"   ⚠️ 深读失败（降级为普通摘要）: {e}")

# Step2: 趋势分析
print("📊 Step2: 趋势分析...")
try:
    # # 读取记忆库
    # memory_path = "Knowledge/projects.json"
    # if os.path.exists(memory_path):
    #     with open(memory_path, "r", encoding="utf-8") as f:
    #         memory = json.load(f)
    #     print(f"   📂 加载历史记忆: {len(memory)} 个项目")
    # else:
    #     memory = {}
    #     print("   📂 暂无历史记忆")
    # 读取记忆库（修复空文件问题）
    memory_path = os.path.join(VAULT_PATH, "Knowledge", "projects.json")
    memory = {}
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():  # 文件非空才解析
                    memory = json.loads(content)
                else:
                    print("   📂 记忆文件为空，初始化为空字典")
        except json.JSONDecodeError:
            print("   ⚠️ 记忆文件损坏，初始化为空字典")
            memory = {}

    history_context = get_trend_summary(memory, structured, week)
    analysis = analyze_trends(structured, history_context=history_context)
    
    if not analysis or not analysis.strip():
        raise ValueError("Step2 返回空内容")
    print("   ✅ 趋势分析完成")
except Exception as e:
    print(f"❌ Step2 失败: {e}")
    exit(1)

# Step3: 学习任务
print("🎯 Step3: 生成学习任务...")
try:
    tasks = generate_learning_tasks(structured)
    print("   ✅ 学习任务生成完成")
except Exception as e:
    print(f"⚠️ Step3 失败（非致命）: {e}")
    tasks = "学习任务生成失败，请稍后重试。"

# Step4: 趋势变化检测
print("📈 Step4: 趋势变化检测...")
try:
    trend_changes_table = detect_trend_changes(memory, week, structured)
    print("   ✅ 趋势变化检测完成")
except Exception as e:
    print(f"⚠️ Step4 失败（非致命）: {e}")
    trend_changes_table = "趋势变化检测失败。"

# Step5: 保存记忆
print("💾 Step5: 保存项目记忆...")
try:
    save_project_memory(structured, week)
    print("   ✅ 记忆保存完成")
except Exception as e:
    print(f"⚠️ Step5 失败（非致命）: {e}")

# ============================================================
# 组装报告
# ============================================================

# 统计信息
total_items = len(structured)
high_importance_items = [item for item in structured if item.get("importance", 0) >= 7]
categories = [item.get("category") for item in structured if item.get("category")]
category_counter = Counter(categories)
top_category = category_counter.most_common(1)[0] if category_counter else ("未知", 0)

# ---- 辅助函数 ----

def get_link(item, all_repos):
    """获取条目对应的链接"""
    item_id = item.get("id", "?")
    for repo in all_repos:
        if repo["full_name"] == item_id or repo["name"] == item.get("name", ""):
            return repo.get("url", "#")
    return "#"

def normalize_heading_level(text, target=3):
    """把 Markdown 文本最外层的标题统一到 target 级。

    AI 输出的小节标题层级不受控（有时 ##、有时 ###），直接拼进报告会让
    Obsidian 大纲面板里所有小节变成兄弟节点。这里按「当前最小层级」整体平移。
    """
    if not text:
        return text
    lines = text.splitlines()
    levels = []
    for ln in lines:
        m = re.match(r'^(#{1,6})\s', ln)
        if m:
            levels.append(len(m.group(1)))
    if not levels:
        return text
    delta = target - min(levels)
    if delta == 0:
        return text
    out = []
    for ln in lines:
        m = re.match(r'^(#{1,6})(\s.*)$', ln)
        if m:
            new_level = min(6, max(1, len(m.group(1)) + delta))
            out.append('#' * new_level + m.group(2))
        else:
            out.append(ln)
    return "\n".join(out)


def importance_badge(imp):
    """根据重要度返回视觉标记"""
    if imp >= 8:
        return f"🔥 {imp}"
    elif imp >= 5:
        return f"⭐ {imp}"
    else:
        return f"📎 {imp}"

def build_stats_line(item_id, github_lookup, hn_lookup):
    """卡片/表格共用的数据行：语言与 Star 增长，或 HN 分数与评论数"""
    gh = github_lookup.get(item_id)
    if gh:
        parts = []
        if gh.get("language"):
            parts.append(f"📝 **{gh['language']}**")
        if gh.get("stars"):
            parts.append(f"⭐ **{gh['stars']:,}**")
        if gh.get("growth"):
            parts.append(f"📈 **{gh['growth']}**")
        return ("　".join(parts) + "\n\n") if parts else ""
    hn = hn_lookup.get(item_id)
    if hn:
        parts = []
        if hn.get("score"):
            parts.append(f"🔥 **{hn['score']} 分**")
        if hn.get("comments"):
            parts.append(f"💬 **{hn['comments']} 条评论**")
        if hn.get("hn_url"):
            parts.append(f"[讨论区]({hn['hn_url']})")
        return ("　".join(parts) + "\n\n") if parts else ""
    return ""


def deep_info_for(item_id, deep_info):
    """按标识取深读结果。模型偶尔会改写 key（大小写、首尾空白），这里做宽松匹配。"""
    if not deep_info:
        return None
    if item_id in deep_info:
        return deep_info[item_id]
    target = str(item_id).strip().lower()
    for key, value in deep_info.items():
        if str(key).strip().lower() == target:
            return value
    return None


def as_callout(title, body, kind="note", collapsible=False):
    """把一段 markdown 包成 Obsidian callout。

    callout 自带边框、底色和图标，比「#### 标题 + --- 分隔线」干净得多，
    也给 CSS 片段留了统一的挂点（.callout[data-callout="example"]）。
    """
    marker = f"> [!{kind}]{'-' if collapsible else ''} {title}".rstrip()
    lines = [marker]
    for line in body.splitlines():
        lines.append("> " + line if line.strip() else ">")
    return "\n".join(lines) + "\n"


def card_title(item, link):
    """卡片标题行：**名称** · `分类` · 重要度badge"""
    item_id = item.get("id", "?")
    cat = item.get("category", "?")
    badge = importance_badge(item.get("importance", 0))
    return f"**[{clean_id(item_id)}]({link})** · `{cat}` · {badge}"


def build_card(item, link, stats_line):
    """普通卡片：完整描述 + 关注理由，用于非深读条目"""
    desc = (item.get("description_cn") or "").strip()
    reason = (item.get("reason") or "").strip()

    body = []
    if stats_line.strip():
        body += [stats_line.strip(), ""]
    if desc:
        body.append(desc)
    if reason:
        body += ["", f"💡 **关注理由**：{reason}"]

    return as_callout(card_title(item, link), "\n".join(body), "note")


def build_deep_card(item, link, stats_line, info):
    """「本周必看」的富卡片：是什么 / 什么时候用 / 比什么好 / 上手成本"""
    info = info or {}

    filled = []
    for label, key in (("是什么", "what"), ("什么时候用", "when"),
                       ("比什么好", "vs"), ("上手成本", "cost")):
        value = (info.get(key) or "").strip()
        # 模型偶尔会无视「留空」的要求，写回占位话，这里一并过滤
        if value and "素材不足" not in value:
            filled.append((label, value))

    # 深读字段不足两个（比如没抓到 README），退回普通卡片，
    # 避免出现「只有一行是什么」的半成品
    if len(filled) < 2:
        return build_card(item, link, stats_line)

    body = []
    if stats_line.strip():
        body += [stats_line.strip(), ""]
    # 用段落而不是列表：列表在 callout 里会再叠一层缩进，正文被推得很靠右
    body.append("\n\n".join(f"**{label}**　{value}" for label, value in filled))

    return as_callout(card_title(item, link), "\n".join(body), "example")

# ---- 分离 GitHub 和 HN ----

github_items = [item for item in structured if item.get("name", "").startswith("[GitHub]")]
hn_items = [item for item in structured if item.get("name", "").startswith("[HN]")]

github_items.sort(key=lambda x: x.get("importance", 0), reverse=True)
hn_items.sort(key=lambda x: x.get("importance", 0), reverse=True)

# ---- 数据大观：一行 callout，替代原来那个空表头的两列表格 ----

overview = as_callout(
    "📊 本周数据",
    f"📥 **{total_items}** 条（GitHub {len(github_items)} · HN {len(hn_items)}）"
    f"　·　🔥 高关注 **{len(high_importance_items)}** 条"
    f"　·　🏷️ 最热 **{top_category[0]}**（{top_category[1]} 次）",
    "info",
)

# ---- GitHub 项目卡片：前 5 条富卡片，其余全部用紧凑卡片 ----
# 一条不落：非深读条目也要有大模型写的描述，不能只剩表格一格 50 字
deep_ids = {str(it.get("id")) for it in top_items}

gh_section = f"### 🐙 GitHub Trending（{len(github_items)} 项）\n\n"
gh_repo_ids = []
for item in github_items:
    item_id = item.get("id", "")
    link = get_link(item, all_repos)
    stats = build_stats_line(item_id, github_lookup, hn_lookup)
    if str(item_id) in deep_ids:
        gh_section += build_deep_card(item, link, stats, deep_info_for(item_id, deep_info)) + "\n"
    else:
        gh_section += build_card(item, link, stats) + "\n"
    if item_id:
        gh_repo_ids.append(item_id)

gh_section += "\n"

# 追加一张合并的 Star 趋势图
if gh_repo_ids:
    combined_repos = ",".join(gh_repo_ids[:5])
    gh_section += f"""
### ⭐ Star 趋势总览

![Star History](https://api.star-history.com/svg?repos={combined_repos}&type=Date)

"""

# ---- HN 讨论卡片 ----
# 与 GitHub 一致：每条都给完整描述，而不是表格里一格截断的 60 字
hn_section = f"### 💬 Hacker News 热门（{len(hn_items)} 项）\n\n"
for item in hn_items:
    item_id = item.get("id", "?")
    link = get_link(item, all_repos)
    stats = build_stats_line(item_id, github_lookup, hn_lookup)
    hn_section += build_card(item, link, stats) + "\n"

# ---- 组装 ----

structured_section = f"""## 🧩 结构化摘要

{overview}
{gh_section}
{hn_section}"""

# ---- Obsidian Frontmatter ----

unique_categories = sorted(set(c for c in categories if c and c != "Other"))
tag_lines = "\n".join(f"  - {cat.lower()}" for cat in unique_categories)
date_str = datetime.now().strftime("%Y-%m-%d")

frontmatter = f"""---
date: {date_str}
week: "{week}"
tags:
  - weekly
{tag_lines}
github_count: {len(github_items)}
hn_count: {len(hn_items)}
high_importance: {len(high_importance_items)}
top_category: "{top_category[0]}"
cssclasses:
  - weekly-report
---

"""

# 统一 AI 输出的小节层级，避免和报告自身的一级/二级标题打架
analysis = normalize_heading_level(analysis, target=3)
tasks = normalize_heading_level(tasks, target=3)

# ---- 本周必看：一个 callout 装 5 行索引，正文在下方 GitHub 区（前 5 条即富卡片） ----
mr_lines = []
for i, item in enumerate(top_items, 1):
    item_id = item.get("id", "?")
    link = get_link(item, all_repos)
    headline = (item.get("reason") or item.get("description_cn") or "").strip()
    mr_lines.append(f"{i}. **[{clean_id(item_id)}]({link})**　{headline}")

mr_lines += ["", f"共 {total_items} 条见下方；前 5 条带「什么时候用 / 比什么好 / 上手成本」的深读。"]
must_read_section = as_callout("🎯 本周必看", "\n".join(mr_lines), "important") + "\n"

# ---- 原始数据：折叠 callout，不占正文滚动长度 ----
raw_callout = as_callout("📦 原始数据（点击展开）", raw_section, "quote", collapsible=True)

# 最终报告模板（用 callout 自带的分隔，不再堆 --- 横线）
content = f"""{frontmatter}# Weekly AI Report
**生成时间**：{week_display}

{must_read_section}
{structured_section}

## 🔥 技术趋势分析

{analysis}

## 📈 项目趋势变化

{trend_changes_table}

## ✅ 本周行动

{tasks}

{raw_callout}"""

# 写入文件
output_dir = os.path.join(VAULT_PATH, "Weekly")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, f"{week}.md")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n✅ 报告已生成: {output_path}")

# ---- 生成项目索引（Obsidian Dataview 兼容） ----
if github_lookup:
    index_lines = [
        "---",
        f"date: {date_str}",
        "type: project-index",
        "---",
        "",
        "# 📇 项目索引",
        "",
        f"> 自动生成 · 共追踪 {len(github_lookup)} 个项目 · {date_str} 更新",
        "",
        "| 项目 | 语言 | ⭐ Stars | 📈 周增长 | 分类 | 重要度 |",
        "|------|------|----------|-----------|------|--------|",
    ]
    for item in structured:
        item_id = item.get("id", "")
        if item_id not in github_lookup:
            continue
        gh = github_lookup[item_id]
        lang = gh.get("language", "-")
        stars = f"{gh['stars']:,}" if gh.get("stars") else "-"
        growth = gh.get("growth", "-")
        cat = item.get("category", "-")
        imp = item.get("importance", "-")
        index_lines.append(
            f"| [{item_id}](https://github.com/{item_id}) | {lang} | {stars} | {growth} | {cat} | {imp} |"
        )

    knowledge_dir = os.path.join(VAULT_PATH, "Knowledge")
    os.makedirs(knowledge_dir, exist_ok=True)
    index_path = os.path.join(knowledge_dir, "项目索引.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))
    print(f"✅ 项目索引已更新: {index_path}")