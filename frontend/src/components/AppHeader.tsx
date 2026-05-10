import { HiltiLogo, RouteIQWordmark } from './Icon'

type AppHeaderProps = {
  salespersonName?: string
  territoryName?: string
}

export function AppHeader({ salespersonName, territoryName }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div className="app-header-brand">
        <HiltiLogo height={28} />
        <div className="app-header-title">
          <RouteIQWordmark height={30} />
          <span className="app-header-tagline">AI sales visit copilot</span>
        </div>
      </div>
      <div className="app-header-end">
        {salespersonName ? (
          <div className="app-header-meta">
            <span>{salespersonName}</span>
            {territoryName ? <small>{territoryName}</small> : null}
          </div>
        ) : null}
      </div>
    </header>
  )
}
