import type { SVGProps } from 'react'

import hiltiMarkUrl from '../assets/hilti.png'
import routeiqWordmarkUrl from '../assets/logo.png'

type IconProps = SVGProps<SVGSVGElement> & {
  size?: number
}

function BaseIcon({ children, size = 22, ...rest }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.8}
      viewBox="0 0 24 24"
      width={size}
      xmlns="http://www.w3.org/2000/svg"
      {...rest}
    >
      {children}
    </svg>
  )
}

export function TodayIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <rect height="16" rx="2.5" width="17" x="3.5" y="4.5" />
      <path d="M3.5 9.5h17M8 3v3M16 3v3" />
      <path d="m8.5 14 2.2 2.2L15.5 11" />
    </BaseIcon>
  )
}

export function MapIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M9 4.5 3.5 6.5v13L9 17.5l6 2 5.5-2v-13L15 6.5Z" />
      <path d="M9 4.5v13M15 6.5v13" />
    </BaseIcon>
  )
}

export function CustomerIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="12" cy="9" r="3.6" />
      <path d="M5 20c1.4-3.4 4-5 7-5s5.6 1.6 7 5" />
    </BaseIcon>
  )
}

export function SettingsIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9c.3.6.9 1 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </BaseIcon>
  )
}

export function TeamIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M8.5 11a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
      <path d="M15.5 11a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
      <path d="M3 19c1.2-3.5 3.7-6 7-6s5.8 2.5 7 6" />
      <path d="M14 19c1.2-3.5 3.7-6 7-6" />
    </BaseIcon>
  )
}

export function NavigateIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M5 12 19 5l-3 14-3.5-6Z" />
      <path d="M12.5 13 19 5" />
    </BaseIcon>
  )
}

export function BackIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M14 6 8 12l6 6" />
    </BaseIcon>
  )
}

export function CheckIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m5 13 4 4 10-10" />
    </BaseIcon>
  )
}

export function PlayIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M7 5v14l12-7Z" fill="currentColor" stroke="none" />
    </BaseIcon>
  )
}

export function StopIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <rect height="12" rx="2" width="12" x="6" y="6" fill="currentColor" stroke="none" />
    </BaseIcon>
  )
}

export function VolumeIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 10v4h3l5 4V6L7 10Z" />
      <path d="M16 9c1.5 1.2 1.5 4.8 0 6" />
      <path d="M18.5 7c2.5 2 2.5 8 0 10" />
    </BaseIcon>
  )
}

export function MuteIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 10v4h3l5 4V6L7 10Z" />
      <path d="m16 9 5 6m0-6-5 6" />
    </BaseIcon>
  )
}

type ManeuverIconProps = IconProps & {
  type: string
  modifier?: string
}

export function ManeuverIcon({ modifier, size = 24, type, ...rest }: ManeuverIconProps) {
  if (type === 'arrive') {
    return (
      <BaseIcon size={size} {...rest}>
        <path d="M12 22s7-7.5 7-13a7 7 0 1 0-14 0c0 5.5 7 13 7 13Z" />
        <circle cx="12" cy="9" r="2.4" />
      </BaseIcon>
    )
  }
  if (type === 'depart') {
    return (
      <BaseIcon size={size} {...rest}>
        <circle cx="12" cy="12" r="3.5" />
        <path d="M12 4v3M12 17v3M4 12h3M17 12h3" />
      </BaseIcon>
    )
  }
  if (type === 'roundabout' || type === 'rotary') {
    return (
      <BaseIcon size={size} {...rest}>
        <circle cx="12" cy="13" r="5" />
        <path d="M12 13V4M12 4l-3 3M12 4l3 3" />
      </BaseIcon>
    )
  }
  if (type === 'merge') {
    return (
      <BaseIcon size={size} {...rest}>
        <path d="M8 21V12c0-3 4-3 4-7" />
        <path d="M12 5l-2-2M12 5l2-2" />
        <path d="M16 21V14" />
      </BaseIcon>
    )
  }
  if (modifier === 'left' || modifier === 'sharp left') {
    return (
      <BaseIcon size={size} {...rest}>
        <path d="M12 21V10" />
        <path d="M12 10c0-2 0-4-3-4H5" />
        <path d="M5 6l3-3M5 6l3 3" />
      </BaseIcon>
    )
  }
  if (modifier === 'right' || modifier === 'sharp right') {
    return (
      <BaseIcon size={size} {...rest}>
        <path d="M12 21V10" />
        <path d="M12 10c0-2 0-4 3-4h4" />
        <path d="M19 6l-3-3M19 6l-3 3" />
      </BaseIcon>
    )
  }
  if (modifier === 'slight left') {
    return (
      <BaseIcon size={size} {...rest}>
        <path d="M12 21V12" />
        <path d="M12 12 7 6" />
        <path d="M7 6h4M7 6v4" />
      </BaseIcon>
    )
  }
  if (modifier === 'slight right') {
    return (
      <BaseIcon size={size} {...rest}>
        <path d="M12 21V12" />
        <path d="M12 12 17 6" />
        <path d="M17 6h-4M17 6v4" />
      </BaseIcon>
    )
  }
  return (
    <BaseIcon size={size} {...rest}>
      <path d="M12 21V5" />
      <path d="M12 5l-3 3M12 5l3 3" />
    </BaseIcon>
  )
}

export function HiltiLogo({ height = 24 }: { height?: number }) {
  return (
    <img
      alt="Hilti"
      className="hilti-logo"
      height={height}
      loading="lazy"
      src={hiltiMarkUrl}
      style={{ height, width: 'auto', display: 'block', objectFit: 'contain' }}
    />
  )
}

/** Red RouteIQ wordmark PNG — use in header; app icon stays `RouteIQLogo`. */
export function RouteIQWordmark({ height = 22 }: { height?: number }) {
  return (
    <img
      alt="RouteIQ"
      className="routeiq-wordmark"
      height={height}
      loading="lazy"
      src={routeiqWordmarkUrl}
      style={{ height, width: 'auto', display: 'block', objectFit: 'contain' }}
    />
  )
}

export function RouteIQLogo({ size = 28 }: { size?: number }) {
  return (
    <svg
      aria-label="Hilti RouteIQ"
      height={size}
      role="img"
      viewBox="0 0 32 32"
      width={size}
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect fill="currentColor" height="32" rx="8" width="32" />
      <path
        d="M8 21c2.5 0 3.5-3 6-3s3.5 3 6 3"
        fill="none"
        stroke="#ffffff"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.4"
      />
      <circle cx="8" cy="21" fill="#ffffff" r="2.4" />
      <circle cx="20" cy="21" fill="#ffffff" r="2.4" />
      <path
        d="M16 6v8m0 0-3-3m3 3 3-3"
        fill="none"
        stroke="#ffffff"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.2"
      />
    </svg>
  )
}
