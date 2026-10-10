import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router'
import { Bot, ChevronLeft, ChevronRight, Maximize2 } from 'lucide-react'
import ConnectContent from './connect/ConnectContent'
import { CopyButton } from './connect/CopyButton'
import { getMcpUrl } from './connect/mcpUrl'
import { useStoredState } from '../hooks/useStoredState'
import styles from './ConnectAssistantPanel.module.css'

export const SEEN_STORAGE_KEY = 'pktx.connect.seen'

const isBoolean = (v: unknown): v is boolean => typeof v === 'boolean'

// The open panel overlays most of a small screen, so only auto-open where it fits.
const roomToAutoOpen = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(min-width: 1024px)').matches === true

export default function ConnectAssistantPanel() {
  const { pathname } = useLocation()
  const [seen, setSeen] = useStoredState(SEEN_STORAGE_KEY, false, isBoolean)
  // Open once for first-time users so the URL and pitch get seen at least once.
  const [open, setOpen] = useState(() => !seen && roomToAutoOpen())

  useEffect(() => {
    if (!seen) setSeen(true)
  }, [seen, setSeen])

  // /connect renders the same content full-page.
  if (pathname === '/connect') return null

  return (
    <aside
      className={`${styles.panel} ${open ? styles.panelOpen : styles.panelClosed}`}
      aria-label="Connect your AI assistant"
    >
      {open ? (
        <div className={styles.shell}>
          <div className={styles.header}>
            <button
              className={styles.collapseBtn}
              onClick={() => setOpen(false)}
              aria-expanded={true}
              aria-label="Collapse AI assistant panel"
            >
              <Bot size={20} aria-hidden="true" />
              <span className={styles.collapseLabel}>Connect your AI assistant</span>
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <Link
              to="/connect"
              className={styles.fullPageLink}
              onClick={() => setOpen(false)}
              aria-label="Open connect page"
              title="Open full page"
            >
              <Maximize2 size={16} aria-hidden="true" />
            </Link>
          </div>
          <div className={styles.body}>
            <ConnectContent />
          </div>
        </div>
      ) : (
        <div className={styles.rail}>
          <button
            className={styles.expandBtn}
            onClick={() => setOpen(true)}
            aria-expanded={false}
            aria-label="Connect your AI assistant"
          >
            <Bot size={28} aria-hidden="true" />
            <span className={styles.expandLabel}>Connect</span>
            <ChevronRight size={18} aria-hidden="true" />
          </button>
          <CopyButton text={getMcpUrl()} label="Copy MCP URL" variant="icon" />
        </div>
      )}
    </aside>
  )
}
