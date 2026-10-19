import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { palette } from '../../theme'

// Read from disk: Vitest does not load CSS contents through imports.
const srcDir = join(__dirname, '../..')
const cssFiles: Record<string, string> = Object.fromEntries(
  (readdirSync(srcDir, { recursive: true }) as string[])
    .filter((f) => f.endsWith('.css'))
    .map((f) => [f, readFileSync(join(srcDir, f), 'utf8')]),
)
const tokensCss = cssFiles[join('styles', 'tokens.css')]

function definedProperties(css: string): Set<string> {
  return new Set([...css.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]))
}

describe('design tokens', () => {
  it('theme palette mirrors tokens.css', () => {
    for (const [name, value] of Object.entries(palette)) {
      const match = tokensCss.match(new RegExp(`--${name}:\\s*([^;]+);`))
      expect(match?.[1].trim(), `--${name}`).toBe(value)
    }
  })

  it('every var() used in CSS is defined (or has a fallback)', () => {
    const defined = new Set<string>()
    for (const css of Object.values(cssFiles)) {
      for (const p of definedProperties(css)) defined.add(p)
    }
    const missing: string[] = []
    for (const [file, css] of Object.entries(cssFiles)) {
      for (const m of css.matchAll(/var\(\s*(--[\w-]+)\s*(,)?/g)) {
        if (!m[2] && !defined.has(m[1])) missing.push(`${file}: ${m[1]}`)
      }
    }
    expect(missing).toEqual([])
  })
})
