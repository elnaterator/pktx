import type { ReactNode } from 'react'
import { safeHref } from '../utils/safeUrl'

interface ExternalLinkProps {
  /** User-controlled URL. Only http(s) (and mailto, if allowed) become a link. */
  href: string | null | undefined
  className?: string
  children: ReactNode
  allowMailto?: boolean
}

/**
 * Link for user/agent-supplied URLs. Unsafe or unparseable URLs (e.g. `javascript:`)
 * render as plain text in a `<span>` with the same className, so layout is unchanged
 * but nothing is clickable.
 */
export function ExternalLink({ href, className, children, allowMailto }: ExternalLinkProps) {
  const safe = safeHref(href, { allowMailto })
  if (!safe) return <span className={className}>{children}</span>

  // mailto: hands off to the mail client; opening a blank tab for it is just noise.
  const newTab = !/^mailto:/i.test(safe)
  return (
    <a
      href={safe}
      className={className}
      {...(newTab && { target: '_blank', rel: 'noopener noreferrer' })}
    >
      {children}
    </a>
  )
}
