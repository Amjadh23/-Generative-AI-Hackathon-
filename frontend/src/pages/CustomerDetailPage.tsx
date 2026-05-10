import { useEffect, useState } from 'react'

import { BackIcon, CheckIcon, NavigateIcon } from '../components/Icon'
import { MascotTip } from '../components/MascotTip'
import { VisitRecapPanel } from '../components/VisitRecap'
import {
  type CustomerDetail,
  fetchCustomer,
  logVisit,
  type VisitOutcome,
} from '../lib/api'
import {
  currencyFormatter,
  displayRecommendedAction,
  formatSegment,
  googleMapsUrl,
  percentFormatter,
} from '../lib/format'

type CustomerDetailPageProps = {
  customerId: string
  salespersonId: string
  onBack: () => void
  onAfterVisitLogged: () => Promise<void> | void
}

const OUTCOMES: { id: VisitOutcome; label: string }[] = [
  { id: 'order', label: 'Order' },
  { id: 'follow_up', label: 'Follow up' },
  { id: 'no_interest', label: 'No interest' },
  { id: 'closed', label: 'Closed' },
]

export function CustomerDetailPage({
  customerId,
  onAfterVisitLogged,
  onBack,
  salespersonId,
}: CustomerDetailPageProps) {
  const [customer, setCustomer] = useState<CustomerDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [outcome, setOutcome] = useState<VisitOutcome>('order')
  const [notes, setNotes] = useState('')
  const [confirmation, setConfirmation] = useState<string | null>(null)

  const loadCustomer = async () => {
    setError(null)
    try {
      const data = await fetchCustomer(customerId)
      setCustomer(data)
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Unable to load customer')
    }
  }

  useEffect(() => {
    setCustomer(null)
    void loadCustomer()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId])

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      await logVisit({
        customerId,
        notes: notes.trim() || undefined,
        outcome,
        salespersonId,
      })
      setConfirmation(`Visit logged as ${outcome.replace('_', ' ')}.`)
      setNotes('')
      await onAfterVisitLogged()
      await loadCustomer()
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Unable to log visit')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="customer-page">
      <button className="link-button" onClick={onBack} type="button">
        <BackIcon size={18} />
        <span>Back to plan</span>
      </button>

      {error ? <p className="status error">{error}</p> : null}
      {!customer && !error ? <p className="status">Loading customer...</p> : null}

      {customer ? (
        <>
          <header className="customer-header">
            <p className="eyebrow">{formatSegment(customer.segment)}</p>
            <h2>{customer.name}</h2>
            <p className="customer-meta">
              RouteIQ {customer.priority_class} · {(customer.visit_likelihood_score * 100).toFixed(0)}% visit
              likelihood · {customer.last_visit_days} days since last visit
            </p>
            <a
              className="primary-action customer-navigate"
              href={googleMapsUrl(customer.lat, customer.lng)}
              rel="noreferrer"
              target="_blank"
            >
              <NavigateIcon size={18} />
              <span>Navigate</span>
            </a>
          </header>

          <section aria-label="Score signals" className="summary-grid">
            <article>
              <span>RouteIQ score (0–100)</span>
              <strong>{Math.round(customer.score)}</strong>
            </article>
            <article>
              <span>Suggested action</span>
              <strong>
                {displayRecommendedAction(customer.recommended_action, customer.priority_class)}
              </strong>
            </article>
            <article>
              <span>Expected return</span>
              <strong>{currencyFormatter.format(customer.expected_return_rm)}</strong>
            </article>
            <article>
              <span>Avg order value</span>
              <strong>{currencyFormatter.format(customer.avg_order_value_rm)}</strong>
            </article>
            <article>
              <span>Reorder probability</span>
              <strong>{percentFormatter.format(customer.reorder_probability)}</strong>
            </article>
            <article>
              <span>Visit confidence</span>
              <strong>{percentFormatter.format(customer.sentiment_confidence_score)}</strong>
            </article>
          </section>

          <MascotTip
            label="Why this score"
            message={
              customer.top_reasons.length > 0
                ? customer.top_reasons.join(' ')
                : `RouteIQ ranked this customer ${Math.round(customer.score)} using visit likelihood from recency, pipeline, order history, and reorder probability (CRM priority ${customer.crm_priority} is not a model input).`
            }
            mood="thinking"
          />

          <section className="contribution-card">
            <h3>Score breakdown</h3>
            <ul className="contribution-list">
              {Object.entries(customer.score_contributions).map(([key, value]) => {
                const widthPercent = Math.min(100, Math.round(value * 100 * 4))
                return (
                  <li key={key}>
                    <div className="contribution-label">
                      <span>{formatSegment(key)}</span>
                      <span>{(value * 100).toFixed(1)}</span>
                    </div>
                    <div className="contribution-bar">
                      <div className="contribution-fill" style={{ width: `${widthPercent}%` }} />
                    </div>
                  </li>
                )
              })}
            </ul>
          </section>

          <section className="history-card">
            <h3>Recent orders</h3>
            {customer.orders.length === 0 ? (
              <p className="status">No orders yet.</p>
            ) : (
              <ul className="history-list">
                {customer.orders.map((order) => (
                  <li key={order.id}>
                    <span>{order.order_date}</span>
                    <span>{formatSegment(order.product_family)}</span>
                    <strong>{currencyFormatter.format(order.amount_rm)}</strong>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="history-card">
            <h3>Recent visits</h3>
            {customer.visits.length === 0 ? (
              <p className="status">No visits yet.</p>
            ) : (
              <ul className="history-list">
                {customer.visits.map((visit) => (
                  <li key={visit.id}>
                    <span>{visit.visited_at.slice(0, 10)}</span>
                    <span>{formatSegment(visit.outcome)}</span>
                    <span className="history-notes">{visit.notes ?? ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <VisitRecapPanel
            customerId={customer.id}
            customerName={customer.name}
            key={customer.id}
            onPersisted={() => {
              void onAfterVisitLogged()
              void loadCustomer()
              setConfirmation('AI recap saved as a visit. The plan will refresh.')
            }}
            salespersonId={salespersonId}
          />

          <form className="visit-form" onSubmit={onSubmit}>
            <h3>Mark visit</h3>
            <div className="outcome-grid">
              {OUTCOMES.map((option) => {
                const active = outcome === option.id
                return (
                  <button
                    aria-pressed={active}
                    className={active ? 'outcome-button active' : 'outcome-button'}
                    key={option.id}
                    onClick={() => setOutcome(option.id)}
                    type="button"
                  >
                    {option.label}
                  </button>
                )
              })}
            </div>
            <label className="notes-field">
              <span>Notes</span>
              <textarea
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Discussion summary, next action..."
                rows={3}
                value={notes}
              />
            </label>
            <button className="primary-action" disabled={submitting} type="submit">
              <CheckIcon size={18} />
              <span>{submitting ? 'Logging...' : 'Log visit'}</span>
            </button>
            {confirmation ? <p className="status success">{confirmation}</p> : null}
          </form>
        </>
      ) : null}
    </section>
  )
}
