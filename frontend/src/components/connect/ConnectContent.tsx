import { useId, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import { ArrowUpRight, ChevronDown, Download } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { useStoredState } from '../../hooks/useStoredState'
import { cx } from '../../utils/cx'
import { buildAssistants, SERVER_NAME, type Assistant } from './connectAssistants'
import { AssistantIcon } from './AssistantIcon'
import { CopyButton } from './CopyButton'
import { getMcpUrl } from './mcpUrl'
import styles from './Connect.module.css'

export const ASSISTANT_STORAGE_KEY = 'pktx.connect.assistant'

/** The one prompt that proves the connection works. */
export const TEST_PROMPT = 'List my resumes'

const isString = (v: unknown): v is string => typeof v === 'string'

const verifiedFormat = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})

/**
 * Three-step connect flow: choose an assistant, add pktx to it, try it.
 * The choice is remembered and reflected in `?assistant=` so it can be linked.
 */
export default function ConnectContent() {
  const uid = useId()
  const mcpUrl = getMcpUrl()
  const assistants = useMemo(() => buildAssistants(mcpUrl), [mcpUrl])
  const [searchParams, setSearchParams] = useSearchParams()
  const [storedId, setStoredId] = useStoredState(ASSISTANT_STORAGE_KEY, assistants[0].id, isString)

  const byId = (id: string | null) => assistants.find((a) => a.id === id)
  const assistant = byId(searchParams.get('assistant')) ?? byId(storedId) ?? assistants[0]

  const choose = (id: string) => {
    setStoredId(id)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('assistant', id)
        return next
      },
      { replace: true },
    )
  }

  return (
    <ol className={styles.flow}>
      <Step n={1} title="Choose your assistant" id={`${uid}-choose`}>
        <AssistantTiles assistants={assistants} value={assistant.id} onChange={choose} labelledBy={`${uid}-choose`} />
      </Step>

      <Step n={2} title={`Add ${SERVER_NAME} to ${assistant.name}`} id={`${uid}-add`}>
        {assistant.install && (
          <a className={styles.installBtn} href={assistant.install.url}>
            <Download size={ICON_SIZE.lg} aria-hidden="true" />
            {assistant.install.label}
          </a>
        )}
        <ol className={styles.steps}>
          {assistant.steps.map((step) => (
            <li key={step}>
              {step}
              {/* The URL sits where you paste it, not in a separate block. */}
              {step.includes('MCP URL') && <UrlChip url={mcpUrl} />}
            </li>
          ))}
        </ol>
        {assistant.snippet?.inSetup && <Snippet assistant={assistant} />}
      </Step>

      <Step n={3} title="Try it" id={`${uid}-try`}>
        <div className={styles.tryRow}>
          <span className={styles.tryLabel}>Ask {assistant.name}:</span>
          <span className={styles.chip}>
            <span className={styles.chipText}>&ldquo;{TEST_PROMPT}&rdquo;</span>
            <CopyButton text={TEST_PROMPT} label="Copy test prompt" variant="icon" />
          </span>
        </div>
        <p className={styles.hint}>Real data back means you&rsquo;re connected.</p>
      </Step>

      <li className={styles.detailsItem}>
        <Details assistant={assistant} mcpUrl={mcpUrl} />
      </li>
    </ol>
  )
}

function Step({ n, title, id, children }: { n: number; title: string; id: string; children: ReactNode }) {
  return (
    <li className={styles.step}>
      <span className={styles.stepNumber} aria-hidden="true">{n}</span>
      <div className={styles.stepBody}>
        <h3 className={styles.stepTitle} id={id}>{title}</h3>
        {children}
      </div>
    </li>
  )
}

function UrlChip({ url }: { url: string }) {
  return (
    <span className={cx(styles.chip, styles.urlChip)}>
      <code className={styles.chipText}>{url}</code>
      <CopyButton text={url} label="Copy MCP URL" variant="icon" />
    </span>
  )
}

function Snippet({ assistant }: { assistant: Assistant }) {
  if (!assistant.snippet) return null
  return (
    <div className={styles.snippet}>
      <div className={styles.snippetHeader}>
        <span className={styles.snippetLabel}>{assistant.snippet.label}</span>
        <CopyButton text={assistant.snippet.text} label={`Copy ${assistant.name} config`} />
      </div>
      <pre className={styles.code}>{assistant.snippet.text}</pre>
    </div>
  )
}

interface AssistantTilesProps {
  assistants: Assistant[]
  value: string
  onChange: (id: string) => void
  labelledBy: string
}

/** Radio-style tiles: common assistants up front, the rest behind "More". */
function AssistantTiles({ assistants, value, onChange, labelledBy }: AssistantTilesProps) {
  const featured = assistants.filter((a) => a.featured)
  const others = assistants.filter((a) => !a.featured)
  const selectedIsOther = others.some((a) => a.id === value)
  const [showMore, setShowMore] = useState(selectedIsOther)
  const visible = showMore || selectedIsOther ? assistants : featured

  return (
    <div className={styles.tilesWrap}>
      <div className={styles.tiles} role="radiogroup" aria-labelledby={labelledBy}>
        {visible.map((a) => (
          <button
            key={a.id}
            type="button"
            role="radio"
            aria-checked={a.id === value}
            className={cx(styles.tile, a.id === value && styles.tileSelected)}
            onClick={() => onChange(a.id)}
          >
            <AssistantIcon id={a.id} size={20} />
            <span>{a.name}</span>
          </button>
        ))}
      </div>
      {!selectedIsOther && others.length > 0 && (
        <button
          type="button"
          className={styles.moreBtn}
          aria-expanded={showMore}
          onClick={() => setShowMore((v) => !v)}
        >
          {showMore ? 'Fewer assistants' : `More: ${others.map((a) => a.name).join(', ')}`}
          <ChevronDown size={ICON_SIZE.sm} aria-hidden="true" className={cx(showMore && styles.flip)} />
        </button>
      )}
    </div>
  )
}

function Details({ assistant, mcpUrl }: { assistant: Assistant; mcpUrl: string }) {
  return (
    <details className={styles.details}>
      <summary className={styles.summary}>
        Details for {assistant.name}
        <ChevronDown size={ICON_SIZE.sm} aria-hidden="true" className={styles.summaryIcon} />
      </summary>
      <div className={styles.detailsBody}>
        <p className={styles.nounLine}>
          {assistant.name} calls this {assistant.noun === 'MCP server' ? 'an' : 'a'}{' '}
          <span className={styles.noun}>{assistant.noun}</span>. Sign-in happens in your browser —
          no API key to manage.
        </p>
        <div className={styles.urlLine}>
          <span className={styles.hint}>MCP URL</span>
          <UrlChip url={mcpUrl} />
        </div>
        {assistant.snippet && !assistant.snippet.inSetup && <Snippet assistant={assistant} />}
        {assistant.notes && (
          <ul className={styles.notes}>
            {assistant.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        )}
        <p className={styles.verified}>
          Verified {verifiedFormat.format(new Date(`${assistant.lastVerified}T00:00:00Z`))} ·{' '}
          <a href={assistant.docsUrl} target="_blank" rel="noopener noreferrer">
            {assistant.name} docs
            <ArrowUpRight size={ICON_SIZE.sm} aria-hidden="true" />
          </a>
        </p>
      </div>
    </details>
  )
}
