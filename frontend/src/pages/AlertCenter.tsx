import { useState, useEffect, useCallback } from 'react'
import {
  Table,
  Card,
  Select,
  Button,
  Space,
  Tag,
  Typography,
  Row,
  Col,
  Statistic,
  Modal,
  Input,
  message,
  Badge,
} from 'antd'
import {
  AlertOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { alertApi, supplierApi, exportApi } from '../api'
import type { QualityAlert, AlertType, Severity, AlertStatus, Supplier, AlertStats } from '../types'

const { Text } = Typography

const ALERT_TYPE_LABEL: Record<AlertType, string> = {
  CALORIFIC_SHORTAGE: '热值亏损',
  ASH_EXCESS: '灰分偏高',
  SULFUR_EXCESS: '硫分偏高',
  MOISTURE_EXCESS: '水分偏高',
  CONTRACT_CAL_BREACH: '热值违约',
  CONTRACT_ASH_BREACH: '灰分违约',
  CONTRACT_SULFUR_BREACH: '硫分违约',
  COMPREHENSIVE: '综合异常',
}

const ALERT_STATUS_LABEL: Record<AlertStatus, { label: string; color: string }> = {
  PENDING: { label: '待处理', color: 'warning' },
  ACKNOWLEDGED: { label: '已确认', color: 'processing' },
  RESOLVED: { label: '已解决', color: 'success' },
  DISMISSED: { label: '已忽略', color: 'default' },
}

const SEVERITY_LABEL: Record<Severity, { label: string; color: string }> = {
  GENERAL: { label: '一般', color: 'default' },
  SEVERE: { label: '严重', color: 'red' },
}

export default function AlertCenter() {
  const [alerts, setAlerts] = useState<QualityAlert[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [stats, setStats] = useState<AlertStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [messageApi, contextHolder] = message.useMessage()

  // 筛选
  const [alertType, setAlertType] = useState<AlertType | undefined>()
  const [severity, setSeverity] = useState<Severity | undefined>()
  const [alertStatus, setAlertStatus] = useState<AlertStatus | undefined>()
  const [supplierId, setSupplierId] = useState<number | undefined>()

  // 处理弹窗
  const [resolveModal, setResolveModal] = useState<{ open: boolean; alertId: number; action: 'resolve' | 'acknowledge' | 'dismiss' }>({
    open: false,
    alertId: 0,
    action: 'resolve',
  })
  const [resolveNotes, setResolveNotes] = useState('')

  const fetchSuppliers = useCallback(async () => {
    try {
      const res = await supplierApi.list({ page_size: 200 })
      setSuppliers(res.data.data.items)
    } catch {
      // ignore
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const res = await alertApi.stats(30)
      setStats(res.data.data)
    } catch {
      // ignore
    }
  }, [])

  const fetchAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const res = await alertApi.list({
        page,
        page_size: pageSize,
        alert_type: alertType,
        severity,
        status: alertStatus,
        supplier_id: supplierId,
      })
      setAlerts(res.data.data.items)
      setTotal(res.data.data.total)
    } catch {
      messageApi.error('加载预警数据失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, alertType, severity, alertStatus, supplierId, messageApi])

  useEffect(() => {
    fetchSuppliers()
    fetchStats()
  }, [fetchSuppliers, fetchStats])

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts])

  const handleReset = useCallback(() => {
    setAlertType(undefined)
    setSeverity(undefined)
    setAlertStatus(undefined)
    setSupplierId(undefined)
    setPage(1)
  }, [])

  const handleExport = useCallback(async () => {
    try {
      await exportApi.alerts({
        alert_type: alertType,
        severity,
        status: alertStatus,
        supplier_id: supplierId,
      })
      messageApi.success('导出成功')
    } catch {
      messageApi.error('导出失败')
    }
  }, [alertType, severity, alertStatus, supplierId, messageApi])

  const handleAction = useCallback(async () => {
    const { alertId, action } = resolveModal
    try {
      if (action === 'acknowledge') {
        await alertApi.acknowledge(alertId)
        messageApi.success('已确认')
      } else if (action === 'resolve') {
        await alertApi.resolve(alertId, resolveNotes)
        messageApi.success('已处理')
      } else {
        await alertApi.dismiss(alertId)
        messageApi.success('已忽略')
      }
      setResolveModal({ open: false, alertId: 0, action: 'resolve' })
      setResolveNotes('')
      fetchAlerts()
      fetchStats()
    } catch {
      messageApi.error('操作失败')
    }
  }, [resolveModal, resolveNotes, messageApi, fetchAlerts, fetchStats])

  const openModal = useCallback(
    (alertId: number, action: 'resolve' | 'acknowledge' | 'dismiss') => {
      setResolveModal({ open: true, alertId, action })
      setResolveNotes('')
    },
    [],
  )

  const columns: ColumnsType<QualityAlert> = [
    {
      title: '类型',
      dataIndex: 'alert_type',
      key: 'alert_type',
      width: 110,
      render: (v: AlertType) => <Tag color="orange">{ALERT_TYPE_LABEL[v]}</Tag>,
    },
    {
      title: '严重度',
      dataIndex: 'severity',
      key: 'severity',
      width: 80,
      render: (v: Severity) => {
        const s = SEVERITY_LABEL[v]
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '批次号',
      dataIndex: 'batch_number',
      key: 'batch_number',
      width: 140,
      render: (v: string | undefined) => <Text style={{ color: '#1677ff' }}>{v ?? '-'}</Text>,
    },
    {
      title: '供应商',
      dataIndex: 'supplier_name',
      key: 'supplier_name',
      width: 130,
      render: (v: string | undefined) => v ?? '-',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '偏差值',
      key: 'deviation',
      width: 140,
      render: (_: unknown, record: QualityAlert) => {
        if (record.port_value === null && record.factory_value === null) return '-'
        return (
          <div style={{ fontSize: 12 }}>
            <div>港口：{record.port_value ?? '-'}</div>
            <div>入厂：{record.factory_value ?? '-'}</div>
            {record.deviation_rate !== null && (
              <Text type="danger">偏差：{record.deviation_rate.toFixed(2)}%</Text>
            )}
          </div>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: AlertStatus) => {
        const s = ALERT_STATUS_LABEL[v]
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 155,
      render: (v: string) => v.slice(0, 16).replace('T', ' '),
    },
    {
      title: '操作',
      key: 'action',
      width: 170,
      fixed: 'right',
      render: (_: unknown, record: QualityAlert) => (
        <Space size="small">
          {record.status === 'PENDING' && (
            <Button size="small" onClick={() => openModal(record.id, 'acknowledge')}>
              确认
            </Button>
          )}
          {(record.status === 'PENDING' || record.status === 'ACKNOWLEDGED') && (
            <Button size="small" type="primary" onClick={() => openModal(record.id, 'resolve')}>
              处理
            </Button>
          )}
          {record.status === 'PENDING' && (
            <Button size="small" danger onClick={() => openModal(record.id, 'dismiss')}>
              忽略
            </Button>
          )}
        </Space>
      ),
    },
  ]

  const pendingCount = stats?.by_status?.['PENDING'] ?? 0
  const resolvedCount = stats?.by_status?.['RESOLVED'] ?? 0
  const severeCount = stats?.by_severity?.['SEVERE'] ?? 0

  return (
    <div>
      {contextHolder}

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总预警数（近30天）"
              value={stats?.total ?? 0}
              prefix={<AlertOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="待处理"
              value={pendingCount}
              valueStyle={{ color: pendingCount > 0 ? '#faad14' : 'inherit' }}
              prefix={<ClockCircleOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="已解决"
              value={resolvedCount}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="严重预警"
              value={severeCount}
              valueStyle={{ color: severeCount > 0 ? '#ff4d4f' : 'inherit' }}
              prefix={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col xs={24} sm={12} md={5}>
            <Select
              placeholder="预警类型"
              style={{ width: '100%' }}
              allowClear
              value={alertType}
              onChange={(v) => setAlertType(v)}
              options={Object.entries(ALERT_TYPE_LABEL).map(([k, v]) => ({ value: k, label: v }))}
            />
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Select
              placeholder="严重度"
              style={{ width: '100%' }}
              allowClear
              value={severity}
              onChange={(v) => setSeverity(v)}
              options={[
                { value: 'GENERAL', label: '一般' },
                { value: 'SEVERE', label: '严重' },
              ]}
            />
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Select
              placeholder="处理状态"
              style={{ width: '100%' }}
              allowClear
              value={alertStatus}
              onChange={(v) => setAlertStatus(v)}
              options={Object.entries(ALERT_STATUS_LABEL).map(([k, v]) => ({ value: k, label: v.label }))}
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
          <Col xs={24} sm={24} md={6}>
            <Space>
              <Button onClick={handleReset}>重置</Button>
              <Button icon={<DownloadOutlined />} onClick={handleExport}>
                导出CSV
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 表格 */}
      <Card
        title={
          <Space>
            <span>预警列表</span>
            <Badge count={pendingCount} style={{ backgroundColor: '#faad14' }} />
          </Space>
        }
      >
        <Table
          dataSource={alerts}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => setPage(p),
          }}
          size="small"
          rowClassName={(record) =>
            record.severity === 'SEVERE' && record.status === 'PENDING'
              ? 'ant-table-row-danger'
              : ''
          }
        />
      </Card>

      {/* 处理弹窗 */}
      <Modal
        title={
          resolveModal.action === 'acknowledge'
            ? '确认预警'
            : resolveModal.action === 'resolve'
              ? '处理预警'
              : '忽略预警'
        }
        open={resolveModal.open}
        onOk={handleAction}
        onCancel={() => { setResolveModal({ open: false, alertId: 0, action: 'resolve' }); setResolveNotes('') }}
        okText={
          resolveModal.action === 'acknowledge' ? '确认' : resolveModal.action === 'resolve' ? '确认处理' : '确认忽略'
        }
        cancelText="取消"
      >
        {resolveModal.action === 'resolve' && (
          <>
            <div style={{ marginBottom: 8 }}>
              <Text type="secondary">请填写处理说明：</Text>
            </div>
            <Input.TextArea
              rows={4}
              placeholder="请描述处理措施或结果..."
              value={resolveNotes}
              onChange={(e) => setResolveNotes(e.target.value)}
            />
          </>
        )}
        {resolveModal.action === 'acknowledge' && (
          <Text>确认已知悉该预警，将标记为"已确认"状态？</Text>
        )}
        {resolveModal.action === 'dismiss' && (
          <Text type="warning">确认忽略该预警？忽略后不会计入处理统计。</Text>
        )}
      </Modal>
    </div>
  )
}
