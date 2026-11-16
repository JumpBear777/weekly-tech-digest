"""抓取 GitHub 仓库的 README，作为「深读」的分析依据。

只用 raw.githubusercontent.com：走 CDN，不计入 GitHub API 的限流额度，
所以可以对几个精选项目放心请求。
"""
import requests

FILENAMES = ("README.md", "readme.md", "README.MD", "README.rst", "README", "Readme.md")
BRANCHES = ("HEAD", "main", "master")


def fetch_readme(full_name, max_chars=3000):
    """返回 README 前 max_chars 个字符；取不到时返回空字符串。

    依次尝试 HEAD / main / master 三个分支——有的仓库默认分支不是 main，
    而 HEAD 在部分仓库上也会 404。
    """
    for branch in BRANCHES:
        for name in FILENAMES:
            url = f"https://raw.githubusercontent.com/{full_name}/{branch}/{name}"
            try:
                resp = requests.get(url, timeout=10)
            except Exception as e:
                print(f"   ⚠️ README 请求异常 {full_name}: {e}")
                return ""
            if resp.status_code == 200 and resp.text.strip():
                return resp.text[:max_chars]
        # 拿到 404 说明该分支下确实没有这些文件，换分支继续
    return ""
