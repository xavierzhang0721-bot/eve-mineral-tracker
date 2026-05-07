# 🦞 EVE 欧服矿物价格追踪

追踪 The Forge (Jita) 8种矿物的每日价格，全自动更新。

🌐 **公网地址: https://xavierzhang0721-bot.github.io/eve-mineral-tracker/**

## 矿物列表

Tritanium · Pyerite · Mexallon · Isogen · Nocxium · Zydrine · Megacyte · Morphite

## 快速开始

### 查看网站

```bash
cd ~/.../eve-mineral-tracker
bash serve.sh
```

浏览器打开 **http://localhost:8080**

### 手动更新数据

```bash
python3 scraper.py
```

## 自动更新

每天 **08:00 AM（北京时间）** 自动运行爬虫。

```bash
# 查看定时任务状态
launchctl list | grep mineral

# 手动触发一次
launchctl start com.eve.mineral-tracker

# 停止自动更新
launchctl unload ~/Library/LaunchAgents/com.eve.mineral-tracker.plist
```

日志在 `logs/` 目录下。

## 数据来源

- 当日价格: **Janice** (https://janice.e-351.com) Jita 4-4 实时报价
- 历史数据: EVE ESI API (/markets/history/) 补全
- 存储: data/prices.json

## 项目文件

```
eve-mineral-tracker/
├── index.html          # 前端页面（图表+极值表）
├── scraper.py          # 数据采集脚本
├── serve.sh            # 本地预览启动脚本
├── data/
│   └── prices.json     # 所有价格数据
└── logs/               # 定时任务日志
```
