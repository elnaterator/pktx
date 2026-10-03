const WEB_PROTOCOLS = new Set(['http:', 'https:'])

export interface SafeHrefOptions {
  /** Also accept `mailto:` links. */
  allowMailto?: boolean
}

/**
 * Returns `url` (trimmed) when it is an absolute http(s) URL — or a `mailto:` URL
 * when `allowMailto` is set — and `undefined` otherwise.
 *
 * The protocol is read from WHATWG URL parsing, the same algorithm the browser uses
 * when following the link, so case tricks (`JaVaScRiPt:`), leading whitespace and
 * embedded tabs/newlines (`java\tscript:`) resolve to their real scheme and are
 * rejected. Relative and scheme-less values never parse and are rejected too.
 */
export function safeHref(
  url: string | null | undefined,
  opts: SafeHrefOptions = {},
): string | undefined {
  const value = url?.trim()
  if (!value) return undefined

  let protocol: string
  try {
    protocol = new URL(value).protocol
  } catch {
    return undefined
  }

  if (WEB_PROTOCOLS.has(protocol)) return value
  if (opts.allowMailto && protocol === 'mailto:') return value
  return undefined
}

/** True when `url` parses as an absolute http(s) URL. */
export function isHttpUrl(url: string): boolean {
  return safeHref(url) !== undefined
}
