# PP-020 执行计划

按 executing-plans 顺序执行，版本化台账代替不可用的插件支持脚本；末尾一次 fresh-context 整分支审查，接受的重要问题单次 RED→GREEN 修复。

- [x] 从现有 JWT/SQLite HTTP fixture 建立范围拒绝无副作用、单位换算/局部更新、基准拒绝、完整性、零热值、极小基数回归；确认业务失败。
- [x] 实现共享 measurement contract、DTO 及双端输出；完整性与安全比值应用到质量引擎及比较接口，保留运输证据和状态优先级。
- [x] 修复前端响应读取、基准和缺项显示；完整后端、ruff、pip check、前端构建通过后推送，保存 implemented 检查点。
- [ ] 一次整分支审查及实际新会话恢复演练；重要问题先失败再修复，更新台账。固定候选 CI 成功后合并，复核 main CI。
- [ ] 更新中央发布索引/核心摘要，保存实际 merged/释放操作及下一批第一动作；在线核验和最终中央 CI。

## 执行台账

环境依赖安装尚未完成时首个基线命令因 pydantic_settings 缺失失败，仅为环境错误；安装完成后完整 110 passed。没有将依赖错误作为业务 RED。

初次业务 RED：82 个新 HTTP 回归，77 failed / 5 passed；额外极小基数数据库断言先 3 failed / 2 passed。实现后完整 192 passed（110 原有 + 82 新增），ruff E9/F63/F7/F82、pip check、TypeScript 与 Vite 构建通过。旧 all-none 单测的 COMPLETED 期待同步改为 PARTIAL，这是已由真实接口 RED 证明的预期行为变化。

不存在数据库迁移/历史回填；合同口径保持 canonical kcal/kg/%；输出口径对两处化验序列化均生效。运输处理历史和评分保留由旧/新 HTTP 回归覆盖。雷达仅双端六项有效值齐全时显示；构建通过，不声称浏览器或现场验收。

首次复现提交 4b95d183b040d0966373b21d95b7133949264226 已推送；候选等待一次整分支审查及实际 GitHub CI。
