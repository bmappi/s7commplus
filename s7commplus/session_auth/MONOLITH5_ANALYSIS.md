# Monolith5: recovered compact Boolean model

This is an exact compact model of the pinned, generated Family-0 Monolith5,
not a runtime replacement or a claim about every proprietary DLL version.
Source and destination are little-endian 32-bit words, numbered from zero.

Monolith5 consumes 54 source words and produces 12 output words. Its generated
body is mostly bitwise logic, but unlike Monolith11 it contains fixed shifts
and multiplications by two. The bitwise-only truth-table method therefore does
not apply directly. `tools/trace_session_auth_bits.py` follows every output
bit through the versioned backward slice, including constant masks, logical
right shifts, left shifts, and power-of-two multiplication modulo 2³².

## Recovered formula

The 12 output words form two streams, each with six 28-bit payload limbs.
Payload bits occupy word bits 2–29; word bits 0, 1, 30, and 31 are always zero.
Let `A[t]` be the first stream's payload bits and `B[t]` the second stream's,
for `t = 0..167`. The first bit of the second stream is always zero: `B[0]=0`.

An input bit lane is a nine-bit vector: for source triplet `c` (0–5) and bit
position `p` (0–31), take bit `p` of source words `18*s + 3*c + j`, with span
`s = 0..2` and member `j = 0..2`. Place those nine bits at positions `3*s+j`
of the vector. Call one of the 32 recovered nine-input truth-table functions
on this vector `F_k(c,p)`.

Each position record selects two or three such lane functions `f₀, f₁, …`
and a constant `a`. The exact two-output formula is:

```text
A[t]   = a XOR f₀ XOR f₁ [XOR f₂]
B[t+1] = r XOR XOR { product(f_j for j in S) : S selected by mask }
```

Here `r` is zero except for the first position, where one extra nine-input
lane function supplies a boundary correction. A product is Boolean AND; the
empty product is one. No selected term contains all three functions, so the
second stream is at most quadratic in these lane functions. The 32 truth
tables, 168 position records, and masks are in
`tools/monolith5_model.json`; `tools/monolith5_model.py` evaluates this formula.
Both are analysis-only and leave the generated runtime code unchanged.
Every recovered lane function is symmetric under permutation of the three
72-byte input spans; the test suite checks all 512 inputs and all six span
permutations for every truth table.

## Named gates and span structure

The nine-input functions have a second, more readable exact decomposition.
Every function applies the **same three-input gate** independently to each
input span and then combines the three results:

```text
s0 = g(x0, x1, x2)
s1 = g(x3, x4, x5)
s2 = g(x6, x7, x8)
F_k = h(s0, s1, s2)
```

The gate `g` is conditional selection (`choose`) or `majority`, with fixed
argument permutations and input inversions. Its normalized value at `000`
is zero. Under that normalization, exhaustive search finds exactly one
complete decomposition for each of the 32 functions. The symmetric combine
`h` belongs to four familiar operations:

| Combine | Exact formula | Number of lane functions |
| --- | --- | --- |
| XOR of three | `a XOR b XOR c` | 15 |
| Majority | `(a AND b) XOR (a AND c) XOR (b AND c)` | 15 |
| OR of three | `a OR b OR c` | 1 |
| Not all equal | `(a OR b OR c) XOR (a AND b AND c)` | 1 |

Here `choose(a,b,c) = b XOR ((a XOR b) AND c)`. For example, lane
function zero uses `choose(x0,x1,x2)` in each span and `not_all_equal`
to combine the three results. This structure explains the previously observed
symmetry under permutation of whole input spans. It does not by itself identify
the proprietary algorithm or establish a cryptographic interpretation.

`tools/recover_monolith5_gates.py` checks all 512 rows for every candidate
decomposition and recognizes the local gates through the shared Boolean
decomposition machinery. The saved `tools/monolith5_gate_model.json` contains
32 gate records. The evaluator `tools/monolith5_gate_model.py` applies each
gate to entire uint32 words, evaluating 32 bit lanes together; it reuses the
existing 168 position records to reconstruct all twelve output words.
The exhaustive tests compare all 16,384 lane-function truth rows with the
original LUTs, in addition to the known-answer vector and comparisons against
the generated implementation on structured, single-bit, and random inputs.

```bash
python -m tools.recover_monolith5_gates --formula 0
python -m tools.recover_monolith5_gates --verify tools/monolith5_gate_model.json
```

## Exact additive span identity

`tools/recover_monolith5_span_decoder.py` derives an additive interpretation of
the two raw streams directly from the recovered position and named-gate models.
Let A and B be their six-lane 168-bit payload integers, p = 2^160 - 47,
and s0, s1, s2 the three eighteen-word input spans. Then:

```text
A + B = C + D(s0) + D(s1) + D(s2) - p * majority(b0,b1,b2) (mod 2^168)
C = 51698806077986350461380052348415547004375582574557
bi = choose(si.word0_bit0, si.word1_bit0, si.word2_bit0)
```

D is a reusable sum of 169 signed, weighted local choose/majority gates. The
tool prints their complete coefficients with `python -m
tools.recover_monolith5_span_decoder`. No interpolation or chosen-input fitting
is used: integer truth-table transforms check every interior output pair;
`xor3 + 2*majority = sum` cancels their interactions. The first-position identity
`2*or3 - not_all_equal = sum - majority` leaves the explicit -p correction.
Top-position XOR interactions vanish modulo 2^168.

Tests check the known-answer vector, 1,000 seeded arbitrary-word inputs,
structured and single-bit inputs, and all boundary configurations with span
permutations against generated Monolith5. The derivation is exact relative to
the existing symbolically recovered gate/position models, not merely a sampled
identity.

This is **not yet a field decoder**: reducing a 168-bit sum before reducing
modulo p discards a multiple of 2^168, which is not zero modulo p. The identity
also does not determine A and B separately, so it cannot replace the exact
setup merge or its carry correction. Earlier Monolith3/4/6 encoded-span
identities still need source-derived proofs on their valid encoding domain.

## Binary normalization and Monolith4 carry investigation

The recovered decoder admits a further exact normalization, checked directly
from all 169 coefficients in `tools/recover_monolith4_span_identity.py`.
Its boundary gate h has weight H=(p+1)/2. Each of its other 168 gates has a
distinct weight +2^k or -2^k, k=0..167. Complement every negative-weight gate
to obtain an ordinary unsigned binary payload B. If n is the sum of the
negative weights, D=n+B+H*h and the recovered constant C is exactly -3*n.
Consequently the candidate field shadow is V=B+H*h modulo p, with no fitted
offset. These normalization statements are exact integer algebra, before any
modular reduction.

Substituting this into the already recovered exact Monolith5 identity gives:

```text
A+B = B0+B1+B2 + H*parity(h0,h1,h2) + majority(h0,h1,h2) (mod 2^168)
```

This uses 2H=p+1, so H*sum(h)-p*majority(h) becomes
H*parity(h)+majority(h). It is an exact reformulation of the symbolic model,
not interpolation. It still does not recover the two streams separately.

For Monolith4, the resulting full-addition **candidate** is:

```text
T = B0+B1+(h0 & h1)
B_out = T mod 2^168
h_out = h0 XOR h1
overflow = T >= 2^168
V(out)-V(in0)-V(in1) = -12032*overflow (mod p)
```

The last equation follows algebraically from the candidate: the boundary
contributes -p*(h0 & h1), which vanishes modulo p, while a discarded carry
contributes -2^168, congruent to -12032. All 1,000 seeded arbitrary raw-span
tests match the complete candidate and both overflow branches. Thus it explains
the previous negative control, but sampling does not prove all 168 output bits.

The tool separately proves h_out and the first **eight** B_out bits for every
uint32 source using canonical ROBDD equality against ripple-addition diagrams.
It interprets only demanded bits from versioned source slices, preserving
assignment versions, masks, fixed shifts, complements, and uint32 truncation.
The eight-bit proof peaks at 157,895 decision nodes. Wider attempts exceed the
existing two-million-node bound; integer polynomial expansion also grows too
large. Neither attempt is represented as a completed full-addition proof.
Further solver-backed verification would require an additional development
dependency. The approved development-only `analysis` extra supplies Z3 without
changing runtime dependencies. `tools/prove_monolith4_span_identity.py` first
checks an independent fixed-width AST translation and its demanded Boolean
translation against eight generated-code controls. It then checks each decoded
output bit incrementally, retaining only equalities already proved for all
source assignments as lemmas. Reports include source/model SHA-256 hashes,
solver version, completed query count, and timeout/unknown or counterexample
status. An unknown result exits unsuccessfully; it is never treated as proof.

With Z3 4.16.0 and a 60-second solver budget, the full attempt established the
boundary bit and first 25 payload bits, then returned unknown/timeout on the
next query. This extends the bounded source proof, but **does not establish the
remaining 143 payload bits**. The runtime is unchanged.

```bash
python -m tools.recover_monolith4_span_identity
python -m pip install '.[analysis]'
python -m tools.prove_monolith4_span_identity --payload-bits 25
python -m tools.prove_monolith4_span_identity --timeout-ms 60000
```

Remaining work: prove the full Monolith4 candidate, derive corresponding
Monolith3/6 equations, and establish encoding bounds through the whole setup.
A bounded prefix proof alone does not justify a runtime rewrite.

## Dependency neighborhoods

The source-word neighborhoods repeat across the two six-word outputs:

| Output words | Possible source words in each of the three 18-word input spans |
| --- | --- |
| 0 and 6 | 0–2 |
| 1 and 7 | 0–5 |
| 2 and 8 | 0–8 |
| 3 and 9 | 0–2, 6–11 |
| 4 and 10 | 0–2, 9–14 |
| 5 and 11 | 0–2, 12–17 |

Add offsets 0, 18, and 36 to the second column for the three actual input
spans. For example, output word 0 can depend on source words 0–2, 18–20,
and 36–38. These are conservative *bit-level* dependencies from the earlier
trace: cancellation can remove an input. The symbolic recovery finds the
actual Boolean functions, including those cancellations.

Run the detailed trace with:

```bash
python -m tools.trace_session_auth_bits 5 0
python -m tools.trace_session_auth_bits 5 0 --json
```

## Equivalence and limits

`tools/recover_monolith5.py` symbolically interprets each output's versioned
backward slice using reduced ordered binary decision diagrams (ROBDDs). It
converts each exact Boolean function to its unique algebraic normal form,
checks the first-stream lane separation, factors every second-stream bit,
and deterministically regenerates the compact data. It rejects unsupported
operations, mixed first-stream lanes, unexpected factorization residuals,
nonzero padding bits, or a change in the expected function count. Verify the
checked-in model with:

```bash
python -m tools.recover_monolith5 --verify tools/monolith5_model.json
```

The test suite checks the symbolic engine on a small exhaustive expression,
regenerates and compares the complete saved model, checks the upstream
Monolith5 known-answer vector, and differentially compares 100 seeded random
inputs against the generated implementation. Thus the model is equivalent to
the pinned generated Monolith5 *within the supported uint32 expression and
sound backward-slice model*. It does not prove equivalence to every Siemens
DLL or firmware version, and it has not replaced the hardware-validated
runtime implementation.
