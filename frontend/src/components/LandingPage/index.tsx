import { SignInButton } from '@clerk/clerk-react'
import { Button } from '../Button'
import styles from './LandingPage.module.css'

export default function LandingPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.logo}>pktx</h1>
      </header>

      <main className={styles.main}>
        <section className={styles.hero}>
          <h2 className={styles.headline}>Your career data, organized.</h2>
          <p className={styles.subheadline}>
            pktx keeps your resumes, job applications, and professional accomplishments in one
            place — ready for your AI assistant to use when you need them most.
          </p>
          <SignInButton mode="modal">
            <Button variant="primary" size="lg" className={styles.cta}>Sign in to get started</Button>
          </SignInButton>
        </section>

        <section className={styles.features}>
          <div className={styles.feature}>
            <div className={styles.featureIcon}>📄</div>
            <h3>Resumes</h3>
            <p>Store and manage multiple resume versions tailored to different roles.</p>
          </div>
          <div className={styles.feature}>
            <div className={styles.featureIcon}>💼</div>
            <h3>Applications</h3>
            <p>Track every job application with status, notes, and contact history.</p>
          </div>
          <div className={styles.feature}>
            <div className={styles.featureIcon}>🏆</div>
            <h3>Accomplishments</h3>
            <p>Log achievements as they happen so you never forget the details.</p>
          </div>
          <div className={styles.feature}>
            <div className={styles.featureIcon}>📝</div>
            <h3>Notes</h3>
            <p>Capture free-form notes with tags — research, prep work, anything you want to recall later.</p>
          </div>
          <div className={styles.feature}>
            <div className={styles.featureIcon}>🤝</div>
            <h3>Contacts</h3>
            <p>Track people you meet during your job search — recruiters, hiring managers, and connections.</p>
          </div>
        </section>
      </main>
    </div>
  )
}
