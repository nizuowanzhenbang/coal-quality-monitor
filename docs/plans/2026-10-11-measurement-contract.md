# PP-020 执行计划

按 executing-plans 顺序执行，版本化台账代替不可用的插件支持脚本；末尾一次 fresh-context 整分支审查，接受的重要问题单次 RED→GREEN 修复。

- [x] 从现有 JWT/SQLite HTTP fixture 建立范围拒绝无副作用、单位换算/局部更新、基准拒绝、完整性、零热值、极小基数回归；确认业务失败。
- [x] 实现共享 measurement contract、DTO 及双端输出；完整性与安全比值应用到质量引擎及比较接口，保留运输证据和状态优先级。
- [x] 修复前端响应读取、基准和缺项显示；完整后端、ruff、pip check、前端构建通过后推送，保存 implemented 检查点。
- [x] 尝试一次独立整分支审查并完成新会话恢复；最终报告受限的边界已记录，收到的重要问题先失败再修复。父代理检查、候选 CI 和实际 main CI 通过后合并。
- [x] 更新中央发布索引/核心摘要，保存实际 merged/释放操作及下一批第一动作；在线核验和最终中央 CI。

## 执行台账

环境依赖安装尚未完成时首个基线命令因 pydantic_settings 缺失失败，仅为环境错误；安装完成后完整 110 passed。没有将依赖错误作为业务 RED。

初次业务 RED：82 个新 HTTP 回归，77 failed / 5 passed；额外极小基数数据库断言先 3 failed / 2 passed。实现后完整 192 passed（110 原有 + 82 新增），ruff E9/F63/F7/F82、pip check、TypeScript 与 Vite 构建通过。旧 all-none 单测的 COMPLETED 期待同步改为 PARTIAL，这是已由真实接口 RED 证明的预期行为变化。

不存在数据库迁移/历史回填；合同口径保持 canonical kcal/kg/%；输出口径对两处化验序列化均生效。运输处理历史和评分保留由旧/新 HTTP 回归覆盖。雷达仅双端六项有效值齐全时显示；构建通过，不声称浏览器或现场验收。

首次复现提交 4b95d183b040d0966373b21d95b7133949264226 已推送；候选等待一次整分支审查及实际 GitHub CI。

## 一次独立审查与修复

Reviewer 在固定 56c3a176 分支复跑完整 192 项并核对 PR #4 候选 CI 38122605644 成功，返回两个已复现 Important：MJ/kg 超大 JSON 整数触发 float 转换 OverflowError，创建/修改、净/高热值均变 500；科学计数法合同值被详情页字符串清理误解析，显示假达标/假超标。全部接受。后端新回归先 4 failed/4 passed；实际 AntD 合同标签渲染回归先 2 failed/4 passed，再修复转换异常和数值比较。输入单位、基准及缺项语义保留。

审查者最终报告因用量限制未生成；不声称取得完整独立审查批准。父代理继续检查全分支和回归，按用户“继续完成”授权集成，保留该验证边界；没有重新启动第二次整分支审查。收到的两项 Important 无拒绝或延期，TASKS 旧第一动作 Minor 已修正。

前端增加 Node 内置测试及已有 esbuild 的显式开发依赖，测试实际渲染标签；CI 在构建前运行六项回归。第一次 Node --test 输出文件位于 node_modules，被 Node24 的发现规则排除；改为 .test-output 并忽略生成物后才取得业务 RED，未把 runner 路径错误作为业务失败。

修复后的实际验证：完整后端 201 passed，前端六项 AntD 标签渲染 6 passed，TypeScript/Vite 构建、ruff、pip check 和 diff 检查通过。父代理检查了整个范围的 DTO、两处序列化、评估/运输保留、React 数值传递及 CI 配置，未将最终报告受限写成独立批准。修复候选将推送并以实际 SHA/检查验收；最后两项集成/签收待发布后关闭。

## 发布签收

实际 PR #4 squash 合并 26bdbef9360e7b2ea2f037114adbf63ffdabb947；修复候选 CI 38141089655 与合并 main CI 38141214245 的 backend/frontend 全成功。中央 merged 状态提交 04650d970563025f245c4e8a1131d1c201c60c1d，release 8bffef3b032e8b269883c58aa618c96a9f2879e9。中央最终摘要/发布索引签收 37914694644c6730573018d4e0683247d973b7e1，其 Progress checks 38141498168 成功；在线核验五个明确索引的交付通过。

本批四项完成，SESSION 无活动认领；下一批 PP-030/040 均待核查。后续从 [中央 CURRENT](https://github.com/nizuowanzhenbang/smart-power-plant/blob/main/progress/CURRENT.md) 与 SESSION 接续，不重复本计划已验收阶段。最终独立审查报告未生成的验证边界保持，未写成完整独立批准。
