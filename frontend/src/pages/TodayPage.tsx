import { useEffect, useMemo, useState } from 'react'

import { NavigateIcon } from '../components/Icon'
import { ImpactCard } from '../components/ImpactCard'
import { Mascot } from '../components/Mascot'
import { MascotTip } from '../components/MascotTip'
import { StopCard } from '../components/StopCard'
import type { DayPlan } from '../lib/api'
import { currencyFormatter } from '../lib/format'

type TodayPageProps = {
  dayPlan: DayPlan | null
  loading: boolean
  error: string | null
  onSelectCustomer: (customerId: string) => void
  onOpenMap: () => void
  salespersonName: string
  territoryName: string
}

export function TodayPage({
  dayPlan,
  error,
  loading,
  onOpenMap,
  onSelectCustomer,
  salespersonName,
  territoryName,
}: TodayPageProps) {
  const nextStop = dayPlan?.stops[0]
  const [waving, setWaving] = useState(true)
  const [visitListMode, setVisitListMode] = useState<'top5' | 'all'>('top5')
  const visibleStops = useMemo(() => {
    if (!dayPlan) return []
    return visitListMode === 'top5' ? dayPlan.stops.slice(0, 5) : dayPlan.stops
  }, [dayPlan, visitListMode])

  useEffect(() => {
    const timer = window.setTimeout(() => setWaving(false), 1700)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <>
      <section className="hero-card">
        <div>
          <p className="eyebrow">Today's plan</p>
          <h1>Your most valuable route</h1>
          <p className="hero-copy">
            Not just the shortest path: prioritized by value, urgency, proximity, and territory coverage.
          </p>
          <p className="hero-meta">
            {salespersonName} · {territoryName}
          </p>
        </div>
        <div className="hero-mascot">
          <Mascot mood="happy" size={92} waving={waving} />
          <span className="hero-mascot-count">
            <strong>{dayPlan?.stops.length ?? 0}</strong> stops
          </span>
        </div>
      </section>

      {error ? <p className="status error">{error}</p> : null}
      {loading && !dayPlan ? (
        <div className="loading-state">
          <Mascot mood="thinking" size={84} />
          <p>Optimizing today's route...</p>
        </div>
      ) : null}

      {dayPlan ? (
        <>
          {dayPlan.optimization_summary ? (
            <ImpactCard summary={dayPlan.optimization_summary} />
          ) : null}

          <section aria-label="Plan summary" className="summary-grid">
            <article>
              <span>Expected return</span>
              <strong>{currencyFormatter.format(dayPlan.total_expected_return_rm)}</strong>
            </article>
            <article>
              <span>Travel distance</span>
              <strong>{dayPlan.total_distance_km.toFixed(1)} km</strong>
            </article>
          </section>

          {nextStop ? (
            <section className="next-card">
              <div>
                <p className="eyebrow">Next best visit</p>
                <h2>{nextStop.customer_name}</h2>
                <p className="reason">{nextStop.reason}</p>
              </div>
              <MascotTip label="Focus for this meeting" message={nextStop.focus} mood="happy" />
              <button className="primary-action" onClick={onOpenMap} type="button">
                <NavigateIcon size={18} />
                <span>Start navigation</span>
              </button>
            </section>
          ) : null}

          <section aria-label="Recommended visits" className="route-list">
            <div className="section-header">
              <div>
                <h2>Visit order</h2>
                <span>{dayPlan.date}</span>
              </div>
              <div aria-label="Visit list filter" className="route-filter">
                <button
                  aria-pressed={visitListMode === 'top5'}
                  onClick={() => setVisitListMode('top5')}
                  type="button"
                >
                  Top 5
                </button>
                <button
                  aria-pressed={visitListMode === 'all'}
                  onClick={() => setVisitListMode('all')}
                  type="button"
                >
                  All
                </button>
              </div>
            </div>

            {visibleStops.map((stop) => (
              <StopCard key={stop.customer_id} onSelect={onSelectCustomer} stop={stop} />
            ))}
          </section>
        </>
      ) : null}
    </>
  )
}
