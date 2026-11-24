import { resolveAppVersion } from '../utils/appVersion'
import { cx } from '../utils/cx'
import { ExternalLink } from './ExternalLink'
import styles from './VersionBadge.module.css'

const APP_VERSION = resolveAppVersion()

/**
 * Page footer with the running release, faint and small: in the page flow, so it is
 * seen only at the bottom of the page. Links to the GitHub release; sha in the tooltip.
 */
export default function VersionBadge({ className }: { className?: string }) {
  const { version, sha, releaseUrl } = APP_VERSION
  const title = sha ? `pktx ${version} (${sha})` : `pktx ${version}`

  return (
    <footer className={cx(styles.footer, className)}>
      <span className={styles.version} title={title}>
        {releaseUrl ? (
          <ExternalLink href={releaseUrl} className={styles.link}>
            {version}
          </ExternalLink>
        ) : (
          version
        )}
      </span>
    </footer>
  )
}
