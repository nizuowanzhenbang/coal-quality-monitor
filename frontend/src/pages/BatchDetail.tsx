import { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  Descriptions,
  Tag,
  Table,
  Button,
  Space,
  Typography,
  Spin,
  message,
  Modal,
  Input,
  Divider,
} from 'antd'
import {
  ArrowLeftOutlined,
  CheckOutlined,
  CloseOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useParams, useNavigate } from 'react-router-dom'
import { batchApi, alertApi } from '../api'
import type { CoalBatch, QualityTest, QualityAlert, BatchStatus, AlertType, Severity, AlertStatus } from '../types'

const { Title, Text } = Typography

const BATCH_STATUS_MAP: Record<BatchStatus, { label: string; color: string }> = {
  PENDING: { label: '待化验', color: 'default' },
  PARTIAL: { label: '部分完成', color: 'processing' },
  COMPLETED: { label: '已完成', color: 'success' },
  ALERT: { label: '预警', color: 'warning' },
  SEVERE: { label: '严重', color: 'error' },
}

const ALERT_TYPE_LABEL: Record<AlertType, string> = {
  CALORIFIC_SHORTAGE: '热值亏损',
  ASH_EXCESS: '灰分偏高',
  SULFUR_EXCESS: '硫分偏高',
  MOISTURE_EXCESS: '水分偏高',
  CONTRACT_CAL_BREACH: '热值违约',
  CONTRACT_ASH_BREACH: '灰分违约',
  CONTRACT_SULFUR_BREACH: '硫分违约',
  COMPREHENSIVE: '综合异常',
  TRANSPORT_WEIGHT: '运输重量异常',
  TRANSPORT_TIME: '运输超时',
  TRANSPORT_SEAL: '铅封异常',
}

const ALERT_STATUS_LABEL: Record<AlertStatus, { label: string; color: string }> = {
  PENDING: { label: '待处理', color: 'warning' },
  ACKNOWLEDGED: { label: '已确认', color: 'processing' },
  RESOLVED: { label: '已解决', color: 'success' },
  DISMISSED: { label: '已忽略', color: 'default' },
}

interface CompareRow {
  key: string
  label: string
  portValue: number | null
  factoryValue: number | null
  contractStd: string | null
  unit: string
  higherIsBetter: boolean
}

// 归一化到 0-100 分，用于雷达图
function normalize(value: number | null, min: number, max: number): number {
  if (value === null) return 0
  return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100))
}

export default function BatchDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [batch, setBatch] = useState<CoalBatch | null>(null)
  const [loading, setLoading] = useState(true)
  const [messageApi, contextHolder] = message.useMessage()

  // 处理弹窗
  const [resolveModal, setResolveModal] = useState<{ open: boolean; alertId: number }>({ open: false, alertId: 0 })
  const [resolveNotes, setResolveNotes] = useState('')

  const fetchBatch = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const res = await batchApi.get(Number(id))
      setBatch(res.data.data)
    } catch {
      messageApi.error('加载批次详情失败')
    } finally {
      setLoading(false)
    }
  }, [id, messageApi])

  useEffect(() => {
    fetchBatch()
  }, [fetchBatch])

  const portTest = batch?.tests?.find((t) => t.test_type === 'PORT') ?? null
  const factoryTest = batch?.tests?.find((t) => t.test_type === 'FACTORY') ?? null

  // 雷达图配置
  const radarOption: EChartsOption = (() => {
    const indicators = [
      { name: '热值(Qnet)', max: 100 },
      { name: '灰分(Ad)', max: 100 },
      { name: '硫分(St,d)', max: 100 },
      { name: '水分(Mt)', max: 100 },
      { name: '挥发分(Vdaf)', max: 100 },
      { name: '固定碳(FC)', max: 100 },
    ]

    // 热值：4000-8000 kcal/kg，越高越好，归一化正向
    // 灰分、硫分、水分：越低越好，需要反向（100 - normalized）
    // 挥发分：范围 5-50%
    // 固定碳：30-80%

    const portValues = [
      normalize(portTest?.calorific_value_net ?? null, 4000, 8000),
      100 - normalize(portTest?.ash_content ?? null, 5, 40),
      100 - normalize(portTest?.sulfur_content ?? null, 0.1, 3),
      100 - normalize(portTest?.moisture_total ?? null, 2, 20),
      normalize(portTest?.volatile_matter ?? null, 5, 50),
      normalize(portTest?.fixed_carbon ?? null, 30, 80),
    ]

    const factoryValues = [
      normalize(factoryTest?.calorific_value_net ?? null, 4000, 8000),
      100 - normalize(factoryTest?.ash_content ?? null, 5, 40),
      100 - normalize(factoryTest?.sulfur_content ?? null, 0.1, 3),
      100 - normalize(factoryTest?.moisture_total ?? null, 2, 20),
      normalize(factoryTest?.volatile_matter ?? null, 5, 50),
      normalize(factoryTest?.fixed_carbon ?? null, 30, 80),
    ]

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const p = params as { name: string; value: number[] }
          return p.name
        },
      },
      legend: {
        data: ['港口化验', '入厂化验'],
        bottom: 0,
      },
      radar: {
        indicator: indicators,
        radius: '65%',
        splitNumber: 4,
        axisName: { color: '#555', fontSize: 12 },
        splitArea: { areaStyle: { color: ['rgba(0,0,0,0.02)', 'rgba(0,0,0,0.04)'] } },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              name: '港口化验',
              value: portValues,
              lineStyle: { color: '#1677ff' },
              areaStyle: { color: 'rgba(22,119,255,0.15)' },
              itemStyle: { color: '#1677ff' },
            },
            {
              name: '入厂化验',
              value: factoryValues,
              lineStyle: { color: '#ff4d4f' },
              areaStyle: { color: 'rgba(255,77,79,0.15)' },
              itemStyle: { color: '#ff4d4f' },
            },
          ],
        },
      ],
    }
  })()

  // 对比明细表格数据
  const compareRows: CompareRow[] = [
    {
      key: 'calorific',
      label: '热值 (Qnet)',
      portValue: portTest?.calorific_value_net ?? null,
      factoryValue: factoryTest?.calorific_value_net ?? null,
      contractStd: batch?.contract_calorific_value !== null && batch?.contract_calorific_value !== undefined
        ? `≥${batch.contract_calorific_value}`
        : null,
      unit: 'kcal/kg',
      higherIsBetter: true,
    },
    {
      key: 'ash',
      label: '灰分 (Ad)',
      portValue: portTest?.ash_content ?? null,
      factoryValue: factoryTest?.ash_content ?? null,
      contractStd: batch?.contract_ash_max !== null && batch?.contract_ash_max !== undefined
        ? `≤${batch.contract_ash_max}`
        : null,
      unit: '%',
      higherIsBetter: false,
    },
    {
      key: 'sulfur',
      label: '硫分 (St,d)',
      portValue: portTest?.sulfur_content ?? null,
      factoryValue: factoryTest?.sulfur_content ?? null,
      contractStd: batch?.contract_sulfur_max !== null && batch?.contract_sulfur_max !== undefined
        ? `≤${batch.contract_sulfur_max}`
        : null,
      unit: '%',
      higherIsBetter: false,
    },
    {
      key: 'moisture',
      label: '水分 (Mt)',
      portValue: portTest?.moisture_total ?? null,
      factoryValue: factoryTest?.moisture_total ?? null,
      contractStd: batch?.contract_moisture_max !== null && batch?.contract_moisture_max !== undefined
        ? `≤${batch.contract_moisture_max}`
        : null,
      unit: '%',
      higherIsBetter: false,
    },
    {
      key: 'volatile',
      label: '挥发分 (Vdaf)',
      portValue: portTest?.volatile_matter ?? null,
      factoryValue: factoryTest?.volatile_matter ?? null,
      contractStd: null,
      unit: '%',
      higherIsBetter: true,
    },
    {
      key: 'fixedcarbon',
      label: '固定碳 (FC)',
      portValue: portTest?.fixed_carbon ?? null,
      factoryValue: factoryTest?.fixed_carbon ?? null,
      contractStd: null,
      unit: '%',
      higherIsBetter: true,
    },
  ]

  const compareColumns: ColumnsType<CompareRow> = [
    {
      title: '指标',
      dataIndex: 'label',
      key: 'label',
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '港口化验值',
      key: 'portValue',
      align: 'center',
      render: (_: unknown, row: CompareRow) =>
        row.portValue !== null ? `${row.portValue} ${row.unit}` : '-',
    },
    {
      title: '入厂化验值',
      key: 'factoryValue',
      align: 'center',
      render: (_: unknown, row: CompareRow) => {
        if (row.factoryValue === null) return '-'
        const deviation =
          row.portValue !== null && row.portValue !== 0
            ? ((row.factoryValue - row.portValue) / row.portValue) * 100
            : null
        const isAbnormal =
          deviation !== null &&
          (row.higherIsBetter ? deviation < -2 : deviation > 2)
        return (
          <div
            style={{
              background: isAbnormal ? 'rgba(255,77,79,0.12)' : 'transparent',
              padding: '2px 8px',
              borderRadius: 4,
            }}
          >
            <Text style={{ color: isAbnormal ? '#ff4d4f' : 'inherit' }}>
              {row.factoryValue} {row.unit}
            </Text>
          </div>
        )
      },
    },
    {
      title: '偏差',
      key: 'deviation',
      align: 'center',
      render: (_: unknown, row: CompareRow) => {
        if (row.portValue === null || row.factoryValue === null) return '-'
        const diff = row.factoryValue - row.portValue
        const rate = (diff / row.portValue) * 100
        const isPositive = diff >= 0
        const isGood = row.higherIsBetter ? isPositive : !isPositive
        return (
          <Text style={{ color: isGood ? '#52c41a' : '#ff4d4f' }}>
            {isPositive ? '+' : ''}{diff.toFixed(2)} {row.unit}
            {' '}({rate >= 0 ? '+' : ''}{rate.toFixed(2)}%)
          </Text>
        )
      },
    },
    {
      title: '合同标准',
      key: 'contractStd',
      align: 'center',
      render: (_: unknown, row: CompareRow) =>
        row.contractStd !== null ? `${row.contractStd} ${row.unit}` : '-',
    },
    {
      title: '状态',
      key: 'contractStatus',
      align: 'center',
      render: (_: unknown, row: CompareRow) => {
        if (row.contractStd === null || row.factoryValue === null) return <Tag>-</Tag>
        const stdNum = parseFloat(row.contractStd.replace(/[^0-9.]/g, ''))
        const isOk = row.higherIsBetter
          ? row.factoryValue >= stdNum
          : row.factoryValue <= stdNum
        return <Tag color={isOk ? 'green' : 'red'}>{isOk ? '达标' : '超标'}</Tag>
      },
    },
  ]

  const handleAcknowledge = useCallback(
    async (alertId: number) => {
      try {
        await alertApi.acknowledge(alertId)
        messageApi.success('已确认')
        fetchBatch()
      } catch {
        messageApi.error('操作失败')
      }
    },
    [messageApi, fetchBatch],
  )

  const handleResolve = useCallback(async () => {
    try {
      await alertApi.resolve(resolveModal.alertId, resolveNotes)
      messageApi.success('已处理')
      setResolveModal({ open: false, alertId: 0 })
      setResolveNotes('')
      fetchBatch()
    } catch {
      messageApi.error('操作失败')
    }
  }, [resolveModal.alertId, resolveNotes, messageApi, fetchBatch])

  const handleDismiss = useCallback(
    async (alertId: number) => {
      try {
        await alertApi.dismiss(alertId)
        messageApi.success('已忽略')
        fetchBatch()
      } catch {
        messageApi.error('操作失败')
      }
    },
    [messageApi, fetchBatch],
  )

  const alertColumns: ColumnsType<QualityAlert> = [
    {
      title: '类型',
      dataIndex: 'alert_type',
      key: 'alert_type',
      render: (v: AlertType) => <Tag color="orange">{ALERT_TYPE_LABEL[v]}</Tag>,
    },
    {
      title: '严重度',
      dataIndex: 'severity',
      key: 'severity',
      render: (v: Severity) => (
        <Tag color={v === 'SEVERE' ? 'red' : 'default'}>{v === 'SEVERE' ? '严重' : '一般'}</Tag>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '偏差率',
      dataIndex: 'deviation_rate',
      key: 'deviation_rate',
      render: (v: number | null) =>
        v !== null ? (
          <Text style={{ color: Math.abs(v) > 2 ? '#ff4d4f' : '#faad14' }}>
            {v >= 0 ? '+' : ''}{v.toFixed(2)}%
          </Text>
        ) : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: AlertStatus) => {
        const s = ALERT_STATUS_LABEL[v]
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: QualityAlert) => (
        <Space size="small">
          {record.status === 'PENDING' && (
            <Button
              size="small"
              icon={<CheckOutlined />}
              onClick={() => handleAcknowledge(record.id)}
            >
              确认
            </Button>
          )}
          {(record.status === 'PENDING' || record.status === 'ACKNOWLEDGED') && (
            <Button
              size="small"
              type="primary"
              onClick={() => setResolveModal({ open: true, alertId: record.id })}
            >
              处理
            </Button>
          )}
          {record.status === 'PENDING' && (
            <Button
              size="small"
              danger
              icon={<CloseOutlined />}
              onClick={() => handleDismiss(record.id)}
            >
              忽略
            </Button>
          )}
        </Space>
      ),
    },
  ]

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!batch) return null

  const statusInfo = BATCH_STATUS_MAP[batch.status]

  return (
    <div>
      {contextHolder}
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/batches')}>
          返回列表
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          批次详情：{batch.batch_number}
        </Title>
        <Tag color={statusInfo.color}>{statusInfo.label}</Tag>
      </Space>

      {/* 基本信息卡片 */}
      <Card title="批次基本信息" style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
          <Descriptions.Item label="批次号">{batch.batch_number}</Descriptions.Item>
          <Descriptions.Item label="供应商">{batch.supplier_name ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="煤种">{batch.coal_type ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="发港">{batch.departure_port ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="到厂">{batch.arrival_plant ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="到货日期">{batch.arrival_date ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="合同数量">
            {batch.contract_quantity !== null ? `${batch.contract_quantity} 吨` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="实际数量">
            {batch.actual_quantity !== null ? `${batch.actual_quantity} 吨` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="风险评分">
            <Text
              strong
              style={{
                color:
                  batch.risk_score <= 1 ? '#52c41a' : batch.risk_score <= 3 ? '#faad14' : '#ff4d4f',
              }}
            >
              {batch.risk_score.toFixed(1)} / 5.0
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="合同热值">
            {batch.contract_calorific_value !== null ? `≥${batch.contract_calorific_value} kcal/kg` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="合同灰分">
            {batch.contract_ash_max !== null ? `≤${batch.contract_ash_max}%` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="合同硫分">
            {batch.contract_sulfur_max !== null ? `≤${batch.contract_sulfur_max}%` : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 化验对比 */}
      <Card title="化验对比分析" style={{ marginBottom: 16 }}>
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={10}>
            <div style={{ textAlign: 'center', marginBottom: 8 }}>
              <Text type="secondary">六维质量雷达图（港口 vs 入厂）</Text>
            </div>
            <ReactECharts option={radarOption} style={{ height: 340 }} notMerge />
          </Col>
          <Col xs={24} lg={14}>
            <Table
              dataSource={compareRows}
              columns={compareColumns}
              rowKey="key"
              pagination={false}
              size="small"
              bordered
            />
          </Col>
        </Row>

        <Divider style={{ margin: '16px 0' }} />

        <Row gutter={[24, 0]}>
          <Col xs={24} md={12}>
            <Card size="small" title="港口化验信息" type="inner">
              {portTest ? (
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="报告编号">{portTest.report_number ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="化验机构">{portTest.test_org ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="化验时间">{portTest.test_time ?? '-'}</Descriptions.Item>
                </Descriptions>
              ) : (
                <Text type="secondary">暂无港口化验数据</Text>
              )}
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card size="small" title="入厂化验信息" type="inner">
              {factoryTest ? (
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="报告编号">{factoryTest.report_number ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="化验机构">{factoryTest.test_org ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="化验时间">{factoryTest.test_time ?? '-'}</Descriptions.Item>
                </Descriptions>
              ) : (
                <Text type="secondary">暂无入厂化验数据</Text>
              )}
            </Card>
          </Col>
        </Row>
      </Card>

      {/* 预警列表 */}
      <Card
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: '#faad14' }} />
            <span>预警记录（{batch.alerts?.length ?? 0}条）</span>
          </Space>
        }
      >
        <Table
          dataSource={batch.alerts ?? []}
          columns={alertColumns}
          rowKey="id"
          pagination={false}
          size="small"
          locale={{ emptyText: '该批次暂无预警记录' }}
        />
      </Card>

      {/* 处理弹窗 */}
      <Modal
        title="处理预警"
        open={resolveModal.open}
        onOk={handleResolve}
        onCancel={() => { setResolveModal({ open: false, alertId: 0 }); setResolveNotes('') }}
        okText="确认处理"
        cancelText="取消"
      >
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary">请填写处理说明（可选）：</Text>
        </div>
        <Input.TextArea
          rows={4}
          placeholder="请描述处理措施或结果..."
          value={resolveNotes}
          onChange={(e) => setResolveNotes(e.target.value)}
        />
      </Modal>
    </div>
  )
}
