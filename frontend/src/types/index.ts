export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// 供应商
export type SupplierStatus = 'ACTIVE' | 'SUSPENDED' | 'BLACKLISTED'

export interface Supplier {
  id: number
  name: string
  contact_person: string | null
  contact_phone: string | null
  coal_types: string | null
  credit_score: number
  status: SupplierStatus
  notes: string | null
  created_at: string
  updated_at: string
  // 附加统计
  batch_count?: number
  alert_count?: number
  anomaly_rate?: number
}

// 批次
export type BatchStatus = 'PENDING' | 'PARTIAL' | 'COMPLETED' | 'ALERT' | 'SEVERE'

export interface CoalBatch {
  id: number
  batch_number: string
  supplier_id: number
  supplier_name?: string
  coal_type: string | null
  departure_port: string | null
  arrival_plant: string | null
  contract_quantity: number | null
  actual_quantity: number | null
  contract_calorific_value: number | null
  contract_ash_max: number | null
  contract_sulfur_max: number | null
  contract_moisture_max: number | null
  status: BatchStatus
  alert_count: number
  risk_score: number
  notes: string | null
  arrival_date: string | null
  created_at: string
  updated_at: string
  tests?: QualityTest[]
  alerts?: QualityAlert[]
}

// 化验记录
export type TestType = 'PORT' | 'FACTORY'

export interface QualityTest {
  id: number
  batch_id: number
  test_type: TestType
  test_org: string | null
  test_time: string | null
  report_number: string | null
  calorific_value_net: number | null
  calorific_value_gross: number | null
  ash_content: number | null
  sulfur_content: number | null
  moisture_total: number | null
  moisture_inherent: number | null
  volatile_matter: number | null
  fixed_carbon: number | null
  notes: string | null
  created_at: string
}

// 预警
export type AlertType =
  | 'CALORIFIC_SHORTAGE'
  | 'ASH_EXCESS'
  | 'SULFUR_EXCESS'
  | 'MOISTURE_EXCESS'
  | 'CONTRACT_CAL_BREACH'
  | 'CONTRACT_ASH_BREACH'
  | 'CONTRACT_SULFUR_BREACH'
  | 'COMPREHENSIVE'

export type Severity = 'GENERAL' | 'SEVERE'
export type AlertStatus = 'PENDING' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED'

export interface QualityAlert {
  id: number
  batch_id: number
  alert_type: AlertType
  severity: Severity
  description: string
  port_value: number | null
  factory_value: number | null
  deviation: number | null
  deviation_rate: number | null
  threshold_value: number | null
  status: AlertStatus
  resolved_by: string | null
  resolved_at: string | null
  resolution_notes: string | null
  created_at: string
  supplier_name?: string
  batch_number?: string
}

// 仪表盘
export interface OverviewData {
  total_batches: number
  today_batches: number
  pending_alerts: number
  severe_alerts: number
  anomaly_rate: number
  avg_calorific_deviation: number
  total_suppliers: number
  active_suppliers: number
}

export interface QualityTrendItem {
  date: string
  avg_calorific_deviation: number
  avg_ash_deviation: number
  avg_sulfur_deviation: number
  alert_count: number
}

export interface SupplierRankItem {
  id: number
  name: string
  credit_score: number
  batch_count: number
  anomaly_rate: number
  severe_count: number
}

export interface AlertDistItem {
  alert_type: AlertType
  count: number
}

export interface CalorificScatterItem {
  batch_number: string
  supplier_name: string
  port_value: number
  factory_value: number
  deviation_rate: number
  severity: string
}

export interface AlertStats {
  total: number
  days: number
  by_type: Partial<Record<AlertType, number>>
  by_severity: Partial<Record<Severity, number>>
  by_status: Partial<Record<AlertStatus, number>>
}

// WebSocket
export interface WsNewAlert {
  type: 'new_alert'
  data: {
    id: number
    batch_id: number
    alert_type: AlertType
    severity: Severity
    description: string
    created_at: string
  }
}

export type WsMessage = WsNewAlert | { type: 'ping' | 'pong' }
