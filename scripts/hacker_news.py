import requests
from typing import List, Dict

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


def get_hn_top(limit: int = 10) -> List[Dict]:
    """
    获取 Hacker News 当前热门帖子。

    每个元素包含：
        name      标题
        desc      原文链接（Ask HN / Show HN 这类自帖回退到讨论页）
        id        HN item id
        url       原文链接
        hn_url    讨论页链接
        score     得分
        comments  评论数
    """
    try:
        ids = requests.get(HN_TOP_STORIES_URL, timeout=15).json()
    except Exception as e:
        print(f"获取 HN 热门列表失败: {e}")
        return []

    results = []
    for story_id in ids[:limit]:
        try:
            item = requests.get(HN_ITEM_URL.format(story_id), timeout=15).json()
        except Exception as e:
            print(f"获取 HN 条目 {story_id} 失败: {e}")
            continue

        if not item or item.get("deleted") or item.get("dead"):
            continue

        hn_url = f"https://news.ycombinator.com/item?id={story_id}"
        article_url = item.get("url") or hn_url

        results.append({
            "name": item.get("title", "No title"),
            "desc": article_url,
            "id": story_id,
            "url": article_url,
            "hn_url": hn_url,
            "score": item.get("score", 0),
            "comments": item.get("descendants", 0),
        })

    return results
