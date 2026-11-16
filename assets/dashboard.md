# 📊 技术周报看板

> 由 GitHub Actions 每周自动生成 · 本页查询依赖 [Dataview](https://github.com/blacksmithgu/obsidian-dataview) 插件

---

## 本周概览

```dataview
TABLE
  date as "日期",
  github_count + hn_count as "收录条目",
  high_importance as "🔥 高关注",
  top_category as "最热类别"
FROM "Weekly"
SORT date DESC
LIMIT 1
```

## 最近 8 周

```dataview
TABLE
  date as "日期",
  github_count as "GitHub",
  hn_count as "HN",
  high_importance as "🔥",
  top_category as "类别"
FROM "Weekly"
SORT date DESC
LIMIT 8
```

## 高关注趋势

```dataview
TABLE
  week as "周次",
  high_importance as "高关注数",
  top_category as "最热类别"
FROM "Weekly"
SORT date DESC
LIMIT 12
```

## 按标签找

```dataview
LIST
FROM #weekly
SORT file.name DESC
LIMIT 20
```

---

## 快捷入口

- [[Weekly/|周报归档]]
- [[Knowledge/项目索引|项目索引]]

---

*周报由 [weekly-tech-digest](https://github.com/JumpBear777/weekly-tech-digest) 生成*
