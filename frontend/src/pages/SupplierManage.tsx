import { useState, useEffect, useCallback } from 'react'
import {
  Table,
  Card,
  Button,
  Space,
  Tag,
  Typography,
  Row,
  Col,
  Progress,
  Modal,
  Form,
  Input,
  Select,
  Drawer,
  Descriptions,
  message,
  Divider,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  ReloadOutlined,
  UserOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { supplierApi } from '../api'
import type { Supplier, SupplierStatus } from '../types'

const { Text } = Typography

const SUPPLIER_STATUS_MAP: Record<SupplierStatus, { label: string; color: string }> = {
  ACTIVE: { label: '活跃', color: 'success' },
  SUSPENDED: { label: '暂停', color: 'warning' },
  BLACKLISTED: { label: '黑名单', color: 'error' },
}

function creditColor(score: number): string {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#faad14'
  return '#ff4d4f'
}

// 模拟近20批次信用评分历史（基于当前评分生成历史趋势）
function mockCreditHistory(currentScore: number, count = 20): number[] {
  const result: number[] = []
  let score = Math.max(40, currentScore - 15)
  for (let i = 0; i < count; i++) {
    score = Math.min(100, Math.max(0, score + (Math.random() - 0.4) * 4))
    result.push(Math.round(score * 10) / 10)
  }
  return result
}

interface SupplierFormValues {
  name: string
  contact_person?: string
  contact_phone?: string
  coal_types?: string
  notes?: string
  status?: SupplierStatus
}

export default function SupplierManage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [messageApi, contextHolder] = message.useMessage()

  // 弹窗
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null)
  const [form] = Form.useForm<SupplierFormValues>()
  const [saving, setSaving] = useState(false)

  // 抽屉
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerSupplier, setDrawerSupplier] = useState<Supplier | null>(null)
  const [recalcLoading, setRecalcLoading] = useState(false)

  const fetchSuppliers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await supplierApi.list({ page, page_size: pageSize })
      setSuppliers(res.data.data.items)
      setTotal(res.data.data.total)
    } catch {
      messageApi.error('加载供应商数据失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, messageApi])

  useEffect(() => {
    fetchSuppliers()
  }, [fetchSuppliers])

  const openCreate = useCallback(() => {
    setEditingSupplier(null)
    form.resetFields()
    setModalOpen(true)
  }, [form])

  const openEdit = useCallback(
    (supplier: Supplier) => {
      setEditingSupplier(supplier)
      form.setFieldsValue({
        name: supplier.name,
        contact_person: supplier.contact_person ?? undefined,
        contact_phone: supplier.contact_phone ?? undefined,
        coal_types: supplier.coal_types ?? undefined,
        notes: supplier.notes ?? undefined,
        status: supplier.status,
      })
      setModalOpen(true)
    },
    [form],
  )

  const openDrawer = useCallback((supplier: Supplier) => {
    setDrawerSupplier(supplier)
    setDrawerOpen(true)
  }, [])

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      if (editingSupplier) {
        await supplierApi.update(editingSupplier.id, values)
        messageApi.success('供应商信息已更新')
      } else {
        await supplierApi.create(values)
        messageApi.success('供应商已创建')
      }
      setModalOpen(false)
      fetchSuppliers()
    } catch (err: unknown) {
      if (err !== null && typeof err === 'object' && 'errorFields' in err) return // form validation
      messageApi.error('保存失败')
    } finally {
      setSaving(false)
    }
  }, [form, editingSupplier, messageApi, fetchSuppliers])

  const handleRecalcScore = useCallback(async () => {
    if (!drawerSupplier) return
    setRecalcLoading(true)
    try {
      const res = await supplierApi.recalculateScore(drawerSupplier.id)
      setDrawerSupplier(res.data.data)
      messageApi.success('信用评分已重新计算')
      fetchSuppliers()
    } catch {
      messageApi.error('重算失败')
    } finally {
      setRecalcLoading(false)
    }
  }, [drawerSupplier, messageApi, fetchSuppliers])

  const creditHistoryOption: EChartsOption = (() => {
    const history = drawerSupplier ? mockCreditHistory(drawerSupplier.credit_score) : []
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const p = params as Array<{ dataIndex: number; value: number }>
          return `批次 ${p[0]?.dataIndex + 1}：${p[0]?.value} 分`
        },
      },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: history.map((_, i) => `#${i + 1}`),
        axisLabel: { fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        name: '信用分',
        nameTextStyle: { fontSize: 10 },
      },
      series: [
        {
          name: '信用分',
          type: 'line',
          smooth: true,
          data: history,
          lineStyle: { color: '#1677ff' },
          itemStyle: { color: '#1677ff' },
          areaStyle: { color: 'rgba(22,119,255,0.1)' },
          markLine: {
            silent: true,
            lineStyle: { color: '#ff4d4f', type: 'dashed' },
            data: [{ yAxis: 60, name: '合格线' }],
            label: { formatter: '合格线: 60' },
          },
        },
      ],
    }
  })()

  const columns: ColumnsType<Supplier> = [
    {
      title: '供应商名称',
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '联系人',
      dataIndex: 'contact_person',
      key: 'contact_person',
      render: (v: string | null) => v ?? '-',
    },
    {
      title: '信用分',
      dataIndex: 'credit_score',
      key: 'credit_score',
      width: 180,
      render: (v: number) => (
        <Progress
          percent={v}
          size="small"
          strokeColor={creditColor(v)}
          format={(p) => `${p}分`}
        />
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: SupplierStatus) => {
        const s = SUPPLIER_STATUS_MAP[v]
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '批次数',
      dataIndex: 'batch_count',
      key: 'batch_count',
      align: 'center',
      render: (v: number | undefined) => v ?? 0,
    },
    {
      title: '异常率',
      dataIndex: 'anomaly_rate',
      key: 'anomaly_rate',
      align: 'center',
      render: (v: number | undefined) => {
        if (v === undefined) return '-'
        return (
          <Tag color={v <= 10 ? 'green' : v <= 20 ? 'orange' : 'red'}>
            {v.toFixed(1)}%
          </Tag>
        )
      },
    },
    {
      title: '供应煤种',
      dataIndex: 'coal_types',
      key: 'coal_types',
      render: (v: string | null) => v ?? '-',
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 140,
      render: (_: unknown, record: Supplier) => (
        <Space size="small">
          <Button
            size="small"
            icon={<UserOutlined />}
            onClick={() => openDrawer(record)}
          >
            详情
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      {contextHolder}

      <Card
        title="供应商管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增供应商
          </Button>
        }
      >
        <Table
          dataSource={suppliers}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1000 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => setPage(p),
          }}
          size="small"
        />
      </Card>

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editingSupplier ? '编辑供应商' : '新增供应商'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        width={520}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="供应商名称"
            rules={[{ required: true, message: '请输入供应商名称' }]}
          >
            <Input placeholder="请输入供应商名称" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="contact_person" label="联系人">
                <Input placeholder="联系人姓名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="contact_phone" label="联系电话">
                <Input placeholder="联系电话" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="coal_types" label="供应煤种">
            <Input placeholder="如：动力煤、焦煤" />
          </Form.Item>
          {editingSupplier && (
            <Form.Item name="status" label="状态">
              <Select
                options={Object.entries(SUPPLIER_STATUS_MAP).map(([k, v]) => ({
                  value: k,
                  label: v.label,
                }))}
              />
            </Form.Item>
          )}
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={3} placeholder="备注信息" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 供应商详情抽屉 */}
      <Drawer
        title={drawerSupplier?.name ?? '供应商详情'}
        placement="right"
        width={560}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Button
            icon={<ReloadOutlined />}
            loading={recalcLoading}
            onClick={handleRecalcScore}
          >
            重算信用分
          </Button>
        }
      >
        {drawerSupplier && (
          <>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="状态">
                <Tag color={SUPPLIER_STATUS_MAP[drawerSupplier.status].color}>
                  {SUPPLIER_STATUS_MAP[drawerSupplier.status].label}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="联系人">{drawerSupplier.contact_person ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="联系电话">{drawerSupplier.contact_phone ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="供应煤种">{drawerSupplier.coal_types ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="信用评分">
                <Text strong style={{ color: creditColor(drawerSupplier.credit_score) }}>
                  {drawerSupplier.credit_score} 分
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="异常率">
                {drawerSupplier.anomaly_rate !== undefined
                  ? `${drawerSupplier.anomaly_rate.toFixed(1)}%`
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="总批次数">{drawerSupplier.batch_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="备注">{drawerSupplier.notes ?? '-'}</Descriptions.Item>
            </Descriptions>

            <Divider orientation="left" style={{ marginTop: 24 }}>信用评分趋势（近20批次）</Divider>
            <ReactECharts option={creditHistoryOption} style={{ height: 200 }} notMerge />

            <Divider orientation="left" style={{ marginTop: 16 }}>最近质量摘要</Divider>
            <div style={{ fontSize: 13, color: '#888' }}>
              （此处展示最近5批次质量概览，实际数据由批次接口提供）
            </div>
            <Table
              size="small"
              pagination={false}
              style={{ marginTop: 8 }}
              dataSource={[]}
              locale={{ emptyText: '暂无批次数据' }}
              columns={[
                { title: '批次号', dataIndex: 'batch_number', key: 'batch_number' },
                { title: '热值偏差', dataIndex: 'cal_dev', key: 'cal_dev' },
                { title: '灰分偏差', dataIndex: 'ash_dev', key: 'ash_dev' },
                { title: '状态', dataIndex: 'status', key: 'status' },
              ]}
            />
          </>
        )}
      </Drawer>
    </div>
  )
}
