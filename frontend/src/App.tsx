import { useCallback, useEffect, useMemo, useState, type ComponentType } from 'react'

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

function App() {
  const [salespeople, setSalespeople] = useState<Salesperson[]>([])
  const [salespersonId, setSalespersonId] = useState<string>(DEFAULT_SALESPERSON_ID)
  const [dayPlan, setDayPlan] = useState<DayPlan | null>(null)
  const [territory, setTerritory] = useState<Territory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<View>('today')
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)

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

  const loadPlan = useCallback(async (id: string) => {
    setLoading(true)
    setError(null)
    try {
      const [plan, territoryData] = await Promise.all([fetchDayPlan(id), fetchTerritory(id)])
      setDayPlan(plan)
      setTerritory(territoryData)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Unable to load day plan')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadPlan(salespersonId)
  }, [salespersonId, loadPlan])

  const activeSalesperson = useMemo(
    () => salespeople.find((salesperson) => salesperson.id === salespersonId) ?? null,
    [salespeople, salespersonId],
  )

  const onSelectCustomer = (customerId: string) => {
    setSelectedCustomerId(customerId)
    setView('customer')
  }

  const onSelectSalesperson = (id: string) => {
    setSalespersonId(id)
    setSelectedCustomerId(null)
    setView('today')
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
              error={error}
              loading={loading}
              onOpenMap={() => setView('map')}
              onSelectCustomer={onSelectCustomer}
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
                onAfterVisitLogged={() => loadPlan(salespersonId)}
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
              onReplan={() => loadPlan(salespersonId)}
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
