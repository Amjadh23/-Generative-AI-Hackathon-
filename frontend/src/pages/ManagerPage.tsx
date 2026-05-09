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
        <h2>Recaps &amp; future potential</h2>
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
                  {rep.ai_recap_visit_count} AI total
                </span>
              </div>
            ))}
          </div>

          <div className="manager-recap-toolbar">
            <h3>After visit — AI recap outcomes</h3>
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
                  ? 'No interested recaps in this list. Turn off the filter or log more AI recaps from the field.'
                  : 'No AI recaps yet. When reps save a voice recap, it will appear here with outcome and summary.'}
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
          <p className="manager-lead">{impact.headline}</p>
          <p className="manager-sublead">{impact.subhead}</p>

          <div className="manager-story-card">
            <h3 className="manager-story-title">Team average</h3>
            <MeterRow
              hint="From territory and CRM data only — no recent visit story yet."
              label="Before visits & recaps"
              value={impact.avg_before}
              variant="before"
            />
            <MeterRow
              hint="After logging satisfied outcomes and structured recaps."
              label="After satisfied visits"
              value={impact.avg_after}
              variant="after"
            />
          </div>

          {impact.spotlight_customer_name ? (
            <div className="manager-story-card manager-spotlight">
              <h3 className="manager-story-title">Example account</h3>
              <p className="manager-spotlight-name">{impact.spotlight_customer_name}</p>
              <div className="manager-spotlight-compare">
                <div>
                  <span className="manager-spotlight-k">Was</span>
                  <strong>{impact.spotlight_before}</strong>
                </div>
                <span aria-hidden className="manager-spotlight-arrow">
                  →
                </span>
                <div>
                  <span className="manager-spotlight-k">Now</span>
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
