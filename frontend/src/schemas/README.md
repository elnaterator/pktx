# Schema Conventions

Zod schemas mirror backend Pydantic models. One file per resource. Each exports `xxxCreateSchema`, `xxxUpdateSchema` (`.partial()` of create), and inferred TS types.

## Pydantic → Zod Mapping

| Pydantic constraint | Zod equivalent |
|---|---|
| `Field(..., min_length=1, max_length=200)` | `z.string().trim().min(1).max(200)` |
| `EmailStr` | `z.string().email()` |
| `HttpUrl` (http/https only) | `httpUrl()` from `httpUrl.ts` — `z.string().url()` alone accepts `javascript:` |
| `field_validator("date")` ISO date | `z.string().regex(/^\d{4}-\d{2}-\d{2}$/)` |
| `Optional[str]` empty → None | `z.string().trim().transform((v) => v \|\| undefined).optional()` |
| `Literal["a", "b"]` | `z.enum(['a', 'b'])` |

## Validation Mode Convention

- Multi-field forms: `mode: 'onBlur'` — errors on blur, not on every keystroke.
- Single-field inline forms (e.g., label rename, summary): `mode: 'onChange'` — immediate feedback for a single field.

## Schema Drift

Schemas are hand-mirrored from Pydantic — not generated. When changing backend models, update the corresponding schema file here. The Pydantic → zod table above is the canonical reference. Contract tests at the API boundary catch runtime divergence.
