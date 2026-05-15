import { Card, Table, Typography, Tag, Divider, Row, Col, Statistic } from 'antd'
import {
  SettingOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

const { Title, Text, Paragraph } = Typography

interface ThresholdRow {
  key: string
  indicator: string
  parameter: string
  generalThreshold: string
  severeThreshold: string
  unit: string
  description: string
}

const thresholdData: ThresholdRow[] = [
  {
    key: 'calorific_deviation',
    indicator: '热值',
    parameter: '港厂热值偏差率',
    generalThreshold: '1',
    severeThreshold: '2',
    unit: '%',
    description: '港口化验热值与入厂化验热值之差占港口值的百分比',
  },
  {
    key: 'ash_deviation',
    indicator: '灰分',
    parameter: '港厂灰分偏差率',
    generalThreshold: '0.8',
    severeThreshold: '1.5',
    unit: '%',
    description: '港口化验灰分与入厂化验灰分之差的绝对值占港口值的百分比',
  },
  {
    key: 'sulfur_deviation',
    indicator: '硫分',
    parameter: '港厂硫分偏差率',
    generalThreshold: '0.08',
    severeThreshold: '0.15',
    unit: '%',
    description: '港口化验硫分与入厂化验硫分之差的绝对值占港口值的百分比',
  },
  {
    key: 'moisture_deviation',
    indicator: '水分',
    parameter: '港厂水分偏差率',
    generalThreshold: '1.0',
    severeThreshold: '2.0',
    unit: '%',
    description: '港口化验水分与入厂化验水分之差的绝对值占港口值的百分比',
  },
  {
    key: 'contract_calorific',
    indicator: '热值',
    parameter: '合同热值亏损',
    generalThreshold: '200',
    severeThreshold: '400',
    unit: 'kcal/kg',
    description: '入厂化验热值低于合同约定热值的差值',
  },
  {
    key: 'contract_ash',
    indicator: '灰分',
    parameter: '合同灰分超标',
    generalThreshold: '0.5',
    severeThreshold: '1.0',
    unit: '%',
    description: '入厂化验灰分超过合同约定最高灰分的超出量',
  },
  {
    key: 'contract_sulfur',
    indicator: '硫分',
    parameter: '合同硫分超标',
    generalThreshold: '0.05',
    severeThreshold: '0.1',
    unit: '%',
    description: '入厂化验硫分超过合同约定最高硫分的超出量',
  },
]

const columns: ColumnsType<ThresholdRow> = [
  {
    title: '指标',
    dataIndex: 'indicator',
    key: 'indicator',
    width: 70,
    render: (v: string) => <Text strong>{v}</Text>,
  },
  {
    title: '预警参数',
    dataIndex: 'parameter',
    key: 'parameter',
    width: 150,
  },
  {
    title: '一般预警阈值',
    dataIndex: 'generalThreshold',
    key: 'generalThreshold',
    align: 'center',
    width: 130,
    render: (v: string, row: ThresholdRow) => (
      <Tag color="orange">
        {v} {row.unit}
      </Tag>
    ),
  },
  {
    title: '严重预警阈值',
    dataIndex: 'severeThreshold',
    key: 'severeThreshold',
    align: 'center',
    width: 130,
    render: (v: string, row: ThresholdRow) => (
      <Tag color="red">
        {v} {row.unit}
      </Tag>
    ),
  },
  {
    title: '说明',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
    render: (v: string) => <Text type="secondary">{v}</Text>,
  },
]

export default function Settings() {
  return (
    <div>
      <Title level={4} style={{ marginBottom: 20 }}>
        <SettingOutlined style={{ marginRight: 8 }} />
        系统设置
      </Title>

      {/* 预警阈值配置 */}
      <Card
        title="预警阈值配置"
        style={{ marginBottom: 16 }}
        extra={<Tag color="blue">只读配置（需修改请联系管理员）</Tag>}
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          <InfoCircleOutlined style={{ marginRight: 6 }} />
          以下阈值用于自动生成质量预警。当化验偏差超过"一般预警阈值"时生成 GENERAL 级预警，超过"严重预警阈值"时生成 SEVERE 级预警。
        </Paragraph>
        <Table
          dataSource={thresholdData}
          columns={columns}
          rowKey="key"
          pagination={false}
          size="small"
          bordered
        />
      </Card>

      {/* 综合异常规则 */}
      <Card title="综合异常触发规则" style={{ marginBottom: 16 }}>
        <Row gutter={[24, 24]}>
          <Col xs={24} md={8}>
            <Card size="small" type="inner" style={{ textAlign: 'center' }}>
              <Statistic title="触发条件" value={3} suffix="项同时异常" />
              <Text type="secondary" style={{ fontSize: 12 }}>
                当热值、灰分、硫分中同时有 3 项超过一般预警阈值，则触发综合异常（COMPREHENSIVE）预警
              </Text>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card size="small" type="inner" style={{ textAlign: 'center' }}>
              <Statistic title="信用扣分（一般预警）" value={-2} suffix="分/次" valueStyle={{ color: '#faad14' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                每次 GENERAL 级预警触发，供应商信用评分扣除 2 分
              </Text>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card size="small" type="inner" style={{ textAlign: 'center' }}>
              <Statistic title="信用扣分（严重预警）" value={-5} suffix="分/次" valueStyle={{ color: '#ff4d4f' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                每次 SEVERE 级预警触发，供应商信用评分扣除 5 分
              </Text>
            </Card>
          </Col>
        </Row>
      </Card>

      {/* 系统信息 */}
      <Card title="系统信息">
        <Divider orientation="left" plain>版本信息</Divider>
        <Row gutter={[16, 8]}>
          <Col span={12}>
            <Text type="secondary">系统名称：</Text>
            <Text>煤质化验数据比对系统</Text>
          </Col>
          <Col span={12}>
            <Text type="secondary">前端版本：</Text>
            <Text>v1.0.0</Text>
          </Col>
          <Col span={12}>
            <Text type="secondary">技术栈：</Text>
            <Text>React 18 + TypeScript + Ant Design 5 + ECharts</Text>
          </Col>
          <Col span={12}>
            <Text type="secondary">API 地址：</Text>
            <Text>/api（代理至 localhost:8000）</Text>
          </Col>
        </Row>
        <Divider orientation="left" plain style={{ marginTop: 20 }}>功能说明</Divider>
        <Paragraph>
          本系统对煤炭货物在港口化验和入厂化验之间的质量差异进行自动比对，
          通过热值、灰分、硫分、水分等多维度指标分析，实时生成质量预警，
          并对供应商信用评分进行动态管理，为煤炭采购质量管控提供数据支撑。
        </Paragraph>
      </Card>
    </div>
  )
}
