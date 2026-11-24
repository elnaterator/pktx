// The backend fills these meta tags at serve time: the version is deploy-time
// config (release tag in prod, dev-<sha> in dev), the sha is baked into the image.
// `vite dev` serves index.html untouched, so unfilled placeholders mean `local`.
const RELEASES_URL = 'https://github.com/elnaterator/pktx/releases/tag/'

export interface AppVersion {
  /** `vYYYY.MM.DD[.N]`, `dev-<sha>`, or `local`. */
  version: string
  /** Full git sha of the image, or '' when unknown. */
  sha: string
  /** GitHub release page for release versions, else undefined. */
  releaseUrl?: string
}

function meta(doc: Document, name: string): string {
  const value = doc.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)?.content.trim() ?? ''
  return value.startsWith('%') ? '' : value
}

export function resolveAppVersion(doc: Document = document): AppVersion {
  const version = meta(doc, 'pktx-version') || 'local'
  const sha = meta(doc, 'pktx-git-sha')
  const releaseUrl = /^v\d+(\.\d+)*$/.test(version) ? `${RELEASES_URL}${version}` : undefined
  return { version, sha, releaseUrl }
}
