import { useState, useEffect, useCallback } from 'react'
import {
  Table,
  Card,
  Input,
  Select,
  DatePicker,
  Button,
  Space,
  Tag,
  Badge,
  Typography,
  Row,
  Col,
  message,
} from 'antd'
import {
  SearchOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useNavigate } from 'react-router-dom'
import { batchApi, supplierApi, exportApi } from '../api'
import type { CoalBatch, BatchStatus, Supplier } from '../types'

const { RangePicker } = DatePicker
const { Text } = Typography

const BATCH_STATUS_MAP: Record<BatchStatus, { label: string; color: string }> = {
  PENDING: { label: '待化验', color: 'default' },
  PARTIAL: { label: '部分完成', color: 'processing' },
  COMPLETED: { label: '已完成', color: 'success' },
  ALERT: { label: '预警', color: 'warning' },
  SEVERE: { label: '严重', color: 'error' },
}

function deviationColor(rate: number | null): string {
  if (rate === null) return 'inherit'
  const abs = Math.abs(rate)
  if (abs <= 1) return '#52c41a'
  if (abs <= 2) return '#faad14'
  return '#ff4d4f'
}

function deviationTagColor(rate: number | null): string {
  if (rate === null) return 'default'
  const abs = Math.abs(rate)
  if (abs <= 1) return 'green'
  if (abs <= 2) return 'orange'
  return 'red'
}

function riskScoreColor(score: number): string {
  if (score <= 1) return '#52c41a'
  if (score <= 3) return '#faad14'
  return '#ff4d4f'
}

function calcDeviationRate(port: number | null, factory: number | null): number | null {
  if (port === null || factory === null || port === 0) return null
  return ((factory - port) / port) * 100
}

export default function BatchList() {
  const navigate = useNavigate()
  const [batches, setBatches] = useState<CoalBatch[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [messageApi, contextHolder] = message.useMessage()

  // 筛选状态
  const [batchNumber, setBatchNumber] = useState('')
  const [supplierId, setSupplierId] = useState<number | undefined>()
  const [status, setStatus] = useState<string | undefined>()
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)

  const fetchSuppliers = useCallback(async () => {
    try {
      const res = await supplierApi.list({ page_size: 200 })
      setSuppliers(res.data.data.items)
    } catch {
      // ignore
    }
  }, [])

  const fetchBatches = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (batchNumber) params.batch_number = batchNumber
      if (supplierId) params.supplier_id = supplierId
      if (status) params.status = status
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD')
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD')
      const res = await batchApi.list(params)
      setBatches(res.data.data.items)
      setTotal(res.data.data.total)
    } catch {
      messageApi.error('加载批次数据失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, batchNumber, supplierId, status, dateRange, messageApi])

  useEffect(() => {
    fetchSuppliers()
  }, [fetchSuppliers])

  useEffect(() => {
    fetchBatches()
  }, [fetchBatches])

  const handleReset = useCallback(() => {
    setBatchNumber('')
    setSupplierId(undefined)
    setStatus(undefined)
    setDateRange(null)
    setPage(1)
  }, [])

  const handleExport = useCallback(async () => {
    try {
      await exportApi.batches({
        batch_number: batchNumber || undefined,
        supplier_id: supplierId,
        status,
        start_date: dateRange?.[0]?.format('YYYY-MM-DD'),
        end_date: dateRange?.[1]?.format('YYYY-MM-DD'),
      })
      messageApi.success('导出成功')
    } catch {
      messageApi.error('导出失败')
    }
  }, [batchNumber, supplierId, status, dateRange, messageApi])

  const getPortTest = (batch: CoalBatch) =>
    batch.tests?.find((t) => t.test_type === 'PORT')

  const getFactoryTest = (batch: CoalBatch) =>
    batch.tests?.find((t) => t.test_type === 'FACTORY')

  const columns: ColumnsType<CoalBatch> = [
    {
      title: '批次号',
      dataIndex: 'batch_number',
      key: 'batch_number',
      fixed: 'left',
      width: 140,
      render: (v: string) => <Text strong style={{ color: '#1677ff' }}>{v}</Text>,
    },
    {
      title: '供应商',
      dataIndex: 'supplier_name',
      key: 'supplier_name',
      width: 130,
    },
    {
      title: '煤种',
      dataIndex: 'coal_type',
      key: 'coal_type',
      width: 90,
      render: (v: string | null) => v ?? '-',
    },
    {
      title: '合同热值',
      dataIndex: 'contract_calorific_value',
      key: 'contract_calorific_value',
      width: 110,
      render: (v: number | null) => (v !== null ? `${v} kcal/kg` : '-'),
    },
    {
      title: '港口热值 / 入厂热值',
      key: 'calorific_compare',
      width: 180,
      render: (_: unknown, record: CoalBatch) => {
        const port = getPortTest(record)
        const factory = getFactoryTest(record)
        const pv = port?.calorific_value_net ?? null
        const fv = factory?.calorific_value_net ?? null
        const rate = calcDeviationRate(pv, fv)
        return (
          <div>
            <span>{pv !== null ? pv : '-'}</span>
            <Text type="secondary"> / </Text>
            <span style={{ color: rate !== null ? deviationColor(rate) : 'inherit' }}>
              {fv !== null ? fv : '-'}
            </span>
          </div>
        )
      },
    },
    {
      title: '热值偏差率',
      key: 'caloric_deviation',
      width: 110,
      align: 'center',
      render: (_: unknown, record: CoalBatch) => {
        const port = getPortTest(record)
        const factory = getFactoryTest(record)
        const pv = port?.calorific_value_net ?? null
        const fv = factory?.calorific_value_net ?? null
        const rate = calcDeviationRate(pv, fv)
        if (rate === null) return <Tag>-</Tag>
        return (
          <Tag color={deviationTagColor(rate)}>
            {rate >= 0 ? '+' : ''}{rate.toFixed(2)}%
          </Tag>
        )
      },
    },
    {
      title: '灰分比对',
      key: 'ash_compare',
      width: 150,
      render: (_: unknown, record: CoalBatch) => {
        const port = getPortTest(record)
        const factory = getFactoryTest(record)
        const pv = port?.ash_content ?? null
        const fv = factory?.ash_content ?? null
        if (pv === null && fv === null) return '-'
        const rate = calcDeviationRate(pv, fv)
        return (
          <div>
            <span>{pv !== null ? `${pv}%` : '-'}</span>
            <Text type="secondary"> → </Text>
            <span style={{ color: rate !== null ? deviationColor(rate) : 'inherit' }}>
              {fv !== null ? `${fv}%` : '-'}
            </span>
          </div>
        )
      },
    },
    {
      title: '硫分比对',
      key: 'sulfur_compare',
      width: 150,
      render: (_: unknown, record: CoalBatch) => {
        const port = getPortTest(record)
        const factory = getFactoryTest(record)
        const pv = port?.sulfur_content ?? null
        const fv = factory?.sulfur_content ?? null
        if (pv === null && fv === null) return '-'
        const rate = calcDeviationRate(pv, fv)
        return (
          <div>
            <span>{pv !== null ? `${pv}%` : '-'}</span>
            <Text type="secondary"> → </Text>
            <span style={{ color: rate !== null ? deviationColor(rate) : 'inherit' }}>
              {fv !== null ? `${fv}%` : '-'}
            </span>
          </div>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: BatchStatus) => {
        const s = BATCH_STATUS_MAP[v]
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '风险评分',
      dataIndex: 'risk_score',
      key: 'risk_score',
      width: 90,
      align: 'center',
      render: (v: number) => (
        <Text strong style={{ color: riskScoreColor(v) }}>
          {v.toFixed(1)}
        </Text>
      ),
    },
    {
      title: '预警数',
      dataIndex: 'alert_count',
      key: 'alert_count',
      width: 80,
      align: 'center',
      render: (v: number) => <Badge count={v} showZero style={{ backgroundColor: v > 0 ? '#ff4d4f' : '#d9d9d9' }} />,
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 90,
      render: (_: unknown, record: CoalBatch) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          size="small"
          onClick={(e) => {
            e.stopPropagation()
            navigate(`/batches/${record.id}`)
          }}
        >
          详情
        </Button>
      ),
    },
  ]

  return (
    <div>
      {contextHolder}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} sm={12} md={6}>
            <Input
              placeholder="批次号搜索"
              prefix={<SearchOutlined />}
              value={batchNumber}
              onChange={(e) => setBatchNumber(e.target.value)}
              onPressEnter={() => { setPage(1); fetchBatches() }}
              allowClear
            />
          </Col>
          <Col xs={24} sm={12} md={5}>
            <Select
              placeholder="供应商"
              style={{ width: '100%' }}
              allowClear
              value={supplierId}
              onChange={(v) => setSupplierId(v)}
              options={suppliers.map((s) => ({ value: s.id, label: s.name }))}
              showSearch
              filterOption={(input, option) =>
                String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Select
              placeholder="状态"
              style={{ width: '100%' }}
              allowClear
              value={status}
              onChange={(v) => setStatus(v)}
              options={Object.entries(BATCH_STATUS_MAP).map(([k, v]) => ({ value: k, label: v.label }))}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <RangePicker
              style={{ width: '100%' }}
              value={dateRange}
              onChange={(v) => setDateRange(v as [Dayjs | null, Dayjs | null] | null)}
              placeholder={['开始日期', '结束日期']}
              presets={[
                { label: '最近7天', value: [dayjs().subtract(7, 'day'), dayjs()] },
                { label: '最近30天', value: [dayjs().subtract(30, 'day'), dayjs()] },
              ]}
            />
          </Col>
          <Col xs={24} sm={24} md={3}>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={handleReset}>
                重置
              </Button>
              <Button icon={<DownloadOutlined />} onClick={handleExport}>
                导出
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card>
        <Table
          dataSource={batches}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1400 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => setPage(p),
          }}
          onRow={(record) => ({
            onClick: () => navigate(`/batches/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          size="small"
        />
      </Card>
    </div>
  )
}
