import type { ReactNode } from 'react'

import { Mascot } from './Mascot'

type MascotTipProps = {
  message: ReactNode
  label?: string
  mood?: 'idle' | 'happy' | 'thinking'
}

export function MascotTip({ label = 'RouteIQ tip', message, mood = 'happy' }: MascotTipProps) {
  return (
    <div className="mascot-tip">
      <div className="mascot-tip-figure">
        <Mascot mood={mood} size={64} />
      </div>
      <div className="mascot-tip-bubble">
        <span className="mascot-tip-label">{label}</span>
        {typeof message === 'string' ? <p>{message}</p> : message}
      </div>
    </div>
  )
}
