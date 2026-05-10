import { useEffect, useMemo, useState } from 'react'

import { BackIcon } from '../components/Icon'
import { type ManagerDashboard, fetchManagerDashboard } from '../lib/api'
import { formatSegment } from '../lib/format'

type ManagerPageProps = {
  onBack: () => void
}

function MeterRow({
  hint,
  label,
  value,
  variant,
}: {
  hint: string
  label: string
  value: number
  variant: 'before' | 'after'
}) {
  const width = Math.min(100, Math.max(0, value))
  return (
    <div className={`manager-meter manager-meter--${variant}`}>
      <div className="manager-meter-head">
        <span className="manager-meter-label">{label}</span>
        <span className="manager-meter-value">{value}</span>
      </div>
      <div aria-hidden className="manager-meter-track">
        <div className="manager-meter-fill" style={{ width: `${width}%` }} />
      </div>
      <p className="manager-meter-hint">{hint}</p>
    </div>
  )
}

function formatVisitedAt(iso: string): string {
  const d = iso.slice(0, 10)
  const t = iso.length > 11 ? iso.slice(11, 16) : ''
  return t ? `${d} · ${t}` : d
}

function formatConfidence(value: number | null | undefined, fallback = 50): string {
  return `${Math.round(value ?? fallback)}%`
}

export function ManagerPage({ onBack }: ManagerPageProps) {
  const [data, setData] = useState<ManagerDashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [interestedOnly, setInterestedOnly] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setError(null)
      try {
        const dashboard = await fetchManagerDashboard()
        if (!cancelled) setData(dashboard)
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'Could not load manager view.')
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const impact = data?.recap_impact
  const hasSentimentSpotlight =
    typeof impact?.spotlight_confidence_before === 'number' &&
    typeof impact?.spotlight_confidence_after === 'number'

  const filteredRecaps = useMemo(() => {
    const rows = data?.recent_ai_recaps ?? []
    if (!interestedOnly) return rows
    return rows.filter((r) => r.is_interested)
  }, [data?.recent_ai_recaps, interestedOnly])

  return (
    <section className="manager-page">
      <button className="link-button manager-back" onClick={onBack} type="button">
        <BackIcon size={18} />
        <span>Back to settings</span>
      </button>

      <header className="manager-header">
        <p className="eyebrow">Manager</p>
        <h2>Opportunity confidence</h2>
      </header>

      {error ? <p className="status error">{error}</p> : null}
      {!data && !error ? <p className="status">Loading…</p> : null}

      {data ? (
        <>
          <p className="manager-recap-note">{data.recap_monitor_note}</p>

          <div className="manager-rep-strip" aria-label="Recap activity by rep">
            {data.reps.map((rep) => (
              <div className="manager-rep-chip" key={rep.salesperson_id}>
                <strong>{rep.name}</strong>
                <span>
                  {rep.interested_recaps_30d} warm recap{rep.interested_recaps_30d === 1 ? '' : 's'} (30d)
                  {' · '}
                  {rep.ai_recap_visit_count} evaluations total
                </span>
              </div>
            ))}
          </div>

          <div className="manager-recap-toolbar">
            <h3>After visit - evaluated outcomes</h3>
            <label className="manager-filter-toggle">
              <input
                checked={interestedOnly}
                onChange={(e) => setInterestedOnly(e.target.checked)}
                type="checkbox"
              />
              Interested only (order / follow-up / closed)
            </label>
          </div>

          <div className="manager-recap-table-wrap">
            {filteredRecaps.length === 0 ? (
              <p className="manager-recap-empty">
                {interestedOnly
                  ? 'No interested evaluations in this list. Turn off the filter or log more visit sentiment from the field.'
                  : 'No visit evaluations yet. When reps save a voice recap or quick sentiment, it will appear here.'}
              </p>
            ) : (
              <table className="manager-recap-table">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Interest</th>
                    <th>Rep</th>
                    <th>When</th>
                    <th>Recap</th>
                    <th>Next step</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRecaps.map((row) => (
                    <tr key={row.visit_id}>
                      <td>
                        <strong>{row.customer_name}</strong>
                        <div style={{ fontSize: '11px', color: 'var(--ink-muted)' }}>
                          {formatSegment(row.segment)} · {row.territory_name}
                        </div>
                      </td>
                      <td>
                        <span
                          className={row.is_interested ? 'manager-interest-warm' : 'manager-interest-cold'}
                        >
                          {row.interest_label}
                        </span>
                        <div style={{ fontSize: '11px', color: 'var(--ink-muted)', marginTop: '4px' }}>
                          {formatSegment(row.outcome)}
                        </div>
                      </td>
                      <td>{row.salesperson_name}</td>
                      <td>{formatVisitedAt(row.visited_at)}</td>
                      <td className="manager-recap-summary">{row.summary || '—'}</td>
                      <td className="manager-recap-summary">{row.next_action || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      ) : null}

      {impact ? (
        <>
          <p className="manager-lead">Fresh visit sentiment turns field notes into account confidence.</p>
          <p className="manager-sublead">
            Every account starts at 50%. AI recaps and quick visit buttons move that score after the rep meets the customer.
          </p>

          <div className="manager-story-card manager-spotlight">
            <h3 className="manager-story-title">Opportunity confidence</h3>
            <p className="manager-spotlight-name">
              {hasSentimentSpotlight
                ? impact.spotlight_customer_name
                : 'No visit sentiment recorded yet'}
            </p>
            <div className="manager-spotlight-compare">
              <div>
                <span className="manager-spotlight-k">
                  {hasSentimentSpotlight ? 'Initial' : 'Baseline'}
                </span>
                <strong>{formatConfidence(impact.spotlight_confidence_before)}</strong>
              </div>
              <span aria-hidden className="manager-spotlight-arrow">
                -&gt;
              </span>
              <div>
                <span className="manager-spotlight-k">After visit</span>
                <strong>
                  {hasSentimentSpotlight
                    ? formatConfidence(impact.spotlight_confidence_after)
                    : '--'}
                </strong>
              </div>
            </div>
            <p className="manager-spotlight-outcome">
              {hasSentimentSpotlight ? (
                <>
                  Sentiment:{' '}
                  <span className="manager-outcome-pill">
                    {formatSegment(impact.spotlight_sentiment ?? 'neutral')}
                  </span>
                  {impact.spotlight_sentiment_source ? (
                    <span className="manager-spotlight-source">
                      {formatSegment(impact.spotlight_sentiment_source)}
                    </span>
                  ) : null}
                </>
              ) : (
                'Waiting for the next AI recap or quick sentiment evaluation.'
              )}
            </p>
          </div>

          <div className="manager-story-card">
            <h3 className="manager-story-title">Team future potential</h3>
            <MeterRow
              hint="Territory, CRM, order history, and route scoring before fresh field sentiment."
              label="Planning baseline"
              value={impact.avg_before}
              variant="before"
            />
            <MeterRow
              hint="Updated with recent visit outcomes, structured recaps, and quick sentiment signals."
              label="After field signals"
              value={impact.avg_after}
              variant="after"
            />
          </div>

          {!hasSentimentSpotlight && impact.spotlight_customer_name ? (
            <div className="manager-story-card manager-spotlight">
              <h3 className="manager-story-title">Top potential movement</h3>
              <p className="manager-spotlight-name">{impact.spotlight_customer_name}</p>
              <div className="manager-spotlight-compare">
                <div>
                  <span className="manager-spotlight-k">Planning baseline</span>
                  <strong>{impact.spotlight_before}</strong>
                </div>
                <span aria-hidden className="manager-spotlight-arrow">
                  →
                </span>
                <div>
                  <span className="manager-spotlight-k">Current signal</span>
                  <strong>{impact.spotlight_after}</strong>
                </div>
              </div>
              {impact.spotlight_outcome ? (
                <p className="manager-spotlight-outcome">
                  Last visit:{' '}
                  <span className="manager-outcome-pill">{formatSegment(impact.spotlight_outcome)}</span>
                </p>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
