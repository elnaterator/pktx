import { useCallback, useEffect, useRef, useState } from 'react'
import { useToast } from '../components/toast'

const DONE_MS = 2000

/**
 * Copy text to the clipboard. `copied` is true for two seconds after a
 * successful copy (for a "Copied" state); a failure shows an error toast.
 */
export function useCopyToClipboard() {
  const toast = useToast()
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const copy = useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        clearTimeout(timer.current)
        timer.current = setTimeout(() => setCopied(false), DONE_MS)
      } catch {
        toast.error('Copy failed — select the text and copy it manually.')
      }
    },
    [toast],
  )

  return { copied, copy }
}
