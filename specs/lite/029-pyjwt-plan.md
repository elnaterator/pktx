---
roadmap_id: 029
issue: n/a
---

# Plan: 029 Replace python-jose with PyJWT

## Overview

python-jose barely maintained; pulls `ecdsa` (unfixed timing side channel PYSEC-2026-1325, waived in 028 until 2027-01-01), `rsa`, `pyasn1`. PyJWT[crypto] already installed via `mcp[crypto]`. Port REST JWT verification + test token helpers to PyJWT, drop python-jose + waiver. Auth-sensitive → standalone PR, behavior unchanged.

- `auth.py`: header parse, JWKS key → `jwt.PyJWK`, `jwt.decode` (RS256, issuer, no aud), unverified claims for rejection logging, error mapping (`ExpiredSignatureError` → "Token has expired", other `PyJWTError` → generic 401).
- Tests: replace `jose.backends.RSAKey` JWK builders + `jose.jwt.encode` in `tests/helpers.py`, `unit/test_auth.py`, `contract/test_auth_contract.py`, `integration/test_multi_user.py`.
- Deps: remove `python-jose[cryptography]`, add explicit `pyjwt[crypto]` (direct import → direct dep), relock; `ecdsa`/`rsa`/`pyasn1` gone from lock unless another dep needs them.
- Makefile: drop `PIP_AUDIT_IGNORE` PYSEC-2026-1325 (+ comment).

## Acceptance criteria

- [x] No `jose` import anywhere in `backend/` (src + tests); `python-jose` absent from `pyproject.toml` and `uv.lock`.
- [x] `pyjwt[crypto]` declared directly in `pyproject.toml`.
- [x] `ecdsa`, `rsa`, `pyasn1` absent from `uv.lock`.
- [x] `PIP_AUDIT_IGNORE` waiver for PYSEC-2026-1325 removed; `make audit` passes.
- [x] REST auth behavior identical: valid token → claims; expired → 401 "Token has expired"; bad sig / bad header / wrong iss / unknown kid / missing sub / bad azp → 401 generic. Existing auth tests pass unchanged in intent.
- [x] `jwt.decode` pins `algorithms=["RS256"]` (no alg confusion; `none` rejected) — covered by a test.
- [x] Non-RSA / malformed JWK in cache → 401, not 500.
- [x] `cd backend && make check` + `uv run pyright` green; root `make check` green.
- [x] AGENTS.md tech list updated (python-jose → PyJWT).

## Design

PyJWT mapping:

| python-jose | PyJWT |
|---|---|
| `jwt.get_unverified_header` | `jwt.get_unverified_header` |
| `jwt.get_unverified_claims(t)` | `jwt.decode(t, options={"verify_signature": False})` |
| `jwt.decode(t, jwk_dict, ...)` | `jwt.decode(t, jwt.PyJWK(jwk_dict).key, algorithms=["RS256"], issuer=..., options={"verify_aud": False})` |
| `JWTError` | `jwt.PyJWTError` (+ `jwt.PyJWKError` for bad JWK) |
| `ExpiredSignatureError` | `jwt.ExpiredSignatureError` |
| `RSAKey(pem).to_dict()` (tests) | `json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(pub_key))` + `kid`/`alg`/`use` |

Notes:
- PyJWT requires `sub` to be string if present, `iat` numeric, etc. — fine for Clerk tokens. Keep explicit `sub` presence check.
- PyJWT `get_unverified_header` raises `DecodeError` (subclass of `PyJWTError`) — same mapping.
- Keep JWK cache storing raw dicts; build `PyJWK` per verify (cheap) — keep cache shape, minimal diff. Catch `PyJWKError` → 401.
- `test_auth_contract.py:772` uses `joserfc` (FastMCP's dep) — unrelated, leave.
- Leeway: python-jose default 0; PyJWT default 0. Same.
- PyJWT (≥2.10) also rejects `iat` in the future; python-jose did not. Disabled via `verify_iat: False` so Clerk tokens don't 401 on clock skew (found in review; covered by `test_iat_slightly_in_future_accepted`).

**Touches:**
- `backend/src/pktx/auth.py` (mod)
- `backend/pyproject.toml`, `backend/uv.lock` (mod)
- `backend/Makefile` (mod — waiver)
- `backend/tests/helpers.py`, `backend/tests/unit/test_auth.py`, `backend/tests/contract/test_auth_contract.py`, `backend/tests/integration/test_multi_user.py` (mod)
- `AGENTS.md` (mod)

## Steps

- [x] Swap deps: `uv remove python-jose && uv add 'pyjwt[crypto]>=2.10'`; check lock for `ecdsa`/`rsa`/`pyasn1`.
- [x] Port `auth.py` imports, decode, header/claims, error mapping, PyJWK handling.
- [x] Port test JWK/token helpers in place (`RSAAlgorithm.to_jwk(..., as_dict=True)`); dedupe of per-file copies left out to keep the auth PR minimal.
- [x] Add tests: `alg=none` / HS256 token rejected; malformed JWK → 401.
- [x] Drop Makefile waiver; update AGENTS.md.
- [x] Run `make check` (backend + root).

## Testing

```bash
cd backend && make check && uv run pyright
grep -rn "jose" backend/src backend/tests backend/pyproject.toml | grep -v joserfc
grep -n 'name = "ecdsa"\|name = "python-jose"' backend/uv.lock
make check
```

## Out of scope

- Moving REST auth onto FastMCP/joserfc verifiers.
- Changing JWKS cache/throttle logic, azp semantics, or MCP OAuth proxy.
