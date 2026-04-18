import { api } from './index'

export function normalizeDeliveryStatus(data = {}) {
  const reviewedCount = Number(data.reports_reviewed_count ?? 0)
  const publishedCount = Number(data.reports_published_count ?? 0)
  const legacyReadyCount = Number(data.reports_published ?? reviewedCount + publishedCount)

  return {
    ...data,
    reports_reviewed_count: reviewedCount,
    reports_published_count: publishedCount,
    reports_published: legacyReadyCount,
    reports_published_deprecated: Boolean(data.reports_published_deprecated)
  }
}

export async function fetchFactoryDashboard(params = {}) {
  const { data } = await api.get('/dashboard/factory-director', { params })
  return data
}

export async function fetchWorkshopDashboard(params = {}) {
  const { data } = await api.get('/dashboard/workshop-director', { params })
  return data
}

export async function fetchStatisticsDashboard(params = {}) {
  const { data } = await api.get('/dashboard/statistics', { params })
  return data
}

export async function fetchDeliveryStatus(params = {}) {
  const { data } = await api.get('/dashboard/delivery-status', { params })
  return normalizeDeliveryStatus(data)
}

export async function fetchFactoryDirectorSummary(params = {}) {
  return fetchFactoryDashboard(params)
}

export async function fetchStatisticsReviewSummary(params = {}) {
  return fetchStatisticsDashboard(params)
}

export const dashboardApi = {
  getFactoryData: fetchFactoryDashboard,
  getWorkshopData: fetchWorkshopDashboard,
  getStatisticsData: fetchStatisticsDashboard,
  getDeliveryStatus: fetchDeliveryStatus,
  getFactoryDirectorSummary: fetchFactoryDirectorSummary,
  getStatisticsReviewSummary: fetchStatisticsReviewSummary
}
