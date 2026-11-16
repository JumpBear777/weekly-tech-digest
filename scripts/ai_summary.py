import os
import requests
import time
from typing import List, Dict
import json
import re


DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")


class ApiClientError(RuntimeError):
    """4xx（密钥无效、参数错误等）：重试没有意义，直接失败"""

# def _call_deepseek(prompt: str, temperature: float = 0.3, max_retries: int = 2) -> str:
#     headers = {
#         "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "model": "deepseek-chat",
#         "messages": [{"role": "user", "content": prompt}],
#         "temperature": temperature
#     }
#     for attempt in range(max_retries + 1):
#         try:
#             resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)
#             resp.raise_for_status()
#             return resp.json()["choices"][0]["message"]["content"]
#         except Exception as e:
#             if attempt == max_retries:
#                 raise RuntimeError(f"API 调用最终失败: {e}")
#             time.sleep(1 * (attempt + 1))
#     return ""
def _call_deepseek(prompt: str, temperature: float = 0.3, max_retries: int = 2) -> str:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    if not DEEPSEEK_API_KEY:
        raise ApiClientError(
            "DEEPSEEK_API_KEY 未设置或为空：本地运行需先设置环境变量，"
            "CI 运行需在仓库 Settings → Secrets and variables → Actions 里配置"
        )

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=90)

            # 4xx 一律不重试：密钥失效/参数错误重试三次只会把日志刷得更乱
            if resp.status_code == 401 or resp.status_code == 403:
                raise ApiClientError(
                    f"API 鉴权失败({resp.status_code})：DEEPSEEK_API_KEY 无效或已被吊销。"
                    f"服务端返回：{resp.text[:300]}"
                )
            if 400 <= resp.status_code < 500:
                raise ApiClientError(
                    f"API 请求被拒绝({resp.status_code})：{resp.text[:400]}"
                )
            if resp.status_code >= 500:
                raise RuntimeError(f"服务端错误 {resp.status_code}: {resp.text[:300]}")

            content = resp.json()["choices"][0]["message"]["content"]
            
            # 关键检查：不允许返回空内容
            if not content or not content.strip():
                raise ValueError(f"API 返回了空内容 (attempt {attempt + 1})")
            
            return content
            
        except ApiClientError:
            raise
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"⚠️ API 调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                time.sleep(2 * (attempt + 1))
            else:
                raise RuntimeError(f"API 调用最终失败: {last_error}")

# def explain_projects(repos: List[Dict[str, str]]) -> str:
#     """
#     第一步：对混合信息源（GitHub 仓库 + HN 帖子）逐个生成技术解释
#     要求 repos 元素包含：
#         - name: 带前缀的项目名（如 [GitHub] xxx 或 [HN] xxx）
#         - desc: 描述（仓库描述或链接）
#         - full_name: 唯一标识（如 owner/repo 或 [HN] 标题）
#     """
#     projects_text = ""
#     for i, r in enumerate(repos, 1):
#         repo_id = r.get('full_name', r['name'])
#         projects_text += f"""
# {i}. 标识：{repo_id}
#    显示名：{r['name']}
#    描述/链接：{r['desc']}
# ---
# """
#     prompt = f"""
# 你是一个技术分析助手，负责解释来自多个来源的技术条目。

# 条目列表包含两类：
# - [GitHub] 开头的为代码仓库
# - [HN] 开头的为 Hacker News 热门讨论帖

# 请对每个条目单独解释，输出中文 Markdown。

# **硬性要求**：
# - 每个条目的解释必须以 `### 标识：xxx` 开头（xxx 为下方给出的“标识”字段，不得修改）
# - 对于 [GitHub] 条目：说明它的技术功能、核心方向，并打上技术标签（Agent / CV / LLM / DevTool / Infra / Data / Security / Web / Mobile / Other）
# - 对于 [HN] 条目：概括讨论的主题、主要观点或争议点，标签可用 Community / Discussion / Show / Ask 等
# - 不要做整体总结，不要合并条目

# 项目列表：
# {projects_text}
# """
#     return _call_deepseek(prompt, temperature=0.3)

def explain_projects(repos: List[Dict[str, str]]) -> List[Dict]:
    """
    返回结构化 JSON 列表（list of dicts），不再是纯文本。
    如果解析失败，降级返回空列表，避免中断流程。
    """
    # 构建项目文本
    projects_text = ""
    for i, r in enumerate(repos, 1):
        repo_id = r.get('full_name', r['name'])
        block = f"""
{i}. 标识：{repo_id}
   显示名：{r['name']}
   描述/链接：{r['desc']}
"""
        # GitHub 条目：语言 / Star / 本周增长一起喂给模型，重要度才有依据
        if r.get("stars") or r.get("language"):
            parts = []
            if r.get("language"):
                parts.append(f"语言 {r['language']}")
            if r.get("stars"):
                parts.append(f"总 Star {r['stars']:,}")
            if r.get("growth"):
                parts.append(f"本周增长 {r['growth']}")
            block += "   数据：" + "，".join(parts) + "\n"
        # HN 条目：热度靠分数和评论数判断
        if r.get("score"):
            block += f"   热度：{r['score']} 分 / {r.get('comments', 0)} 条评论\n"
        projects_text += block + "---\n"
    prompt = f"""
你是一个技术信息结构化分析系统。请分析以下条目，并严格按 JSON 数组输出，不要输出任何其他文字。

每个条目的 JSON 对象格式（所有字段必须存在）：
{{
  "id": "原样复制'标识'字段",
  "name": "原样复制'显示名'字段",
  "category": "Agent / LLM / CV / Infra / DevTool / Web / Security / Other",
  "description_cn": "用中文介绍该条目：它是什么、解决什么问题、亮点或争议点是什么（2-3 句通顺的中文，80-150 字，不要名词堆砌的电报体）",
  "importance": 1-10,
  "reason": "为什么该条目值得关注（一句话）"
}}

importance 评分建议（必须结合上面的「数据」「热度」字段判断，不要只看描述文字）：
- 8‑10：本周新增 Star 超过 5000，或总 Star 超过 2 万且本周仍在榜，或 HN 讨论极热（分数 500+）
- 5‑7：本周新增 Star 数百到数千的活跃项目，或有实质内容的热门讨论
- 1‑4：小众、信息量不足或临时性内容

分类规则：
- 只能从上面 8 个类别里选一个，不要自创
- HN 讨论帖按它讨论的技术主题归类（讨论数据库就归 Data→Infra，讨论安全事件就归 Security）
- 纯社会、政策、科普、娱乐类话题一律归 Other

要求：
1. 输出必须是单个合法 JSON 数组，以 [ 开头，以 ] 结尾
2. 不要包含 Markdown 代码块标记（如 ```json）
3. 所有字符串使用双引号
4. 用中文填写 description_cn 和 reason

条目列表：
{projects_text}
"""
    raw = _call_deepseek(prompt, temperature=0.2)  # 低温确保格式严格
    
    # 尝试提取 JSON 数组（容错处理）
    try:
        # 直接解析
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        # 尝试用正则提取最外层 [...] 
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
    
    print("⚠️ explain_projects JSON 解析失败，降级为空列表。原始输出：", raw[:200])
    return []

# def analyze_trends(explained_text: str) -> str:
#     """
#     第二步：基于解释文本（含 GitHub 和 HN 条目）进行趋势分析
#     """
#     prompt = f"""
# 你是一位资深计算机科学研究员。

# 下面是一份“已解释的技术条目列表”（Markdown 格式），其中混合了 [GitHub] 代码仓库和 [HN] 讨论帖。

# 请基于此进行本周技术趋势分析，并严格遵守一致性规则：

# 1. **趋势总结**（3-5 条）：需要结合工程项目和社区讨论的共振点；若某趋势只在 GitHub 或只在 HN 中出现，请明确指出。
# 2. **推荐最值得关注的 3 个条目**（可以混合推荐仓库和讨论帖）：
#    - 必须使用原始“标识”字段（如 `owner/repo` 或 `[HN] 标题`）
#    - 说明推荐理由，并与解释内容直接关联
# 3. **学习路线建议**（面向软件工程/AI方向学生）：可引用条目，同样必须使用标识。
# 4. 输出中文 Markdown，结构清晰，层级合理。

# 已解释条目如下：
# {explained_text}
# """
#     return _call_deepseek(prompt, temperature=0.7)

def analyze_trends(structured_data: List[Dict], history_context: str = "") -> str:
    """
    输入：explain_projects 返回的 JSON 列表
    输出：趋势分析 Markdown
    """
    # 将结构化数据转为紧凑 JSON 字符串，节省 token
    compact_json = json.dumps(structured_data, ensure_ascii=False)
    
    prompt = f"""
你是一位资深计算机科学研究员。以下是本周热门技术条目的结构化数据（JSON 格式）。

{"历史趋势参考：" + history_context if history_context else ""}

请基于这些信息和历史参考（如有）完成分析：

1. **本周技术趋势**（3‑4 条）
   - 结合 category 和 importance，识别高频方向
   - 注意 [GitHub] 项目与 [HN] 讨论的联动
   - 若有历史数据，指出哪些条目持续火热、哪些升温或降温

硬性约束：
- **只能引用「本周数据」里出现过的条目 id**；「历史趋势参考」只用于说明热度变化，
  不得把其中的项目当作本周条目推荐（曾出现把几周前下榜项目写进本周推荐的问题）
- **不要输出「学习路线」「最值得关注的 N 个条目」**：报告开头已有固定的必看列表，
  结尾另有「本周行动」复选框，再写会重复
- 输出中文 Markdown，不要直接输出整个 JSON 数组
- 小节标题一律使用三级标题(###)，禁止使用一级(#)和二级(##)标题

数据：
{compact_json}
"""
    return _call_deepseek(prompt, temperature=0.7)






def generate_learning_tasks(structured_data: List[Dict]) -> str:
    """
    基于结构化 JSON 数据，为高重要性项目生成具体学习任务。
    输入：explain_projects 返回的 JSON 列表
    输出：Markdown 格式的学习任务清单
    """
    # 只对最值得看的 3 个项目生成任务卡片：给 12 个项目各写三步路径，
    # 多半会退化成「读文档 / 跑 demo / 改代码」的模板话，篇幅还很长
    high_priority = sorted(
        [item for item in structured_data if item.get("importance", 0) >= 7],
        key=lambda x: x.get("importance", 0),
        reverse=True,
    )[:3]
    if not high_priority:
        return "⚠️ 本周没有 importance ≥ 7 的项目，暂无特定学习任务推荐。"

    # 将高优先级数据转 JSON 字符串，方便模型理解
    compact_json = json.dumps(high_priority, ensure_ascii=False)

    prompt = f"""
你是一位 AI 学习规划助手。以下是本周最值得动手的技术条目（JSON 格式）。

请为每一条输出**一行**行动项，格式严格如下：

- [ ] **{{id}}** —— 具体要做什么（预计 Xh）

要求：
- 每条只写一行，必须是当天就能开始、且能验收的动作
  （例：clone 后跑通 demo 并记录实际 star 数、读某个 issue 的争论并写下自己的判断）
- 禁止「阅读文档」「学习原理」「了解生态」这类无法验收的表述
- 耗时只用 1h / 3h / 6h
- 只输出这个复选框列表，不要标题、不要解释、不要 JSON
- 如果条目是 [HN] 讨论帖，动作要落在「读哪些评论、写下什么结论」

数据如下：
{compact_json}
"""
    return _call_deepseek(prompt, temperature=0.5)

def deep_dive(items, materials):
    """对少数精选条目做深读：是什么 / 什么时候用 / 比什么好 / 上手成本。

    items: 本周精选条目（约 5 条）
    materials: {标识: README 摘录}，没有 README 的条目（如 HN 讨论）留空
    返回: {标识: {"what":..., "when":..., "vs":..., "cost":...}}
    """
    if not items:
        return {}

    blocks = []
    for i, item in enumerate(items, 1):
        iid = item.get("id", "?")
        material = (materials.get(iid) or "").strip() or "（无 README，只有标题与热度数据）"
        blocks.append(
            f"""
{i}. 标识：{iid}
   分类：{item.get("category")}
   简介：{item.get("description_cn")}
   关注理由：{item.get("reason")}
   素材（README 摘录）：{material}
"""
        )

    schema = """{
  "owner/repo": {
    "what": "它是什么、解决什么问题（2-3 句通顺的中文）",
    "when": "什么时候该用它，必须是「如果……就……」句式，写出具体场景（2-3 句）",
    "vs": "相比哪个具体替代方案更好、好在哪里、代价是什么，必须点名一个竞品（2-3 句）",
    "cost": "上手成本：依赖、环境、要先准备什么、大约几小时（2 句）"
  }
}"""

    prompt = f"""你是资深技术选型顾问。请为下面每个条目写一段「能不能用、值不值得用」的判断。

输出严格的 JSON 对象（以 {{ 开头），key 是条目标识，value 结构如下：

{schema}

硬性要求：
- 只输出 JSON，不要 Markdown 代码块标记，不要任何解释
- 只写下面给出的条目，不要新增条目
- **每个字段 60-150 字，写成完整通顺的中文句子**；不要「名词+逗号」的电报体，
  像「提供组件、主题和CLI，让UI与AI Agent共用规范」这种写法不合格
- 禁止「更轻量」「更灵活」「生态成熟」「性能优秀」这类没有信息量的形容词：
  写优势必须点名一个具体替代方案（如 shadcn/ui、LangChain、Docker），并说明代价
- **素材不足以判断某个字段时，把该字段设为空字符串 ""**，
  绝对不要写「素材不足」「需看文档」这类占位文字
- 全部用中文

条目：
{"".join(blocks)}
"""
    raw = _call_deepseek(prompt, temperature=0.2)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"深读结果不是合法 JSON：{raw[:200]}")
        data = json.loads(match.group())
    return data if isinstance(data, dict) else {}

