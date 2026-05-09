import { HiltiLogo } from './Icon'

type AppHeaderProps = {
  salespersonName?: string
  territoryName?: string
}

export function AppHeader({ salespersonName, territoryName }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div className="app-header-brand">
        <HiltiLogo height={26} />
        <div className="app-header-title">
          <span className="app-header-product">RouteIQ</span>
          <span className="app-header-tagline">AI sales visit copilot</span>
        </div>
      </div>
      {salespersonName ? (
        <div className="app-header-meta">
          <span>{salespersonName}</span>
          {territoryName ? <small>{territoryName}</small> : null}
        </div>
      ) : null}
    </header>
  )
}
