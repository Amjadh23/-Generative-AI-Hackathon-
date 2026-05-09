import type { Salesperson } from '../lib/api'

type SettingsPageProps = {
  salespeople: Salesperson[]
  selectedSalespersonId: string
  onSelectSalesperson: (salespersonId: string) => void
  onReplan: () => void
}

export function SettingsPage({
  onReplan,
  onSelectSalesperson,
  salespeople,
  selectedSalespersonId,
}: SettingsPageProps) {
  return (
    <section className="settings-page">
      <header>
        <p className="eyebrow">Settings</p>
        <h2>Daily setup</h2>
        <p className="settings-meta">
          Switch salesperson to demo coverage across territories. The plan re-runs immediately.
        </p>
      </header>

      <div className="settings-card">
        <h3>Salesperson</h3>
        <ul className="settings-list">
          {salespeople.map((salesperson) => {
            const active = salesperson.id === selectedSalespersonId
            return (
              <li key={salesperson.id}>
                <button
                  className={active ? 'settings-row active' : 'settings-row'}
                  onClick={() => onSelectSalesperson(salesperson.id)}
                  type="button"
                >
                  <div>
                    <strong>{salesperson.name}</strong>
                    <span>{salesperson.territory_name}</span>
                  </div>
                  <span className="settings-badge">{salesperson.max_daily_stops} stops</span>
                </button>
              </li>
            )
          })}
        </ul>
      </div>

      <button className="primary-action" onClick={onReplan} type="button">
        Re-run plan
      </button>
    </section>
  )
}
