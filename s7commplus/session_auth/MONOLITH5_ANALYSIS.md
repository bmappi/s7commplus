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

For Monolith4, the resulting decoded full-addition identity is now proved
by the carry-stage source proof below:

```text
T = B0+B1+(h0 & h1)
B_out = T mod 2^168
h_out = h0 XOR h1
overflow = T >= 2^168
V(out)-V(in0)-V(in1) = -12032*overflow (mod p)
```

The last equation follows algebraically from the decoded addition: the boundary
contributes -p*(h0 & h1), which vanishes modulo p, while a discarded carry
contributes -2^168, congruent to -12032. All 1,000 seeded arbitrary raw-span
tests match the complete formula and both overflow branches. Sampling alone
did not prove all 168 output bits; the later source proof completes that step.
The exact signed decoder also obeys the integer identity:

```text
D(out) = D(in0)+D(in1)-n-p*(h0 & h1)-2^168*overflow
```

This retains both corrections before modular reduction. Independent weighted
decoder tests cover all eight boundary-bit/overflow combinations. The tool's
historical `candidate_add` name is retained, but its decoded predictions are
now established for the pinned source, not merely sampled.

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

The initial Z3 4.16.0 run with a 60-second solver budget established the
boundary bit and first 25 payload bits, then returned unknown/timeout on the
next query. That attempt was only a bounded source proof; the carry-stage
decomposition below subsequently proves all 168 bits. The runtime is unchanged.

```bash
python -m tools.recover_monolith4_span_identity
python -m pip install '.[analysis]'
python -m tools.prove_monolith4_span_identity --payload-bits 25
python -m tools.prove_monolith4_span_identity --timeout-ms 60000
```

Remaining work: derive corresponding Monolith3/6 equations and establish
encoding bounds through the whole setup. A decoded identity alone does not
justify replacing encoded runtime words.

## Carry-stage proof decomposition

`tools/prove_monolith4_carry_stages.py` expresses the addition proof in terms
of the actual decoded source functions, rather than growing ideal prefixes.
Let xk and yk be the normalized input payload bits and sk the decoded output.
Define ck = sk XOR xk XOR yk. The proof obligations are:

```text
h_out = h0 XOR h1
c0 = h0 AND h1
c(k+1) = majority(xk,yk,ck)        k=0..166
```

These 169 obligations imply all 168 payload sum bits by induction: sk is
xk XOR yk XOR ck by definition. No carry equality is assumed to prove itself.
The final overflow follows from the mathematical addition once this chain is
complete. Eight deterministic controls compare both the independent fixed-width
AST compiler and the demanded-bit compiler against generated output before any
solver queries. Reports pin source/model hashes and solver version.

Initially, dedicated stages [0,31) with Z3 4.16.0 all returned UNSAT, establishing
the boundary and a **30-bit payload prefix**. An isolated UNSAT proof of
carry_29_to_30 then extends the established prefix to **31 bits by composition**.
The isolated report correctly claims no prefix on its own: it does not include
the base cases. That was a partial result, superseded by the complete run below.

The full source run now returns **UNSAT for all 169 obligations**, proving the
boundary identity and all **168 payload bits** for arbitrary uint32 inputs.
It uses fresh Z3 SAT-tactic solvers over the unsimplified demanded-bit DAG,
without cut signals, retained lemmas, or reachable-state assumptions. Preserving
the source DAG and selecting the direct SAT tactic made previously stalled
queries tractable. The run used a 30-second budget per stage; total stage time
was about 530 seconds and the slowest stage about 7.05 seconds. Compilation and
the eight generated-code controls are outside the per-stage solver budget.

`tools/monolith4_carry_proof.json` records the full run, hashes, Z3 version,
timings, and every completed obligation. It is a solver-run record, **not an
independently checkable proof certificate**. Default tests check its provenance
and accounting, not the UNSAT answers themselves; rerun the optional harness to
replay the proof. Time budgets and proof frontiers can vary, and an unknown is
still neither a proof nor a refutation.

The experimental cone mode replaces nonlocal sub-DAGs with consistently shared,
independent Boolean cut signals. Every concrete source assignment specializes
those signals back to their original functions, so UNSAT proves a stronger
equation and therefore the source equation. SAT may be spurious. Refinement
expands cut definitions instead of inventing reachable-state constraints.
Initial aggressive cuts prove the base cases but lose correlations required
for later stages; widening them has not completed the full proof. An optional
lemma-retaining solver mode uses only previously proved equalities and was
slower in the tested run, so independent stage queries remain the default.

Dependency-free tests exhaustively check cone specialization and refinement on
small shared Boolean DAGs, including an original UNSAT expression whose
generalization is SAT. They also guard constant preservation, induction gaps,
partial-range completion, invalid query limits, source DAG preservation,
observer isolation, and explicit timeout reasons. CLI failures and timeouts
exit unsuccessfully, and a full proof requires every one of the 169 stages.

```bash
python -m tools.prove_monolith4_carry_stages --stop 31 --timeout-ms 10000
python -m tools.prove_monolith4_carry_stages --start 31 --stop 32 --timeout-ms 30000
python -m tools.prove_monolith4_carry_stages --timeout-ms 30000 --progress
python -m tools.prove_monolith4_carry_stages --abstract --stop 6
```

The next source-proof targets are Monolith3/6 and the complete setup composition,
including overflow and carry-sensitive packing. The completed Monolith4 proof
establishes only its decoded payload and boundary, not individual encoded output
words or the safety of a whole-pipeline modular rewrite. Runtime source and
dependencies remain unchanged.

## Monolith6: local carry proof and corrected pair halving

`tools/prove_monolith6_span_identity.py` establishes a decoded **pair** identity
from the pinned generated Monolith6 AST. There are three normalized inputs
`(Bi,hi)` and two outputs `(Oj,gj)`, with the same H=(p+1)/2 and M=2^168.
Define:

```text
q = parity(h0,h1,h2)
a = majority(h0,h1,h2)
T = B0+B1+B2+H*q+a
U = 2*(O0+O1)+g0+g1
U = T                         (mod M)
g0+g1 <= 1
```

This is not unconditional field halving: M is nonzero modulo p. The local
proof also establishes the signed wrap balance m is -1, 0, or 1. Consequently:

```text
m = (U-T)/M
2*(V(out0)+V(out1))-sum(V(in)) = M*m+p*(g0+g1-a)     (exact integers)
V(out0)+V(out1) = H*sum(V(in))+6016*m                (mod p)
2*(D(out0)+D(out1))-sum(D(in)) = n+M*m+p*(g0+g1-a)   (exact integers)
```

Here the exact-integer V means B+H*h before reduction; D=n+V remains the
weighted signed decoder. These equations use only 2H=p+1 and M mod p=12032,
not a primality assumption. The m calculation currently uses actual output
high bits; it is **not an input-only prediction** from the current decoder.

The source proof decomposes the equation into local integer columns. Let nik
be input i's payload bit k, Nk=sum_i(nik), and fk=bit_k(H). Set:

```text
ak = majority(h0,h1,h2)            if k=0
ak = majority(n0,k-1,n1,k-1,n2,k-1) otherwise
rk = floor((Nk+fk*q+ak)/2)
g0+g1 = N0+q+a0-2*r0
o0,k-1+o1,k-1 = Nk+fk*q+r(k-1)-2*rk   k=1..167
m = o0,167+o1,167-r167
-1 <= m <= 1
```

The initial column and 167 subsequent columns telescope to U=T modulo M;
the top-bit equation gives its exact wrap balance. The carries are explicit
input functions, not assumed equalities or growing ideal-prefix recurrences.
Each equality is proved independently for all source assignments. Four-bit
bitvector arithmetic encodes these small integer comparisons exactly: counts
are at most five, carries at most two, and column differences lie between
-6 and 6, so no mismatch can alias zero modulo 16. Dependency-free tests check
these bounds and the integer equations independently.

With Z3 4.16.0, all **170 obligations returned UNSAT**: boundary exclusivity,
initial column, 167 local columns, and the wrap bound. Stage time totaled about
5.46 seconds, with no stage exceeding 0.10 seconds in the recorded run. This
excludes source compilation and eight generated-runtime controls comparing both
the independent fixed-width AST and demanded-bit compilers. A full-width query
previously timed out after 60 seconds, and the slower prefix formulation remains
available as `--prefix-queries`; neither a timeout nor an interrupted run is a
completed proof.

`tools/monolith6_span_proof.json` records the source/model hashes, Z3 version,
timings, and all completed obligations. Like the Monolith4 record, it is **not
an independently checkable proof certificate**. Normal tests verify provenance
and accounting without requiring Z3; rerun the optional harness for the proof.
The shared demanded-bit evaluator now supports separately cached versioned
Monolith3/4/6 programs and output spans. Concrete controls exercise all three
on one backend, retaining the existing Monolith4 defaults and bounded proof.

`tools/recover_monolith6_span_identity.py` checks 1,000 arbitrary raw sources:
all corrected shadows match, with wrap counts m=-1:256, m=0:515, and m=1:229.
It preserves a stronger negative control for decoded-only state. Compare an
all-zero 216-byte source with one whose uint32 word 17 has bit 9 set. All
three `(Bi,hi)` inputs are identical, but O0 decreases by 2^167, O1 is unchanged,
and the output pair shadow decreases by 6016 modulo p. The first source has
m=1, the second m=0. The bit sits outside the current input decoder and shifts
into the output's highest payload position. Therefore the existing input
payload/boundary model cannot determine even the complete output-pair shadow
for arbitrary raw sources. This is a synthetic kernel counterexample, not a
hardware authentication-failure claim.

```bash
python -m tools.recover_monolith6_span_identity
python -m tools.prove_monolith6_span_identity --timeout-ms 10000 --progress
```

Next: derive Monolith3's corresponding source equations, and track these extra
high bits or prove encoding bounds through the real setup call graph. The
conditional affine setup composition still assumes the uncorrected halving
relationship and does not incorporate these wraps. This pair proof does not
recover the individual output split or justify a modular runtime substitution.
Runtime code and dependencies remain unchanged.

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
