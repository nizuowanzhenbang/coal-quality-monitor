# PP-055 两端契约持续回归

目标：在煤质仓库CI实际运行煤质导出API和固定能效版本的预览API，检查真实导出能被消费、来源/时间/单位不丢失，及错配拒绝。两端app包重名、依赖版本不同，使用两个独立Python进程与独立SQLite，JSON经标准输入传递；不能模拟能效API。能效checkout固定到已合并30e8e6af92d796d6889875ec55b1de24c1ca13fe；依赖使用各仓库现有requirements，网络无法安装时CI失败而非跳过。

来源接口返回的时间声明依据保留在调用端并验证；当前能效measurement契约不接收该字段，不宣称预览持久保存依据。所有数据合成，无自动传输、现场或真实入炉证明。测试同时验证修改实例/批次或指标拒绝、重复调用不写运行快照、未知来源时间拒绝。成功4000 kcal/kg→16747.2 kJ/kg。

文件：backend/tests/contract_coal_energy.py构造合成源记录并调用真实导出，将其输出交给独立能效进程；backend/tests/energy_peer.py运行真实能效FastAPI TestClient和SQLite，返回结果；.github/workflows/quality.yml追加独立job及固定checkout。步骤：先新增跨系统测试并运行，因peer不存在失败；实现peer/CI后目标测试通过，人工破坏契约应失败；执行两端相关回归、审查、CI、PR/default验收并登记证据。缺少对端路径时明确失败，不放入普通后端测试自动发现。
