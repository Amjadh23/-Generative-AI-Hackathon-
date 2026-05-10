export type DayPlanStop = {
  sequence: number
  customer_id: string
  customer_name: string
  segment: string
  lat: number
  lng: number
  score: number
  visit_likelihood_score: number
  priority_class: string
  recommended_action: string
  top_reasons: string[]
  expected_return_rm: number
  distance_from_previous_km: number
  eta_minutes: number
  visit_duration_minutes: number
  reason: string
  focus: string
}

export type OptimizationSummary = {
  routes_evaluated: number
  baseline_expected_return_rm: number
  baseline_distance_km: number
  value_gain_rm: number
  distance_saved_km: number
  value_uplift_pct: number
}

export type DayPlan = {
  salesperson_id: string
  date: string
  total_expected_return_rm: number
  total_distance_km: number
  stops: DayPlanStop[]
  optimization_summary: OptimizationSummary | null
}

export type Salesperson = {
  id: string
  name: string
  home_lat: number
  home_lng: number
  max_daily_stops: number
  territory_id: string
  territory_name: string
}

export type Territory = {
  id: string
  name: string
  salesperson_id: string
  salesperson_name: string
  center_lat: number
  center_lng: number
  radius_km: number
  home_lat: number
  home_lng: number
}

export type CustomerVisit = {
  id: string
  salesperson_id: string
  visited_at: string
  outcome: string
  notes: string | null
}

export type CustomerOrder = {
  id: string
  order_date: string
  amount_rm: number
  product_family: string
}

export type CustomerDetail = {
  id: string
  name: string
  segment: string
  territory_id: string
  assigned_salesperson_id: string
  lat: number
  lng: number
  /** Synthetic CRM field from seed data — not used by the XGBoost model. */
  crm_priority: number
  avg_order_value_rm: number
  open_pipeline_rm: number
  last_visit_days: number
  reorder_probability: number
  score: number
  visit_likelihood_score: number
  priority_class: string
  /** Prefer server value; UI falls back from `priority_class` if missing (stale cache / old API). */
  recommended_action?: string
  expected_return_rm: number
  score_contributions: Record<string, number>
  top_reasons: string[]
  sentiment_initial_confidence_score: number
  sentiment_confidence_score: number
  sentiment_label: string
  sentiment_source: string
  sentiment_updated_at: string | null
  xgboost_explanation: {
    base_value: number
    top_priority_reasons: Array<{
      feature: string
      actual_value: string | number
      shap_value: number
      effect: string
      meaning: string
    }>
  } | null
  visits: CustomerVisit[]
  orders: CustomerOrder[]
}

export type VisitOutcome = 'order' | 'follow_up' | 'no_interest' | 'closed'

export type VisitSentiment =
  | 'very_negative'
  | 'negative'
  | 'neutral'
  | 'positive'
  | 'very_positive'

export type AssistantResponse = {
  answer: string
  intent: string
  related_customer_id: string | null
  suggestions: string[]
}

export type VisitRecap = {
  visit_id: string | null
  persisted: boolean
  summary: string
  outcome: VisitOutcome
  next_action: string
  due_date: string | null
  products_mentioned: string[]
  sentiment: 'positive' | 'neutral' | 'negative'
  confidence: number
  previous_sentiment_confidence_score: number | null
  sentiment_confidence_score: number
  raw_transcript: string
}

/** Trim trailing slash so paths like `/admin/dashboard` never become `//admin/dashboard` (404 on FastAPI). */
const API_BASE_URL = String(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/+$/,
  '',
)

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${path}`)
  }
  return response.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${path}`)
  }
  return response.json() as Promise<T>
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
    method: 'PATCH',
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${path}`)
  }
  return response.json() as Promise<T>
}

export function fetchDayPlan(
  salespersonId: string,
  options: { maxStops?: number } = {},
): Promise<DayPlan> {
  const params = new URLSearchParams()
  if (options.maxStops !== undefined) {
    params.set('max_stops', String(options.maxStops))
  }
  const query = params.toString()
  return get<DayPlan>(`/salespeople/${salespersonId}/day-plan${query ? `?${query}` : ''}`)
}

export function fetchSalespeople(): Promise<Salesperson[]> {
  return get<Salesperson[]>('/salespeople')
}

export function fetchTerritory(salespersonId: string): Promise<Territory> {
  return get<Territory>(`/salespeople/${salespersonId}/territory`)
}

export function fetchCustomer(customerId: string): Promise<CustomerDetail> {
  return get<CustomerDetail>(`/customers/${customerId}`)
}

export function logVisit(input: {
  customerId: string
  salespersonId: string
  outcome: VisitOutcome
  notes?: string
}): Promise<{ id: string; status: string }> {
  return post('/visits', {
    customer_id: input.customerId,
    notes: input.notes ?? null,
    outcome: input.outcome,
    salesperson_id: input.salespersonId,
  })
}

export function askAssistant(input: {
  salespersonId: string
  question: string
  currentCustomerId?: string | null
  maxStops?: number
}): Promise<AssistantResponse> {
  return post<AssistantResponse>('/assistant/ask', {
    current_customer_id: input.currentCustomerId ?? null,
    max_stops: input.maxStops ?? null,
    question: input.question,
    salesperson_id: input.salespersonId,
  })
}

export function recapVisit(input: {
  customerId: string
  salespersonId: string
  transcript: string
  persist?: boolean
}): Promise<VisitRecap> {
  return post<VisitRecap>('/visits/recap', {
    customer_id: input.customerId,
    persist: input.persist ?? true,
    salesperson_id: input.salespersonId,
    transcript: input.transcript,
  })
}

export type VisitSentimentResult = {
  visit_id: string
  status: string
  sentiment: VisitSentiment
  sentiment_label: string
  outcome: VisitOutcome
  previous_sentiment_confidence_score: number
  sentiment_confidence_score: number
}

export function logVisitSentiment(input: {
  customerId: string
  salespersonId: string
  sentiment: VisitSentiment
}): Promise<VisitSentimentResult> {
  return post<VisitSentimentResult>('/visits/sentiment', {
    customer_id: input.customerId,
    salesperson_id: input.salespersonId,
    sentiment: input.sentiment,
  })
}

export type ManagerRepSummary = {
  salesperson_id: string
  name: string
  territory_id: string
  territory_name: string
  customer_count: number
  today_top_expected_return_rm: number
  ai_recap_visit_count: number
  /** AI recaps in last 30d with outcome order / follow_up / closed */
  interested_recaps_30d: number
  active_follow_ups: number
}

export type ManagerRecentAiRecap = {
  visit_id: string
  customer_id: string
  customer_name: string
  segment: string
  salesperson_id: string
  salesperson_name: string
  territory_name: string
  visited_at: string
  outcome: string
  interest_label: string
  is_interested: boolean
  summary: string
  next_action: string
}

export type ManagerCustomerRanking = {
  customer_id: string
  customer_name: string
  segment: string
  territory_id: string
  territory_name: string
  assigned_salesperson_id: string
  assigned_salesperson_name: string
  routeiq_score: number
  expected_return_rm: number
  last_visit_days: number
  visit_signal: number
  last_visit_outcome: string | null
  future_potential_baseline: number
  future_potential_index: number
  sentiment_initial_confidence_score: number
  sentiment_confidence_score: number
  sentiment_label: string
  sentiment_source: string
  sentiment_updated_at: string | null
}

export type ManagerCustomerPick = {
  customer_id: string
  name: string
  segment: string
  territory_name: string
  assigned_salesperson_id: string
  assigned_salesperson_name: string
}

export type RecapImpact = {
  headline: string
  subhead: string
  avg_before: number
  avg_after: number
  spotlight_customer_name: string | null
  spotlight_before: number
  spotlight_after: number
  spotlight_outcome: string | null
  spotlight_confidence_before: number | null
  spotlight_confidence_after: number | null
  spotlight_sentiment: string | null
  spotlight_sentiment_source: string | null
  spotlight_sentiment_updated_at: string | null
}

export type ManagerDashboard = {
  generated_at: string
  date: string
  reps: ManagerRepSummary[]
  rankings: ManagerCustomerRanking[]
  customers_for_assignment: ManagerCustomerPick[]
  recent_ai_recaps: ManagerRecentAiRecap[]
  ranking_note: string
  recap_monitor_note: string
  recap_impact: RecapImpact
}

export function fetchManagerDashboard(): Promise<ManagerDashboard> {
  return get<ManagerDashboard>('/admin/dashboard')
}

export function assignCustomerToRep(input: {
  customerId: string
  salespersonId: string
}): Promise<{ customer_id: string; salesperson_id: string; territory_id: string }> {
  return patch(`/admin/customers/${input.customerId}/assignment`, {
    salesperson_id: input.salespersonId,
  })
}

export const DEFAULT_SALESPERSON_ID = 'sp-kl-central'
