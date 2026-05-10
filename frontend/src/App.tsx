import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from 'react'

import { AppHeader } from './components/AppHeader'
import { CustomerIcon, MapIcon, SettingsIcon, TodayIcon } from './components/Icon'
import { Onboarding } from './components/Onboarding'
import { CustomerDetailPage } from './pages/CustomerDetailPage'
import { ManagerPage } from './pages/ManagerPage'
import { MapPage } from './pages/MapPage'
import { SettingsPage } from './pages/SettingsPage'
import { TodayPage } from './pages/TodayPage'
import {
  type DayPlan,
  DEFAULT_SALESPERSON_ID,
  type Salesperson,
  type Territory,
  fetchDayPlan,
  fetchSalespeople,
  fetchTerritory,
} from './lib/api'

type View = 'today' | 'map' | 'customer' | 'settings' | 'manager'

type NavItem = {
  id: View
  label: string
  Icon: ComponentType<{ size?: number }>
}

const NAV_ITEMS: NavItem[] = [
  { Icon: TodayIcon, id: 'today', label: 'Today' },
  { Icon: MapIcon, id: 'map', label: 'Map' },
  { Icon: CustomerIcon, id: 'customer', label: 'Customer' },
  { Icon: SettingsIcon, id: 'settings', label: 'Settings' },
]

const MIN_STOP_GOAL = 1
const MAX_STOP_GOAL = 10
const DEFAULT_STOP_GOAL = 8
const STOP_GOAL_STORAGE_KEY = 'routeiq.stopGoalOverrides'

type StopGoalOverrides = Record<string, number>

function clampStopGoal(value: number) {
  if (!Number.isFinite(value)) return DEFAULT_STOP_GOAL
  return Math.min(MAX_STOP_GOAL, Math.max(MIN_STOP_GOAL, Math.round(value)))
}

function readStopGoalOverrides(): StopGoalOverrides {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(STOP_GOAL_STORAGE_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return {}

    return Object.entries(parsed).reduce<StopGoalOverrides>((overrides, [id, value]) => {
      if (typeof value === 'number' && Number.isFinite(value)) {
        overrides[id] = clampStopGoal(value)
      }
      return overrides
    }, {})
  } catch {
    return {}
  }
}

function writeStopGoalOverrides(overrides: StopGoalOverrides) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STOP_GOAL_STORAGE_KEY, JSON.stringify(overrides))
  } catch {
    // In private or locked-down browsers the live plan should still update.
  }
}

function App() {
  const [salespeople, setSalespeople] = useState<Salesperson[]>([])
  const [salespersonId, setSalespersonId] = useState<string>(DEFAULT_SALESPERSON_ID)
  const [dayPlan, setDayPlan] = useState<DayPlan | null>(null)
  const [territory, setTerritory] = useState<Territory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<View>('today')
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)
  const [stopGoalOverrides, setStopGoalOverrides] = useState<StopGoalOverrides>(
    readStopGoalOverrides,
  )
  const planRequestRef = useRef(0)

  useEffect(() => {
    fetchSalespeople()
      .then((list) => {
        setSalespeople(list)
        if (list.length > 0 && !list.some((salesperson) => salesperson.id === salespersonId)) {
          setSalespersonId(list[0].id)
        }
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : 'Unable to load salespeople')
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadPlan = useCallback(async (id: string, stopCount?: number) => {
    const requestId = planRequestRef.current + 1
    planRequestRef.current = requestId
    setLoading(true)
    setError(null)
    try {
      const [plan, territoryData] = await Promise.all([
        fetchDayPlan(id, { maxStops: stopCount === undefined ? undefined : clampStopGoal(stopCount) }),
        fetchTerritory(id),
      ])
      if (requestId !== planRequestRef.current) return
      setDayPlan(plan)
      setTerritory(territoryData)
    } catch (caught: unknown) {
      if (requestId === planRequestRef.current) {
        setError(caught instanceof Error ? caught.message : 'Unable to load day plan')
      }
    } finally {
      if (requestId === planRequestRef.current) {
        setLoading(false)
      }
    }
  }, [])

  const activeSalesperson = useMemo(
    () => salespeople.find((salesperson) => salesperson.id === salespersonId) ?? null,
    [salespeople, salespersonId],
  )

  const requestedStopCount =
    stopGoalOverrides[salespersonId] ?? activeSalesperson?.max_daily_stops ?? DEFAULT_STOP_GOAL

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPlan(salespersonId, requestedStopCount)
    }, 220)
    return () => window.clearTimeout(timer)
  }, [salespersonId, requestedStopCount, loadPlan])

  const onSelectCustomer = (customerId: string) => {
    setSelectedCustomerId(customerId)
    setView('customer')
  }

  const onSelectSalesperson = (id: string) => {
    setSalespersonId(id)
    setSelectedCustomerId(null)
    setView('today')
  }

  const onStopCountChange = (value: number) => {
    const nextStopCount = clampStopGoal(value)
    setStopGoalOverrides((current) => {
      if (current[salespersonId] === nextStopCount) return current
      const updated = { ...current, [salespersonId]: nextStopCount }
      writeStopGoalOverrides(updated)
      return updated
    })
  }

  return (
    <main className={view === 'manager' ? 'app-shell app-shell--manager' : 'app-shell'}>
      <Onboarding />
      <AppHeader
        salespersonName={activeSalesperson?.name}
        territoryName={activeSalesperson?.territory_name}
      />
      {view === 'manager' ? (
        <ManagerPage onBack={() => setView('settings')} />
      ) : (
        <>
          {view === 'today' ? (
            <TodayPage
              dayPlan={dayPlan}
              defaultStopCount={activeSalesperson?.max_daily_stops ?? DEFAULT_STOP_GOAL}
              error={error}
              loading={loading}
              maxStopCount={MAX_STOP_GOAL}
              minStopCount={MIN_STOP_GOAL}
              onOpenMap={() => setView('map')}
              onSelectCustomer={onSelectCustomer}
              onStopCountChange={onStopCountChange}
              requestedStopCount={requestedStopCount}
              salespersonName={activeSalesperson?.name ?? 'Salesperson'}
              territoryName={activeSalesperson?.territory_name ?? 'Territory'}
            />
          ) : null}

          {view === 'map' ? (
            <MapPage dayPlan={dayPlan} onSelectCustomer={onSelectCustomer} territory={territory} />
          ) : null}

          {view === 'customer' ? (
            selectedCustomerId ? (
              <CustomerDetailPage
                customerId={selectedCustomerId}
                onAfterVisitLogged={() => loadPlan(salespersonId, requestedStopCount)}
                onBack={() => setView('today')}
                salespersonId={salespersonId}
              />
            ) : (
              <section className="empty-state">
                <p>Select a customer from Today or the Map to see details.</p>
              </section>
            )
          ) : null}

          {view === 'settings' ? (
            <SettingsPage
              onOpenManager={() => setView('manager')}
              onReplan={() => loadPlan(salespersonId, requestedStopCount)}
              onSelectSalesperson={onSelectSalesperson}
              salespeople={salespeople}
              selectedSalespersonId={salespersonId}
            />
          ) : null}

          <nav aria-label="Main navigation" className="bottom-nav">
            {NAV_ITEMS.map((item) => {
              const active = view === item.id
              const ItemIcon = item.Icon
              return (
                <button
                  aria-current={active ? 'page' : undefined}
                  key={item.id}
                  onClick={() => setView(item.id)}
                  type="button"
                >
                  <ItemIcon size={22} />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>
        </>
      )}
    </main>
  )
}

export default App
