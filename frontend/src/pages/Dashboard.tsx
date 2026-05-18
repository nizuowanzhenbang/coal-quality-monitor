import { useState, useEffect, useCallback } from 'react'
import { Row, Col, Card, Statistic, Table, Progress, Typography, notification, Tag } from 'antd'
import {
  ExperimentOutlined,
  AlertOutlined,
  RiseOutlined,
  ThunderboltOutlined,
  CarOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { dashboardApi } from '../api'
import { useAlertWebSocket } from '../hooks/useAlertWebSocket'
import type {
  OverviewData,
  QualityTrendItem,
  SupplierRankItem,
  AlertDistItem,
  CalorificScatterItem,
} from '../types'

const { Text } = Typography

const ALERT_TYPE_LABEL: Record<string, string> = {
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

export default function Dashboard() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [trend, setTrend] = useState<QualityTrendItem[]>([])
  const [supplierRank, setSupplierRank] = useState<SupplierRankItem[]>([])
  const [alertDist, setAlertDist] = useState<AlertDistItem[]>([])
  const [scatter, setScatter] = useState<CalorificScatterItem[]>([])
  const [loading, setLoading] = useState(true)
  const [notifApi, contextHolder] = notification.useNotification()

  const fetchAll = useCallback(async () => {
    try {
      const [ovRes, trendRes, rankRes, distRes, scatterRes] = await Promise.all([
        dashboardApi.overview(),
        dashboardApi.qualityTrend(30),
        dashboardApi.supplierRanking(10),
        dashboardApi.alertDistribution(),
        dashboardApi.calorificScatter(),
      ])
      setOverview(ovRes.data.data)
      setTrend(trendRes.data.data)
      setSupplierRank(rankRes.data.data)
      setAlertDist(distRes.data.data)
      setScatter(scatterRes.data.data)
    } catch {
      // keep stale data
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const timer = setInterval(fetchAll, 60000)
    return () => clearInterval(timer)
  }, [fetchAll])

  useAlertWebSocket({
    onNewAlert: useCallback(
      (data) => {
        notifApi.warning({
          message: `新预警：${ALERT_TYPE_LABEL[data.alert_type] ?? data.alert_type}`,
          description: data.description,
          placement: 'topRight',
          duration: 6,
        })
        fetchAll()
      },
      [notifApi, fetchAll],
    ),
  })

  // 质量趋势折线图
  const trendOption: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as Array<{ axisValue: string; seriesName: string; value: number; color: string }>
        let html = `<b>${p[0]?.axisValue}</b><br/>`
        p.forEach((item) => {
          html += `<span style="color:${item.color}">●</span> ${item.seriesName}: ${item.value?.toFixed(2)}%<br/>`
        })
        return html
      },
    },
    legend: {
      data: ['热值偏差', '灰分偏差', '硫分偏差'],
      bottom: 0,
    },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: trend.map((t) => t.date.slice(5)),
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '偏差(%)',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { formatter: '{value}%' },
    },
    series: [
      {
        name: '热值偏差',
        type: 'line',
        smooth: true,
        data: trend.map((t) => Number(t.avg_calorific_deviation.toFixed(2))),
        lineStyle: { color: '#1677ff' },
        itemStyle: { color: '#1677ff' },
      },
      {
        name: '灰分偏差',
        type: 'line',
        smooth: true,
        data: trend.map((t) => Number(t.avg_ash_deviation.toFixed(2))),
        lineStyle: { color: '#faad14' },
        itemStyle: { color: '#faad14' },
      },
      {
        name: '硫分偏差',
        type: 'line',
        smooth: true,
        data: trend.map((t) => Number(t.avg_sulfur_deviation.toFixed(2))),
        lineStyle: { color: '#ff4d4f' },
        itemStyle: { color: '#ff4d4f' },
      },
    ],
  }

  // 预警分布饼图
  const pieOption: EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}次 ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { fontSize: 11 },
    },
    series: [
      {
        name: '预警类型',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['40%', '50%'],
        data: alertDist.map((item) => ({
          name: ALERT_TYPE_LABEL[item.alert_type] ?? item.alert_type,
          value: item.count,
        })),
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 13, fontWeight: 'bold' },
        },
      },
    ],
  }

  // 热值散点图
  const scatterOption: EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { data: [number, number, number, string, string] }
        const [portV, factV, devRate, batchNo, supplierName] = p.data
        return `批次：${batchNo}<br/>供应商：${supplierName}<br/>港口热值：${portV} kcal/kg<br/>入厂热值：${factV} kcal/kg<br/>偏差率：${devRate?.toFixed(2)}%`
      },
    },
    legend: {
      data: ['正常（≤1%）', '警告（1-2%）', '严重（>2%）'],
      bottom: 0,
    },
    grid: { left: 60, right: 20, top: 20, bottom: 50 },
    xAxis: {
      type: 'value',
      name: '港口热值(kcal/kg)',
      nameLocation: 'middle',
      nameGap: 30,
      scale: true,
    },
    yAxis: {
      type: 'value',
      name: '入厂热值(kcal/kg)',
      nameLocation: 'middle',
      nameGap: 45,
      scale: true,
    },
    series: [
      // 理想对角线
      {
        name: '理想值',
        type: 'line',
        showSymbol: false,
        lineStyle: { type: 'dashed', color: '#999', width: 1 },
        data: (() => {
          if (scatter.length === 0) return [[4000, 4000], [7000, 7000]]
          const allV = scatter.flatMap((s) => [s.port_value, s.factory_value])
          const min = Math.min(...allV) - 100
          const max = Math.max(...allV) + 100
          return [[min, min], [max, max]]
        })(),
        tooltip: { show: false },
        legend: { show: false },
      },
      {
        name: '正常（≤1%）',
        type: 'scatter',
        symbolSize: 10,
        itemStyle: { color: '#52c41a' },
        data: scatter
          .filter((s) => Math.abs(s.deviation_rate) <= 1)
          .map((s) => [s.port_value, s.factory_value, s.deviation_rate, s.batch_number, s.supplier_name]),
      },
      {
        name: '警告（1-2%）',
        type: 'scatter',
        symbolSize: 10,
        itemStyle: { color: '#faad14' },
        data: scatter
          .filter((s) => Math.abs(s.deviation_rate) > 1 && Math.abs(s.deviation_rate) <= 2)
          .map((s) => [s.port_value, s.factory_value, s.deviation_rate, s.batch_number, s.supplier_name]),
      },
      {
        name: '严重（>2%）',
        type: 'scatter',
        symbolSize: 12,
        itemStyle: { color: '#ff4d4f' },
        data: scatter
          .filter((s) => Math.abs(s.deviation_rate) > 2)
          .map((s) => [s.port_value, s.factory_value, s.deviation_rate, s.batch_number, s.supplier_name]),
      },
    ],
  }

  const rankColumns = [
    {
      title: '供应商',
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '信用分',
      dataIndex: 'credit_score',
      key: 'credit_score',
      render: (v: number) => (
        <div style={{ minWidth: 120 }}>
          <Progress
            percent={v}
            size="small"
            strokeColor={v >= 80 ? '#52c41a' : v >= 60 ? '#faad14' : '#ff4d4f'}
            format={(p) => `${p}`}
          />
        </div>
      ),
    },
    {
      title: '批次数',
      dataIndex: 'batch_count',
      key: 'batch_count',
      align: 'center' as const,
    },
    {
      title: '异常率',
      dataIndex: 'anomaly_rate',
      key: 'anomaly_rate',
      align: 'center' as const,
      render: (v: number) => (
        <Tag color={v <= 10 ? 'green' : v <= 20 ? 'orange' : 'red'}>
          {v.toFixed(1)}%
        </Tag>
      ),
    },
    {
      title: '严重预警',
      dataIndex: 'severe_count',
      key: 'severe_count',
      align: 'center' as const,
      render: (v: number) => (
        <span style={{ color: v > 0 ? '#ff4d4f' : 'inherit', fontWeight: v > 0 ? 600 : 400 }}>
          {v}
        </span>
      ),
    },
  ]

  const calorificDeviationColor =
    Math.abs(overview?.avg_calorific_deviation ?? 0) <= 1
      ? '#52c41a'
      : Math.abs(overview?.avg_calorific_deviation ?? 0) <= 2
        ? '#faad14'
        : '#ff4d4f'

  return (
    <div>
      {contextHolder}

      {/* KPI 卡片行 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} lg={5}>
          <Card loading={loading}>
            <Statistic
              title="总批次数"
              value={overview?.total_batches ?? 0}
              prefix={<ExperimentOutlined style={{ color: '#1677ff' }} />}
              suffix={
                overview?.today_batches
                  ? <Text type="secondary" style={{ fontSize: 13 }}>今日+{overview.today_batches}</Text>
                  : null
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Card loading={loading}>
            <Statistic
              title="待处理预警"
              value={overview?.pending_alerts ?? 0}
              valueStyle={{ color: (overview?.pending_alerts ?? 0) > 0 ? '#ff4d4f' : 'inherit' }}
              prefix={<AlertOutlined style={{ color: '#ff4d4f' }} />}
              suffix={
                (overview?.severe_alerts ?? 0) > 0
                  ? <Text type="danger" style={{ fontSize: 13 }}>严重{overview?.severe_alerts}</Text>
                  : null
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Card loading={loading}>
            <Statistic
              title="综合异常率"
              value={overview?.anomaly_rate ?? 0}
              precision={1}
              suffix="%"
              valueStyle={{ color: (overview?.anomaly_rate ?? 0) <= 10 ? '#52c41a' : (overview?.anomaly_rate ?? 0) <= 20 ? '#faad14' : '#ff4d4f' }}
              prefix={<RiseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Card loading={loading}>
            <Statistic
              title="平均热值偏差"
              value={overview?.avg_calorific_deviation ?? 0}
              precision={2}
              suffix="%"
              valueStyle={{ color: calorificDeviationColor }}
              prefix={<ThunderboltOutlined style={{ color: calorificDeviationColor }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <Card loading={loading}>
            <Statistic
              title="运输预警"
              value={overview?.transport_alerts ?? 0}
              valueStyle={{ color: (overview?.transport_alerts ?? 0) > 0 ? '#fa8c16' : '#52c41a' }}
              prefix={<CarOutlined style={{ color: '#fa8c16' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 图表行 1 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={14}>
          <Card title="质量趋势（近30天）" loading={loading} styles={{ body: { padding: 16 } }}>
            <ReactECharts option={trendOption} style={{ height: 300 }} notMerge />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="预警类型分布" loading={loading} styles={{ body: { padding: 16 } }}>
            <ReactECharts option={pieOption} style={{ height: 300 }} notMerge />
          </Card>
        </Col>
      </Row>

      {/* 图表行 2 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24}>
          <Card title="热值散点图（港口 vs 入厂）" loading={loading} styles={{ body: { padding: 16 } }}>
            <ReactECharts option={scatterOption} style={{ height: 340 }} notMerge />
          </Card>
        </Col>
      </Row>

      {/* 供应商信用排名 */}
      <Row>
        <Col xs={24}>
          <Card title="供应商信用排名" loading={loading}>
            <Table
              dataSource={supplierRank}
              columns={rankColumns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
