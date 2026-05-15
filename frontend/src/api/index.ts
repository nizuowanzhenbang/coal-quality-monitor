import axios from 'axios'
import type {
  ApiResponse,
  PaginatedResponse,
  CoalBatch,
  QualityTest,
  QualityAlert,
  Supplier,
  OverviewData,
  QualityTrendItem,
  SupplierRankItem,
  AlertDistItem,
  CalorificScatterItem,
  AlertStats,
} from '../types'
import { useAuthStore } from '../stores/auth'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

// ── 认证 ────────────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    http.post<ApiResponse<{ access_token: string; token_type: string; username: string; role: string }>>(
      '/auth/login',
      { username, password },
    ),
}

// ── 批次 ────────────────────────────────────────────────
export interface BatchListParams {
  page?: number
  page_size?: number
  batch_number?: string
  supplier_id?: number
  status?: string
  start_date?: string
  end_date?: string
}

export const batchApi = {
  list: (params?: BatchListParams) =>
    http.get<ApiResponse<PaginatedResponse<CoalBatch>>>('/batches', { params }),

  create: (data: Partial<CoalBatch>) =>
    http.post<ApiResponse<CoalBatch>>('/batches', data),

  get: (id: number) =>
    http.get<ApiResponse<CoalBatch>>(`/batches/${id}`),

  update: (id: number, data: Partial<CoalBatch>) =>
    http.put<ApiResponse<CoalBatch>>(`/batches/${id}`, data),

  evaluate: (id: number) =>
    http.post<ApiResponse<CoalBatch>>(`/batches/${id}/evaluate`),
}

// ── 化验 ────────────────────────────────────────────────
export interface TestListParams {
  page?: number
  page_size?: number
  batch_id?: number
  test_type?: string
}

export const testApi = {
  list: (params?: TestListParams) =>
    http.get<ApiResponse<PaginatedResponse<QualityTest>>>('/tests', { params }),

  create: (data: Partial<QualityTest>) =>
    http.post<ApiResponse<QualityTest>>('/tests', data),

  get: (id: number) =>
    http.get<ApiResponse<QualityTest>>(`/tests/${id}`),

  update: (id: number, data: Partial<QualityTest>) =>
    http.put<ApiResponse<QualityTest>>(`/tests/${id}`, data),
}

// ── 预警 ────────────────────────────────────────────────
export interface AlertListParams {
  page?: number
  page_size?: number
  alert_type?: string
  severity?: string
  status?: string
  supplier_id?: number
  batch_id?: number
}

export const alertApi = {
  list: (params?: AlertListParams) =>
    http.get<ApiResponse<PaginatedResponse<QualityAlert>>>('/alerts', { params }),

  acknowledge: (id: number) =>
    http.post<ApiResponse<QualityAlert>>(`/alerts/${id}/acknowledge`),

  resolve: (id: number, notes: string) =>
    http.post<ApiResponse<QualityAlert>>(`/alerts/${id}/resolve`, { resolution_notes: notes }),

  dismiss: (id: number) =>
    http.post<ApiResponse<QualityAlert>>(`/alerts/${id}/dismiss`),

  stats: (days?: number) =>
    http.get<ApiResponse<AlertStats>>('/alerts/stats', { params: { days } }),
}

// ── 供应商 ────────────────────────────────────────────────
export interface SupplierListParams {
  page?: number
  page_size?: number
  name?: string
  status?: string
}

export const supplierApi = {
  list: (params?: SupplierListParams) =>
    http.get<ApiResponse<PaginatedResponse<Supplier>>>('/suppliers', { params }),

  create: (data: Partial<Supplier>) =>
    http.post<ApiResponse<Supplier>>('/suppliers', data),

  get: (id: number) =>
    http.get<ApiResponse<Supplier>>(`/suppliers/${id}`),

  update: (id: number, data: Partial<Supplier>) =>
    http.put<ApiResponse<Supplier>>(`/suppliers/${id}`, data),

  recalculateScore: (id: number) =>
    http.post<ApiResponse<Supplier>>(`/suppliers/${id}/recalculate-score`),
}

// ── 仪表盘 ────────────────────────────────────────────────
export const dashboardApi = {
  overview: () =>
    http.get<ApiResponse<OverviewData>>('/dashboard/overview'),

  qualityTrend: (days?: number) =>
    http.get<ApiResponse<QualityTrendItem[]>>('/dashboard/quality-trend', { params: { days } }),

  supplierRanking: (limit?: number) =>
    http.get<ApiResponse<SupplierRankItem[]>>('/dashboard/supplier-ranking', { params: { limit } }),

  alertDistribution: () =>
    http.get<ApiResponse<AlertDistItem[]>>('/dashboard/alert-distribution'),

  calorificScatter: () =>
    http.get<ApiResponse<CalorificScatterItem[]>>('/dashboard/calorific-scatter'),
}

// ── 导出 ────────────────────────────────────────────────
function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export const exportApi = {
  batches: async (params?: BatchListParams) => {
    const res = await http.get('/export/batches', {
      params,
      responseType: 'blob',
    })
    triggerDownload(res.data as Blob, `批次数据_${Date.now()}.csv`)
  },

  alerts: async (params?: AlertListParams) => {
    const res = await http.get('/export/alerts', {
      params,
      responseType: 'blob',
    })
    triggerDownload(res.data as Blob, `预警数据_${Date.now()}.csv`)
  },
}
