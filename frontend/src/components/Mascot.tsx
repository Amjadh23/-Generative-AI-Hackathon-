import mascotUrl from '../assets/mascot.png'

type MascotMood = 'idle' | 'happy' | 'thinking'

type MascotProps = {
  size?: number
  mood?: MascotMood
  waving?: boolean
}

export function Mascot({ mood = 'idle', size = 80, waving = false }: MascotProps) {
  const classes = ['mascot', 'mascot-img-wrap']
  if (waving) {
    classes.push('mascot-waving')
  } else if (mood === 'thinking') {
    classes.push('mascot-thinking')
  }

  return (
    <div
      aria-label="RouteIQ assistant"
      className={classes.join(' ')}
      role="img"
      style={{ width: size, height: size }}
    >
      <img
        alt=""
        className="mascot-img"
        decoding="async"
        src={mascotUrl}
        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
      />
    </div>
  )
}
