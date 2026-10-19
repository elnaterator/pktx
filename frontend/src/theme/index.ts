/**
 * JS-side theme values. CSS lives in styles/tokens.css; this file holds only
 * what JS needs as literals (third-party appearance objects, icon props).
 * `palette` mirrors tokens.css — a test fails if the two drift.
 */

/** Hex values of the colour tokens in styles/tokens.css, keyed by token name. */
export const palette = {
  'bg-primary': '#1a1a1a',
  'bg-input': '#141414',
  'bg-raised-hover': '#2a2a2a',
  'bg-modal-overlay': 'rgba(0, 0, 0, 0.7)',
  'text-primary': '#e0e0e0',
  'text-secondary': '#b3b3b3',
  'text-muted': '#949494',
  'accent-green': '#52b788',
  'accent-green-dim': '#40916c',
  'accent-green-bg': 'rgba(82, 183, 136, 0.07)',
  'status-error': '#ff4444',
} as const

/** Colours used only inside Clerk's own UI (no CSS token counterpart). */
export const clerkPalette = {
  border: palette['bg-raised-hover'],
  neutral: '#888888',
  faint: '#555555',
} as const

export const fontMono =
  "'JetBrains Mono', 'Fira Code', 'SF Mono', 'Cascadia Code', ui-monospace, monospace"

/** Lucide icon sizes (px). Use these instead of literal `size={n}`. */
export const ICON_SIZE = {
  xs: 10,
  sm: 12,
  md: 14,
  lg: 16,
  xl: 20,
  '2xl': 24,
  '3xl': 28,
} as const
