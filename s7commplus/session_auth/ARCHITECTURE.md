# session_auth — S7CommPlus Session Authentication

Python port of [bonk-dev/HarpoS7](https://github.com/bonk-dev/HarpoS7) (MIT),
which is a clean-room re-implementation of the proprietary authentication in
Siemens' `OMSp_core_managed.dll`.

## When is this needed?

V1-initial S7-1200 PLCs (FW < V4.5, no TLS) require a **SessionKey handshake**
in the SetupSession step before they accept data operations. Without it, the PLC
returns an incomplete session and rejects all S7CommPlus requests.

Newer PLCs (V2/V3/TLS) use standard TLS certificates instead and do not need
any of this machinery.

## Authentication flow

```
PLC                                          Client
 │                                              │
 │◄──── CreateObject ───────────────────────────│  V1 framing
 │ response: session_id, public_key_fingerprint │
 │           session_challenge (20 bytes)        │
 │           ServerSessionVersion (Struct 314)   │
 │                                              │
 │  ┌─ Client-side (no network) ──────────────┐ │
 │  │ 1. Look up PLC's public key by          │ │
 │  │    fingerprint (keys.py)                 │ │
 │  │ 2. Generate random key1 (24B), key2     │ │
 │  │    (24B), IV (16B)                       │ │
 │  │ 3. Run Family-0 transforms to produce   │ │
 │  │    180-byte SecurityKeyEncryptedKey blob │ │
 │  │ 4. Derive 24-byte session_key via       │ │
 │  │    HMAC-SHA256(key2[:24], 8-byte         │ │
 │  │    challenge fingerprint ||             │ │
 │  │    challenge[2:18])                     │ │
 │  └─────────────────────────────────────────┘ │
 │                                              │
 │◄──── SetupSession ───────────────────────────│  V2 framing
 │  SecurityKey blob (addr 1830)                │
 │  + ServerSessionVersion echo (addr 306)      │
 │                                              │
 │──── response: success ──────────────────────►│
 │                                              │
 │  ══ V3+HMAC framing enabled ═════════════    │
 │                                              │
 │◄──── SET_VARIABLE addr 323 ──────────────────│  session activation
 │◄──── GET_VAR_SUB addr 303 (challenge) ───────│  legitimation, even
 │◄──── SET_VAR_SUB addr 1846 (solved blob) ────│  with empty password
 │                                              │
 │  ══ data operations now work ════════════    │
```

After SetupSession, all data frames use **V3 framing** with HMAC-SHA256
(keyed by the first 24 bytes of the session key). No intermediate
activation sequence is needed — data reads work immediately.

Legacy SessionKeys are renewed every 25 minutes by default, before the PLC's
key expiry window. Renewal reads a fresh challenge from address 303 and writes
a new SecurityKey to address 1830 while holding the same lock as application
requests. The PLC's response is authenticated with the old key; the new key is
installed only after that response is verified and accepted. A renewal failure
closes the connection instead of continuing with an expired or ambiguous key.

The interval is configurable in seconds through
`S7CommPlusClient.connect(legacy_session_key_refresh_interval=...)` (or the
low-level connection method). Pass `None` to disable automatic renewal. This
timer applies only to legacy V1-initial SessionKey sessions; TLS sessions do not
start it.

The synchronous connection path currently sends SET_VARIABLE address 323 and
then performs post-auth legitimation, even when no password was supplied. Do
not remove these operations on the strength of older traces or the HarpoS7
reference alone: this is the actual implemented handshake and requires
hardware validation before wire-behavior changes. The asyncio client does not
support this legacy SessionKey path.

## Contributor path through the handwritten code

The stable entry point is `S7CommPlusConnection.connect()` in
`s7commplus/connection.py`. Its CreateObject parser saves the session challenge,
public-key fingerprint, and ServerSessionVersion. `_setup_session()` calls
`_try_session_key_auth()` only for non-TLS V1 sessions with both challenge and
fingerprint; `keys.parse_fingerprint()` and `keys.get_public_key()` select the
bundled key. A family-only fingerprint requires an explicit candidate from the
discovery path rather than silently trying all keys.

`legacy_auth.authenticate_real_plc()` is the small cryptographic boundary: it
returns a 180-byte encrypted blob and a 24-byte session key. It delegates blob
construction to `family0/authenticator.py` and key derivation to
`key_derivation.py`. `_encode_security_key_struct()` owns the wire-level
SecurityKey wrapper; `_setup_session()` writes it at address 1830 alongside the
ServerSessionVersion echo at address 306 (with the V1-rejected PAOM string
removed). Only an accepted response
installs `_session_key` and enables IntegrityId tracking. `send_request()` and
the response/fragments readers then own V3 HMAC framing and verification.

After setup, `_session_activate()` sends address 323, and
`_post_auth_legitimation()` reads a *new* challenge at address 303 and writes
the 248-byte result to address 1846. The solver is
`legitimate.solve_legitimate_challenge_real_plc()`. The CreateObject challenge
must never substitute for a failed legitimation read. Renewal is handled by
`_renew_session_key_locked()`: it reads a fresh address-303 challenge and writes
another SecurityKey under the application-request lock. The old key verifies
the response before the new key is installed.

For a new real-PLC key family, add key selection and an authenticator parallel
to `family0/authenticator.py`, then extend the handwritten dispatch in
`legacy_auth.py` and its explicit tests. Do not import `_generated` in the
connection layer, edit transpiled output to fix handshake behavior, or silently
map an unknown family to Family 0. This is a recommended extension boundary,
not a claim that a pluggable authenticator interface already exists.

### Diagnosing a failed connection

- Missing ServerSessionVersion: inspect CreateObject attribute parsing before
  any crypto; SetupSession cannot proceed without an echoable typed value.
- Missing challenge or fingerprint: `_try_session_key_auth()` skips the legacy
  path. Compare the PLC's reported family, firmware, and captured attributes;
  do not infer a bad cryptographic transform from the skipped path.
- Unknown full fingerprint or family-only identifier: check `keys.py` and the
  discovery candidate. A candidate rejected by SetupSession is not proof that
  the bundled key or transform is correct for that PLC.
- Blob generated but SetupSession rejected: compare the 1830/306 request layout,
  public-key family, and PLC response return value before entering monoliths.
- Setup accepted but later request rejected: distinguish activation,
  legitimation, IntegrityId, V3 frame/HMAC, and fragmented-response verification.
  The address-303 challenge is distinct from the CreateObject challenge.
- Renewal failure: the connection is closed intentionally; check the fresh
  challenge read, authenticated SecurityKey write, and PLC expiry behavior.

Do not attach raw packet captures or debug logs containing challenges, session
keys, passwords, or private material to public issues. The real-PLC acceptance
guide describes the shareable artifact workflow.

## Module map

### Orchestration (human-readable)

```
session_auth/
├── __init__.py              Public API re-exports
├── ARCHITECTURE.md          This file
├── keys.py                  Public-key store (fingerprint → 40/64-byte key)
├── key_derivation.py        SHA-256 KDFs (challenge key, seed key+IV, session key)
├── legitimate.py            Post-auth challenge solver (DEADBEEF blob builder)
├── blob_metadata.py         SecurityKeyEncryptedKey blob header/metadata
├── harpo_aes.py             AES-ECB primitives (used by checksum + seed encryption)
├── harpo_aes_ctr.py         Custom AES-CTR mode (non-standard counter increment)
├── harpo_hash.py            SHA-256-based hash with LUT mixing
├── utils.py                 Key-ID derivation (SHA-256 → 8 bytes)
│
├── family0/
│   ├── __init__.py
│   ├── authenticator.py     RealPlcAuthenticator — top-level blob builder
│   ├── fingerprint.py       8-byte challenge fingerprint (LUT + mutation chain)
│   ├── seed_transform.py    Encrypted seed generation (monolith chain)
│   ├── pre_seed_transform.py  Random key → pre-seed via Monolith9
│   ├── key_derivation_transform.py  Pre-seed → 3 AES keys via Monolith9/10
│   ├── checksum_transform.py  AES-ECB checksum of encrypted blocks
│   ├── lut_generator.py     Lookup table for harpo_hash
│   ├── transform7.py        Core EC point multiplication (monolith wrappers)
│   ├── transform12.py       Opcode-driven BigInt dispatcher
│   ├── transform13.py       3×24-byte BigInt output via Monolith9/10
│   ├── big_int_operations.py  192-bit arithmetic (add, sub, mul, square)
│   ├── big_int_transforms.py  BigInt higher-level ops
│   └── monolith_wrappers.py  WithCopy adapters for Monolith3-7
```

### Machine-transpiled (do not edit)

```
│   └── _generated/
│       ├── __init__.py
│       ├── monolith1.py … monolith11.py   Permutation ciphers (~30K lines)
│       ├── nine/part1.py … part11.py      Monolith9 parts (~50K lines)
│       ├── ten/part1.py … part3.py        Monolith10 parts (~15K lines)
│       └── data/
│           ├── __init__.py                Binary data loaders
│           ├── _constants.py              Python constant arrays
│           ├── fp_data1.bin, fp_data2.bin  Fingerprint lookup tables
│           ├── transform12_metadata.bin   Transform12 opcode tape
│           └── transform12_big_int_data.bin  BigInt constant table
```

The `_generated/` modules are transpiled from HarpoS7's C# via
`tools/transpile_harpo_monolith.py`. Each `monolithN.execute(dst, src)` is a
straight-line uint32 arithmetic function verified byte-for-byte against upstream
test vectors. They implement a proprietary permutation cipher and cannot be
meaningfully simplified — the algorithm is designed to resist analysis.

## Artifact provenance and verification

[`artifacts.json`](artifacts.json) is the authoritative inventory for every
generated Python module and binary runtime table. It pins HarpoS7 v1.1.0 to
commit `b4ba7fab14bcca4274e69a4d6524a5a61fcd329d` and records each artifact's
classification, upstream source, generation method, byte size, and SHA-256.
The original MIT license is in `LICENSE-HarpoS7`.

Run the complete deterministic check from the repository root:

```bash
python tools/verify_session_auth_artifacts.py
```

The command fails on a missing, changed, or newly unmanifested artifact and is
also run by pre-commit CI. The monolith source can be regenerated one file at a
time with `tools/transpile_harpo_monolith.py`. The constant and binary extraction
tooling used for the initial port is not yet vendored, so their pinned sizes and
hashes are the authoritative reproducibility check; do not claim regeneration
for those files until that tooling is added.

### Review boundary

- Human-maintained flow and extension points live outside `_generated/`.
- `monolith*.py`, `nine/part*.py`, and `ten/part*.py` are generated source.
- `_constants.py` and the four `.bin` files are generated data.
- Package `__init__.py` files and the binary loaders are human-maintained glue.

When generated output intentionally changes, keep that mechanical diff separate
from handwritten behavior changes where practical. Regenerate from the pinned
upstream revision, run the upstream-derived vector tests, then update the size
and SHA-256 in `artifacts.json` in the same generated-output commit. Adding a new
key family should start with a small authenticator interface parallel to
`family0/authenticator.py`; callers should never import generated monoliths
directly.

## How the blob is built (authenticator.py)

```
RealPlcAuthenticator(key1=random_24B, key2=random_24B)
│
├── write_seed(dst, public_key)
│   ├── PreSeedTransform(key1)           →  60-byte pre-seed
│   ├── KeyDerivationTransform(pre-seed) →  3 × 16-byte keys
│   ├── SeedTransform(key1, public_key)  →  60-byte encrypted seed
│   │   ├── Transform7 (EC scalar mul)
│   │   ├── Monolith1.Loop → Monolith2 → Monolith8
│   │   └── Transform13 → Monolith11
│   └── AES-ECB encrypt seed with derived key
│
├── encrypt_full_blocks(dst, challenge)
│   └── HarpoAesCtr(challenge_key, key2[:16])
│       └── AES-CTR encrypt challenge blocks + checksum
│
└── encrypt_final_block(dst)
    └── HarpoAesCtr final block + PKCS-style padding
```

## References

- [HarpoS7](https://github.com/bonk-dev/HarpoS7) — MIT, C# clean-room implementation
- [lircy/S7CommPlusV3Driver](https://github.com/lircy/S7CommPlusV3Driver) — ships HarpoS7 as precompiled native DLLs
- Cheng Lei et al., "The Spear to Break the Security Wall of S7CommPlus", Black Hat EU 2017
- Biham, Bitan et al., "Rogue7: Rogue Engineering Station Attacks on S7 Simatic PLCs", Black Hat USA 2019
