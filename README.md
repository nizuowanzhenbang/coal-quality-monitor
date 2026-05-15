# 煤质化验数据比对系统

[English](#english) | [中文](#中文)

---

## 中文

### 项目简介

基于港口化验与入厂化验多维度数据比对的煤质异常检测与风险预警系统。通过自动分析热值、灰分、硫分、水分等关键质量指标的偏差，精准识别以次充好、货物掉包等运输舞弊风险。

### 核心功能

| 功能 | 说明 |
|------|------|
| **六维化验比对** | 热值 / 灰分 / 硫分 / 水分 / 挥发分 / 固定碳，港口 vs 入厂全面对比 |
| **智能预警引擎** | 固定阈值 + 合同违约双重检测，8种预警类型，严重/一般分级 |
| **综合异常识别** | 3项指标同时偏差自动触发「综合异常」预警（疑似以次充好）|
| **供应商信用评分** | 基于近20批次质量表现动态评分（0-100），支持黑名单管理 |
| **雷达图可视化** | 六维雷达图直观呈现港口 vs 入厂质量差距 |
| **热值散点图** | 理想线 vs 实际值散点，快速识别系统性偏差供应商 |
| **CSV 数据导出** | 批次对比数据 / 预警记录一键下载 |
| **WebSocket 实时推送** | 新预警秒级通知，侧边栏角标实时更新 |
| **闭环预警管理** | 待处理 → 已确认 → 已解决 全流程可追溯 |

### 预警规则

| 指标 | 一般预警 | 严重预警 |
|------|---------|---------|
| 热值亏损（港口>入厂） | 偏差率 > 1% | 偏差率 > 2% |
| 灰分偏高（入厂>港口） | 绝对偏差 > 0.80% | 绝对偏差 > 1.50% |
| 硫分偏高 | 绝对偏差 > 0.08% | 绝对偏差 > 0.15% |
| 水分偏高 | 绝对偏差 > 1.0% | 绝对偏差 > 2.0% |
| 热值违约（入厂 vs 合同） | 低于合同 > 200 kcal/kg | 低于合同 > 400 kcal/kg |
| 灰分超合同上限 | 超出 > 0.5% | 超出 > 1.0% |
| 硫分超合同上限 | 超出 > 0.05% | 超出 > 0.10% |
| **综合异常** | — | 3项以上指标同时偏差 |

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| 前端 | React 18 + TypeScript + Ant Design 5 |
| 可视化 | ECharts（雷达图 / 散点图 / 折线图 / 环形图）|
| 数据库 | SQLite（开发）/ PostgreSQL（生产）|
| 实时推送 | WebSocket（JWT 鉴权 + 指数退避重连）|
| 容器化 | Docker Compose |

### 快速开始

```bash
git clone https://github.com/woshiniba-debug/coal-quality-monitor.git
cd coal-quality-monitor

# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 生成演示数据（8个供应商 + 50批次 + 自动检测预警）
python seed_data.py

# 前端（新终端）
cd frontend
npm install
npm run dev
```

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 默认账户：`admin` / `admin123`

### 项目结构

```
coal-quality-monitor/
├── backend/
│   ├── app/
│   │   ├── api/          # REST API 路由（批次/化验/预警/供应商/仪表盘/导出/WebSocket）
│   │   ├── models/       # SQLAlchemy 数据模型
│   │   ├── services/     # 质量分析引擎 + 供应商评分器
│   │   └── utils/
│   ├── tests/            # pytest 单元测试（15+ 用例）
│   └── seed_data.py      # 演示数据生成
├── frontend/
│   └── src/
│       ├── pages/        # Dashboard / 批次列表 / 批次详情 / 预警中心 / 供应商管理
│       ├── hooks/        # useAlertWebSocket
│       └── types/        # 完整 TypeScript 类型定义
├── docker-compose.yml
└── Makefile
```

### 与汽车运煤监督系统的关系

本系统与 [coal-transport-monitor](https://github.com/woshiniba-debug/coal-transport-monitor) 构成燃煤采购监督的完整闭环：

```
港口出发 → [运输重量监督] → 入厂到达 → [化验质量比对]
            coal-transport-monitor        coal-quality-monitor
                  ↓                              ↓
           重量/时间/铅封预警              质量偏差/合同违约预警
```

---

## English

### Overview

A coal quality anomaly detection and risk warning system based on multi-dimensional comparison between port sampling and factory testing. Automatically analyzes deviations in calorific value, ash content, sulfur content, moisture and other key quality indicators to identify transportation fraud risks.

### Core Features

- **6-Dimension Quality Comparison**: Port vs Factory across calorific value / ash / sulfur / moisture / volatile matter / fixed carbon
- **Smart Alert Engine**: Dual detection (fixed threshold + contract breach), 8 alert types, 2 severity levels
- **Comprehensive Anomaly Detection**: 3+ simultaneous deviations → "Comprehensive Anomaly" alert (suspected substitution)
- **Supplier Credit Scoring**: Dynamic 0-100 scoring based on recent 20 batches; blacklist support
- **Radar Chart Visualization**: Intuitive 6-axis radar comparing port vs factory quality
- **Calorific Scatter Plot**: Ideal line vs actual, quickly identify systematic deviators
- **Real-time WebSocket Alerts**: Second-level push notifications with live badge updates

### License

MIT
