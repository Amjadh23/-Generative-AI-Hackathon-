import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'

import { MinusIcon, NavigateIcon, PlusIcon } from '../components/Icon'
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
  onStopCountChange: (stopCount: number) => void
  requestedStopCount: number
  defaultStopCount: number
  minStopCount: number
  maxStopCount: number
  salespersonName: string
  territoryName: string
}

export function TodayPage({
  dayPlan,
  defaultStopCount,
  error,
  loading,
  maxStopCount,
  minStopCount,
  onOpenMap,
  onSelectCustomer,
  onStopCountChange,
  requestedStopCount,
  salespersonName,
  territoryName,
}: TodayPageProps) {
  const nextStop = dayPlan?.stops[0]
  const [waving, setWaving] = useState(true)
  const [visitListMode, setVisitListMode] = useState<'top5' | 'all'>('top5')
  const [draftStopCountState, setDraftStopCountState] = useState({
    stopCount: requestedStopCount,
    value: String(requestedStopCount),
  })
  const draftStopCount =
    draftStopCountState.stopCount === requestedStopCount
      ? draftStopCountState.value
      : String(requestedStopCount)
  const setDraftStopCount = (value: string) =>
    setDraftStopCountState({ stopCount: requestedStopCount, value })
  const visibleStops = useMemo(() => {
    if (!dayPlan) return []
    return visitListMode === 'top5' ? dayPlan.stops.slice(0, 5) : dayPlan.stops
  }, [dayPlan, visitListMode])
  const plannedStopCount = dayPlan?.stops.length ?? requestedStopCount
  const stopPlanLabel =
    requestedStopCount < defaultStopCount
      ? 'Compact route'
      : requestedStopCount > defaultStopCount
        ? 'Growth push'
        : 'Standard route'
  const presetOptions = useMemo(() => {
    const options = [
      { label: 'Quick', value: Math.max(minStopCount, defaultStopCount - 3) },
      { label: 'Standard', value: defaultStopCount },
      { label: 'Push', value: Math.min(maxStopCount, defaultStopCount + 2) },
    ]

    return options.filter(
      (option, index) => options.findIndex((candidate) => candidate.value === option.value) === index,
    )
  }, [defaultStopCount, maxStopCount, minStopCount])

  useEffect(() => {
    const timer = window.setTimeout(() => setWaving(false), 1700)
    return () => window.clearTimeout(timer)
  }, [])

  const normalizeStopCount = (value: number) =>
    Math.min(maxStopCount, Math.max(minStopCount, Math.round(value)))

  const applyStopCount = (value: number) => {
    const nextStopCount = normalizeStopCount(value)
    setDraftStopCount(String(nextStopCount))
    onStopCountChange(nextStopCount)
  }

  const commitDraftStopCount = () => {
    const parsed = Number.parseInt(draftStopCount, 10)
    if (Number.isNaN(parsed)) {
      setDraftStopCount(String(requestedStopCount))
      return
    }
    applyStopCount(parsed)
  }

  const onStopInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.currentTarget.blur()
    }
  }

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
            <strong>{plannedStopCount}</strong> stops
          </span>
        </div>
      </section>

      <section aria-label="Daily stop planner" className="plan-tuner">
        <div className="plan-tuner-header">
          <div>
            <span className="plan-tuner-kicker">Route capacity</span>
            <h2>{stopPlanLabel}</h2>
          </div>
          <span className={loading ? 'plan-tuner-status active' : 'plan-tuner-status'}>
            {loading ? `Optimizing ${requestedStopCount}` : `${plannedStopCount} planned`}
          </span>
        </div>

        <div className="stop-planner">
          <div className="stop-input-row">
            <label className="stop-input-label" htmlFor="daily-stop-count">
              Stops today
            </label>
            <div className="stop-stepper">
              <button
                aria-label="Reduce stops"
                disabled={requestedStopCount <= minStopCount}
                onClick={() => applyStopCount(requestedStopCount - 1)}
                title="Reduce stops"
                type="button"
              >
                <MinusIcon size={18} />
              </button>
              <input
                aria-label="Stops today"
                id="daily-stop-count"
                inputMode="numeric"
                max={maxStopCount}
                min={minStopCount}
                onBlur={commitDraftStopCount}
                onChange={(event) => setDraftStopCount(event.target.value)}
                onKeyDown={onStopInputKeyDown}
                type="number"
                value={draftStopCount}
              />
              <button
                aria-label="Add stop"
                disabled={requestedStopCount >= maxStopCount}
                onClick={() => applyStopCount(requestedStopCount + 1)}
                title="Add stop"
                type="button"
              >
                <PlusIcon size={18} />
              </button>
            </div>
          </div>

          <input
            aria-label="Daily stop count"
            className="stop-range"
            max={maxStopCount}
            min={minStopCount}
            onChange={(event) => applyStopCount(Number(event.target.value))}
            step={1}
            type="range"
            value={requestedStopCount}
          />

          <div aria-label="Stop count presets" className="stop-presets">
            {presetOptions.map((preset) => (
              <button
                aria-pressed={requestedStopCount === preset.value}
                key={preset.label}
                onClick={() => applyStopCount(preset.value)}
                type="button"
              >
                <span>{preset.label}</span>
                <strong>{preset.value}</strong>
              </button>
            ))}
          </div>
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
            <ImpactCard stopCount={plannedStopCount} summary={dayPlan.optimization_summary} />
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
