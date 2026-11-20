// The backend fills this meta tag at serve time so one image runs in every
// environment. `vite dev` serves index.html untouched, so fall back to the
// build-time env var there.
const META_NAME = 'pktx-clerk-publishable-key'

export function resolveClerkPublishableKey(
  doc: Document = document,
  fallback: string | undefined = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY,
): string | undefined {
  const injected = doc.querySelector<HTMLMetaElement>(`meta[name="${META_NAME}"]`)?.content.trim()
  if (injected && !injected.startsWith('%')) return injected
  return fallback || undefined
}
