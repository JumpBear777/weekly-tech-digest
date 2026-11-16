import requests
import re
from bs4 import BeautifulSoup


def parse_number(text):
    """解析 GitHub 数字格式：'1,234' → 1234, '2.5k' → 2500"""
    text = text.strip().lower().replace(",", "")
    if "k" in text:
        return int(float(text.replace("k", "")) * 1000)
    return int(text)


def get_trending():
    url = "https://github.com/trending?since=weekly"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; weekly-report-bot)"
    }

    # 必须带超时：CI 里请求挂住会一直占着 runner，直到 job 超时才失败
    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    repos = []

    items = soup.find_all("article", class_="Box-row")
    if not items:
        raise RuntimeError(
            f"GitHub Trending 页面解析到 0 个仓库（HTTP {res.status_code}），"
            "可能被限流或页面结构已变更"
        )

    for item in items:
        # --- 项目名 ---
        h2 = item.find("h2", class_="h3")
        if not h2 or not h2.a:
            continue
        # "owner / repo" → "owner/repo"
        raw_name = h2.a.text.strip()
        full_name = re.sub(r"\s+/\s+", "/", raw_name)  # "owner / repo" → "owner/repo"
        display_name = full_name  # 用于展示

        # --- 描述 ---
        desc_elem = item.find("p", class_="col-9")
        desc = desc_elem.text.strip() if desc_elem else ""

        # --- 语言 ---
        lang_elem = item.find("span", itemprop="programmingLanguage")
        language = lang_elem.text.strip() if lang_elem else ""

        # --- 总 Star 数 ---
        stars_elem = item.find("a", href=lambda h: h and "/stargazers" in h)
        total_stars = 0
        if stars_elem:
            try:
                total_stars = parse_number(stars_elem.text.strip())
            except (ValueError, AttributeError):
                total_stars = 0

        # --- Forks ---
        forks_elem = item.find("a", href=lambda h: h and "/forks" in h)
        total_forks = 0
        if forks_elem:
            try:
                total_forks = parse_number(forks_elem.text.strip())
            except (ValueError, AttributeError):
                total_forks = 0

        # --- 本周 Star 增长 ---
        growth_elem = item.find("span", class_="d-inline-block float-sm-right")
        weekly_growth = ""
        if growth_elem:
            growth_text = growth_elem.text.strip()
            # 格式如 "1,234 stars this week", "123 stars today"
            match = re.search(r"([\d,]+)\s*stars?\s*(this\s*week|today)", growth_text, re.IGNORECASE)
            if match:
                count = match.group(1)
                period = match.group(2)
                weekly_growth = f"+{count} stars {period}"

        repos.append({
            "name": display_name,
            "full_name": full_name,
            "desc": desc,
            "language": language,
            "stars": total_stars,
            "forks": total_forks,
            "growth": weekly_growth,
        })

    # 抓到的数量异常少时直接失败，避免生成一份"0 项"的空气报告还照样提交
    if len(repos) < 5:
        raise RuntimeError(f"只解析到 {len(repos)} 个仓库，数据不完整，本次跳过")

    return repos


if __name__ == "__main__":
    data = get_trending()
    for d in data:
        print(d)
