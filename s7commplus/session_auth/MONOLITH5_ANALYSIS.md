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
