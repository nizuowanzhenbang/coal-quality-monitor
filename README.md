# 煤里的"测谎仪" · 煤质化验数据比对系统

> 🕵️ 一船煤从港口装船到电厂卸车，路上发生了什么很难讲——同一批煤，港口化验热值 5800 kcal/kg，进厂复检只剩 5400 kcal/kg；港口灰分 12%，进厂涨到 14.5%。是装错船？洒了？还是被人在路上"调包"换了次煤？电厂每多花一吨次煤，少发的电、多排的污染、多扣的合同款，全是钱。

**这套系统把港口化验和入厂化验的数据放一起"过堂"**：6 个维度（热值 / 灰分 / 硫分 / 水分 / 挥发分 / 固定碳）逐项比对，偏差超过阈值当场亮红灯；3 项以上同时偏差自动盖"综合异常"章（疑似以次充好）；同时拿入厂数据对照合同约定的质量基准，超出违约线立刻打"合同违约"预警。供应商按近 20 批的表现自动打 0–100 信用分，质量稳定的排前面、长期掉链子的进黑名单。

> ⚠️ **免责声明**：本系统是 **厂内质量监督工具**，不能替代国家煤炭质检中心 / 第三方检测机构出具的法定化验报告，不能作为合同索赔的唯一证据。

---

## ⚡ 30 秒看明白你能用它做什么

| 你是谁 | 它帮你做什么 |
|---|---|
| 🧪 化验员 | 港口/入厂化验数据录入或 CSV 批量导入，自动触发比对评估 |
| ⚠️ 质量监督员 | 看预警中心，确认/解决预警，闭环留痕 |
| 🤝 燃料采购 | 拉供应商信用分，质量差的下次询价靠后；月报里看哪家供应商最稳 |
| 📊 燃料部主任 | 大屏看月度合规率、预警分布、供应商表现榜，例会数据直接拿 |
| 🛡️ 审计/纪检 | 看操作审计日志，谁改过化验数据、谁处理过预警，全程留痕 |

---

## ✨ 核心场景

### 🎯 六维化验比对：哪一项不对都跑不掉

| 指标 | 一般预警 | 严重预警 |
|---|---|---|
| 热值亏损（港口 > 入厂） | 偏差率 > 1% | 偏差率 > 2% |
| 灰分偏高（入厂 > 港口） | 绝对偏差 > 0.80% | 绝对偏差 > 1.50% |
| 硫分偏高 | 绝对偏差 > 0.08% | 绝对偏差 > 0.15% |
| 水分偏高 | 绝对偏差 > 1.0% | 绝对偏差 > 2.0% |
| 热值违约（入厂 vs 合同） | 低于合同 > 200 kcal/kg | 低于合同 > 400 kcal/kg |
| 灰分超合同上限 | 超出 > 0.5% | 超出 > 1.0% |
| 硫分超合同上限 | 超出 > 0.05% | 超出 > 0.10% |
| **综合异常** | — | **3 项以上指标同时偏差** |

> 💡 **为什么单看一项不够？**
> 路上掺一点煤矸石——灰分会涨、热值会跌、硫分可能也变。如果单看灰分还没超阈值就放过，结果三项小偏差合起来就是大问题。所以系统会专门盯"多项同时偏差"，触发"综合异常"标红——这是**最像"换货"的特征**。

### 🚦 预警闭环：从发现到解决全留痕
```
新预警（NEW） → 已确认（CONFIRMED） → 已解决（RESOLVED）
```
- WebSocket 实时推送，侧边栏角标秒级更新
- 每个预警都有处理人 / 处理时间 / 处理备注

### 🏆 供应商信用分（0–100）
- 基于近 **20 批**质量表现动态打分
- 长期掉链子 → 进**黑名单**，采购系统拉黑后下次询价直接屏蔽
- 通过 webhook 实时推送给[燃料采购系统](https://github.com/nizuowanzhenbang/fuel-procurement)影响其供应商排序

### 📊 可视化看板
- **6 维雷达图**：港口 vs 入厂质量差距一眼看出
- **热值散点图**：理想线 vs 实际值，系统性掉链子的供应商自动浮出来
- **月度报表**：环比 / 预警分布饼图 / 供应商表现榜

### 📥 CSV 批量导入 + 🛡️ 操作审计
- 化验数据多？CSV 一次性导入，自动建供应商/批次/触发评估
- 关键写操作（化验录入 / 评估 / 预警处理）全部记 AuditLog，满足合规审计

---

## 🚀 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt
python seed_data.py                  # 演示数据：8 供应商 + 50 批次 + 自动检测预警
uvicorn app.main:app --reload --port 8002

# 前端
cd frontend
npm install
npm run dev                          # http://localhost:5176
```

打开前端 → 用 `admin / admin123` 登录。

> 🔒 生产部署请务必删掉 seed 用户、改强密码。

---

## 🛠️ 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI · SQLAlchemy 2.0 · Pydantic v2 |
| 前端 | React 18 · TypeScript · Ant Design 5 |
| 可视化 | ECharts（雷达图 / 散点图 / 折线图 / 环形图 / 柱状图） |
| 数据 | SQLite（开发）/ PostgreSQL（生产） |
| 实时推送 | WebSocket（JWT 鉴权 + 指数退避重连） |
| 容器化 | Docker Compose |

## 📁 目录结构

```
coal-quality-monitor/
├── backend/
│   ├── app/
│   │   ├── api/          # 批次 / 化验 / 预警 / 供应商 / 仪表盘 / 导出 / 审计 / 报表 / 导入
│   │   ├── models/       # SQLAlchemy 模型（含 AuditLog）
│   │   ├── services/     # 质量分析引擎 + 供应商评分器 + 审计服务
│   │   └── utils/
│   ├── tests/
│   └── seed_data.py
├── frontend/
│   └── src/
│       ├── pages/        # Dashboard / 批次 / 预警中心 / 供应商 / 月度报表 / 数据导入 / 审计日志
│       ├── hooks/        # useAlertWebSocket
│       └── types/
├── docker-compose.yml
└── Makefile
```

---

## 🔗 智慧发电厂全家桶中的位置

本项目是 [smart-power-plant](https://github.com/nizuowanzhenbang/smart-power-plant) 七大子系统中的"煤质化验"模块。已对接：

| 系统 | 关系 |
|---|---|
| [coal-transport-monitor](https://github.com/nizuowanzhenbang/coal-transport-monitor) | 上游链路：运输异常 + 质量异常合起来看 |
| [fuel-procurement](https://github.com/nizuowanzhenbang/fuel-procurement) | 双向：推送供应商信用分 + 暴露 `/api/integration/order-quality` 给采购拉化验结果 |
| [coal-yard-management](https://github.com/nizuowanzhenbang/coal-yard-management) | 暴露 `/api/integration/order-quality-summary` 给煤场入场登记自动拉化验数据 |

构成"运输 → 质量 → 采购 → 库存"四联动闭环：

```
港口装船 → [coal-transport-monitor: 重量/时间/铅封监督]
        ↓
   入厂到货 → [coal-quality-monitor: 化验比对] ← 本系统
        ↓
   质量信用分 → [fuel-procurement: 影响供应商排序]
        ↓
   入煤场 → [coal-yard-management: 拉化验数据落批次]
```

## 📜 License

私有项目，未开源。


## 持续维护

2026-10-04：化验重评只替换质量引擎生成的预警，保留运输重量、超时、铅封预警及其处理记录。批次状态、预警数量和风险评分包含保留的运输预警，供应商重算不会丢失运输扣分。实际接口与数据库回归见[运输预警重评保护](docs/TRANSPORT-ALERT-REEVALUATION.md)。

[开发与验收说明](docs/MAINTENANCE.md)：自动检查、回归测试与演示边界。
