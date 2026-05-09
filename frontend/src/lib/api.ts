export type DayPlanStop = {
  sequence: number
  customer_id: string
  customer_name: string
  segment: string
  lat: number
  lng: number
  score: number
  expected_return_rm: number
  distance_from_previous_km: number
  eta_minutes: number
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
  priority: number
  avg_order_value_rm: number
  open_pipeline_rm: number
  last_visit_days: number
  reorder_probability: number
  score: number
  expected_return_rm: number
  score_contributions: Record<string, number>
  visits: CustomerVisit[]
  orders: CustomerOrder[]
}

export type VisitOutcome = 'order' | 'follow_up' | 'no_interest' | 'closed'

export type AssistantResponse = {
  answer: string
  intent: string
  related_customer_id: string | null
  suggestions: string[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

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

export function fetchDayPlan(salespersonId: string): Promise<DayPlan> {
  return get<DayPlan>(`/salespeople/${salespersonId}/day-plan`)
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
}): Promise<AssistantResponse> {
  return post<AssistantResponse>('/assistant/ask', {
    current_customer_id: input.currentCustomerId ?? null,
    question: input.question,
    salesperson_id: input.salespersonId,
  })
}

export const DEFAULT_SALESPERSON_ID = 'sp-kl-central'
