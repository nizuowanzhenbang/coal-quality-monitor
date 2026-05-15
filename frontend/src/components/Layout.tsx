import { useState, useCallback } from 'react'
import { Layout, Menu, Badge, Avatar, Dropdown, Typography, theme, notification } from 'antd'
import {
  DashboardOutlined,
  ExperimentOutlined,
  AlertOutlined,
  TeamOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  FireOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { useAlertWebSocket } from '../hooks/useAlertWebSocket'

const { Sider, Header, Content } = Layout
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
}

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { username, role, logout } = useAuthStore()
  const { token: colorToken } = theme.useToken()
  const [pendingCount, setPendingCount] = useState(0)
  const [notifApi, contextHolder] = notification.useNotification()

  const handleNewAlert = useCallback(
    (data: { id: number; batch_id: number; alert_type: string; severity: string; description: string; created_at: string }) => {
      setPendingCount((n) => n + 1)
      notifApi.warning({
        message: `${data.severity === 'SEVERE' ? '[严重] ' : ''}新预警：${ALERT_TYPE_LABEL[data.alert_type] ?? data.alert_type}`,
        description: data.description,
        placement: 'topRight',
        duration: 6,
        onClick: () => navigate('/alerts'),
      })
    },
    [notifApi, navigate],
  )

  useAlertWebSocket({ onNewAlert: handleNewAlert })

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/batches',
      icon: <ExperimentOutlined />,
      label: '批次管理',
    },
    {
      key: '/alerts',
      icon: (
        <Badge count={pendingCount} size="small" offset={[6, 0]}>
          <AlertOutlined />
        </Badge>
      ),
      label: (
        <span>
          预警中心
          {pendingCount > 0 && (
            <Badge count={pendingCount} size="small" style={{ marginLeft: 8 }} />
          )}
        </span>
      ),
    },
    {
      key: '/suppliers',
      icon: <TeamOutlined />,
      label: '供应商管理',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
  ]

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => {
        logout()
        navigate('/login')
      },
    },
  ]

  const selectedKey = '/' + location.pathname.split('/')[1]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {contextHolder}
      <Sider
        width={220}
        style={{
          background: colorToken.colorBgContainer,
          borderRight: `1px solid ${colorToken.colorBorderSecondary}`,
        }}
      >
        <div
          style={{
            padding: '16px 20px',
            borderBottom: `1px solid ${colorToken.colorBorderSecondary}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FireOutlined style={{ fontSize: 22, color: colorToken.colorPrimary }} />
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, lineHeight: 1.3, color: colorToken.colorText }}>
                煤质化验比对系统
              </div>
              <div style={{ fontSize: 11, color: colorToken.colorTextSecondary, lineHeight: 1.3 }}>
                数据质量守护平台 v1.0
              </div>
            </div>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          style={{ border: 'none', marginTop: 8 }}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: colorToken.colorBgContainer,
            borderBottom: `1px solid ${colorToken.colorBorderSecondary}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            padding: '0 24px',
            height: 56,
          }}
        >
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <Avatar size={32} icon={<UserOutlined />} style={{ background: colorToken.colorPrimary }} />
              <div>
                <Text strong style={{ fontSize: 14 }}>
                  {username ?? '用户'}
                </Text>
                <Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
                  {role === 'admin' ? '管理员' : role === 'operator' ? '操作员' : '查看者'}
                </Text>
              </div>
            </div>
          </Dropdown>
        </Header>

        <Content
          style={{
            padding: 24,
            background: colorToken.colorBgLayout,
            overflowY: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
