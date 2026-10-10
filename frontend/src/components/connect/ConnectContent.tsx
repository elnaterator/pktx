import { useId, useMemo } from 'react'
import { ArrowUpRight, Download, Sparkles } from 'lucide-react'
import { useStoredState } from '../../hooks/useStoredState'
import { buildAssistants, EXAMPLE_PROMPTS } from './connectAssistants'
import { AssistantPicker } from './AssistantPicker'
import { CopyButton } from './CopyButton'
import { getMcpUrl } from './mcpUrl'
import styles from './Connect.module.css'

export const ASSISTANT_STORAGE_KEY = 'pktx.connect.assistant'

const isString = (v: unknown): v is string => typeof v === 'string'

const verifiedFormat = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})

/** URL hero, example prompts, and per-assistant steps. Shared by the side panel and /connect. */
export default function ConnectContent() {
  const uid = useId()
  const mcpUrl = getMcpUrl()
  const assistants = useMemo(() => buildAssistants(mcpUrl), [mcpUrl])
  const [storedId, setStoredId] = useStoredState(ASSISTANT_STORAGE_KEY, assistants[0].id, isString)
  const assistant = assistants.find((a) => a.id === storedId) ?? assistants[0]

  return (
    <div className={styles.content}>
      <section className={styles.hero} aria-labelledby={`${uid}-url`}>
        <h3 className={styles.eyebrow} id={`${uid}-url`}>
          Your MCP server URL
        </h3>
        <div className={styles.urlRow}>
          <code className={styles.url}>{mcpUrl}</code>
          <CopyButton text={mcpUrl} label="Copy MCP URL" />
        </div>
        <p className={styles.heroHint}>
          Paste it into any assistant that speaks MCP. Sign-in happens in your browser — no API
          key to manage.
        </p>
      </section>

      <section className={styles.pitch} aria-labelledby={`${uid}-prompts`}>
        <h3 className={styles.sectionTitle} id={`${uid}-prompts`}>
          <Sparkles size={16} aria-hidden="true" />
          Then just ask
        </h3>
        <ul className={styles.prompts}>
          {EXAMPLE_PROMPTS.map((prompt) => (
            <li key={prompt} className={styles.prompt}>
              <span className={styles.promptText}>&ldquo;{prompt}&rdquo;</span>
              <CopyButton text={prompt} label={`Copy prompt: ${prompt}`} variant="icon" />
            </li>
          ))}
        </ul>
        <p className={styles.callout}>
          Your assistant can <strong>read and write</strong> — it looks things up, and it can log
          an application, add an accomplishment, or update a note when you ask.
        </p>
      </section>

      <section className={styles.setup} aria-labelledby={`${uid}-setup`}>
        <h3 className={styles.sectionTitle} id={`${uid}-setup`}>
          Set it up
        </h3>
        <AssistantPicker
          assistants={assistants}
          value={assistant.id}
          onChange={setStoredId}
          label="Assistant"
        />

        <div className={styles.card}>
          <p className={styles.nounLine}>
            {assistant.name} calls this {assistant.noun === 'MCP server' ? 'an' : 'a'}{' '}
            <span className={styles.noun}>{assistant.noun}</span>
          </p>

          <ol className={styles.steps}>
            {assistant.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>

          {assistant.install && (
            <a className={styles.installBtn} href={assistant.install.url}>
              <Download size={16} aria-hidden="true" />
              {assistant.install.label}
            </a>
          )}

          {assistant.snippet && (
            <div className={styles.snippet}>
              <div className={styles.snippetHeader}>
                <span className={styles.snippetLabel}>{assistant.snippet.label}</span>
                <CopyButton text={assistant.snippet.text} label={`Copy ${assistant.name} config`} />
              </div>
              <pre className={styles.code}>{assistant.snippet.text}</pre>
            </div>
          )}

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
              <ArrowUpRight size={12} aria-hidden="true" />
            </a>
          </p>
        </div>

        <p className={styles.testHint}>
          Test it: ask &ldquo;list my resumes&rdquo;. Real data back means you&rsquo;re connected.
        </p>
      </section>
    </div>
  )
}
