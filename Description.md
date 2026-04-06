# Claude-TokenMonitor

| 字段 | 内容 |
|------|------|
| 项目ID | 20260407-001 |
| 中文别名 | Claude Token 监控器 |
| 创建日期 | 2026-04-07 |
| 最后修改 | 2026-04-07 |
| 当前版本 | 0.1.0 |
| 开发语言 | Python 3 |
| 依赖环境 | Python 3.8+，httpx，tkinter（内置） |
| 入口文件 | src/monitor.py |
| 运行命令 | `python src/monitor.py` |
| 项目状态 | 已完成 |

## 功能简介

Windows 桌面工具，监控 Anthropic API 账号的 Token 剩余量。
- 自动每 5 分钟刷新一次
- 显示时余量（短窗口）和周余量（长窗口，若 API 返回）
- 进度条 + 百分比颜色提示（≥50% 白色，20-50% 橙色，<20% 红色）
- 纯黑背景简洁 UI

## 标签
`#工具` `#监控` `#Claude` `#tkinter`

## 引用素材
无

## 已知问题 / TODO
- API Key 当前硬编码在 src/monitor.py 顶部，使用前需手动填入
- 若账号仅有单一 rate limit 窗口，周余量区块将自动隐藏

## 版本日志
- 0.1.0 - 2026-04-07 初始版本

## 备注
数据来源：Anthropic API 响应头 `anthropic-ratelimit-tokens-*`
