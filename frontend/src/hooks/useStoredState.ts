import { useCallback, useState } from 'react'

/**
 * `useState` backed by localStorage, for per-browser conveniences only (a remembered
 * pick, a dismissed hint). Storage can be missing or throw (private mode, blocked
 * site data), so every access is guarded and the hook degrades to plain state.
 * `isValid` rejects stale or tampered values and falls back to `initial`.
 */
export function useStoredState<T>(
  key: string,
  initial: T,
  isValid: (value: unknown) => value is T,
): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key)
      if (raw === null) return initial
      const parsed: unknown = JSON.parse(raw)
      return isValid(parsed) ? parsed : initial
    } catch {
      return initial
    }
  })

  const set = useCallback(
    (next: T) => {
      setValue(next)
      try {
        window.localStorage.setItem(key, JSON.stringify(next))
      } catch {
        // Storage unavailable — keep the in-memory value.
      }
    },
    [key],
  )

  return [value, set]
}
