import ConnectContent from '../../components/connect/ConnectContent'
import styles from './ConnectView.module.css'

export default function ConnectView() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h2 className={styles.title}>Connect your AI assistant</h2>
        <p className={styles.lede}>
          Use your resumes, applications, accomplishments, notes, and contacts from Claude,
          ChatGPT, or your editor. Three steps, about a minute.
        </p>
      </header>
      <ConnectContent />
    </div>
  )
}
