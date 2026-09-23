# Transform12: exact arithmetic tape decompilation

`tools/decompile_transform12.py` decodes the pinned Transform12 tape into
versioned arithmetic equations. It can inspect individual dispatch blocks,
trace selected exit slots, and compose the deterministic second phase of
Transform7 into one program. This is analysis tooling; the runtime tape and
interpreter are unchanged.

## Tape coverage and operands

The 498 Transform7 dispatch alternatives partition the first 60,858 tape
words without gaps or overlaps. These contain 34,253 multiplies, 2,510
squares, 16,907 additions, and 7,188 subtractions. The resource has 60,906
complete words plus one trailing zero byte. Its final 48 complete words and
trailing byte are outside every dispatched range; they are not interpreted as
instructions by this analysis.

Each context slot occupies 24 bytes; the 3,576-byte context contains 149 slots.
Source indices below 256 address context slots and higher indices address the
768-row auxiliary table. Square consumes only its first operand. Reserved
encoded bits are recorded and ignored just as in the interpreter.
All dispatched instructions fit their buffers and have zero reserved bits.

The auxiliary rows have 478 distinct integers after `Prepare`; 285 prepare
to zero. The tool prints both row references and their prepared integers on
request. It preserves the original packed values for evaluation.

## Versioned equations and exact evaluation

Every write creates a new value, so an instruction that reads its destination
sees the previous version. An output slice follows those versions backward
to entry context slots and constant rows. Across dispatch boundaries, the
composer replaces block entry references with the previous block's exit
versions. It also retains original tape indices for source navigation.

An independent SSA evaluator uses the same vector-tested BigInt primitives as
the runtime. It resolves initial reads before writing any final slots, and
therefore preserves aliased reads and writes. This verifies the decompilation
and composition of the program, rather than claiming an independent recovery
of the arithmetic primitives themselves. The primitives include packed
`Prepare`/`Finalize` and overflow behavior; replacing them with ordinary
modular arithmetic requires separate proof.

```sh
python -m tools.decompile_transform12 --catalogue
python -m tools.decompile_transform12 --catalogue --json
python -m tools.decompile_transform12 --dispatch 496 --constants
python -m tools.decompile_transform12 --dispatch 496 --output-slot 27
```

## The second phase is a fixed two-input arithmetic program

Stages 0–159 dispatch on `prng2` bits from bit 159 down to bit 0. Stages
160–248 dispatch on the first 89 bits of the work-buffer copy of `prng1`.
For **every** stage in that second group, its two alternatives have identical
versioned equations, operands, destination bindings, and buffer sizes. Their
locations in the tape differ; their operations do not. This equality is
checked before composing the fixed phase. The observation concerns second-loop
dispatch choices; Transform7 also uses `prng1` earlier.

The 89 fixed blocks contain 2,000 arithmetic instructions. Their four exit
slots consumed by Transform7 are 27, 61, 71, and 97 (byte offsets `0x288`,
`0x5B8`, `0x6A8`, and `0x918`). Tracing those four outputs retains 1,989
equations and 119 constant rows, but only two entry slots: 5 and 87.

```sh
python -m tools.decompile_transform12 --phase2
python -m tools.decompile_transform12 --phase2 --output-slot 27 --constants
python -m tools.decompile_transform12 --phase2 --json
```

The final fixed block illustrates the resulting readable structure. Let
`U`, `V`, `A`, and `B` denote its entry slots 14, 65, 81, and 82, and `Kj`
denote packed constant-table row `j`. All functions below denote the exact
packed arithmetic primitives, with their original operation order:

```text
exit71 = add(multiply(K53, A), B)
exit61 = multiply(U, exit71)
exit97 = multiply(A, add(subtract(U, A), B))
D = subtract(A, B)
Q = multiply(K482, multiply(square(U), D))
R = multiply(K482, multiply(V, D))
S = multiply(K481, multiply(A, D))
T = multiply(K480, multiply(U, add(A, B)))
exit27 = add(subtract(add(subtract(K483, R), Q), S), T)
```

This recovers the program's data flow and a deterministic arithmetic tail.
It does not yet identify the tail as a particular curve-coordinate conversion
or field-inversion formula. The next semantic analysis can focus on a fixed
two-input program rather than 178 apparently conditional blocks.

## Independent integer semantics

`tools/transform12_integer_model.py` recovers the arithmetic without calling
Prepare, Finalize, or any runtime arithmetic helper. Canonically packed operands
represent an unsigned 160-bit integer: each of the first five little-endian
uint32 words stores 28 bits shifted left by two; the sixth stores the remaining
20 bits shifted left by two. All 768 constant rows use this packing. Canonical
packing does **not** mean a representative is reduced modulo a field modulus.
Arbitrary noncanonical Prepare inputs are outside this model's domain.

The overflow fold multiplies the bits above position 159 by 47, consistent with
the candidate modulus `p = 2^160 - 47`. But ordinary `% p` is not an exact
replacement for the current implementation:

- Addition leaves results below `2^160` unreduced. On overflow it adds 47 to
  only the low 128 bits. A carry beyond those four words is discarded and an
  additional 94 is added to the low word instead of incrementing word five.
- Subtraction subtracts an additional 47 only for negative differences, then
  truncates the signed representation to 160 bits.
- Multiplication and square fold overflow at most twice. If overflow remains,
  the final correction adds 47 to the low uint32 without propagating its carry,
  and the result is truncated to 160 bits.

A concrete counterexample uses **two already reduced operands**:
`a = p - 1`, `b = 2^128 + 47`. Runtime addition returns `140`, whereas
`(a + b) % p = 2^128 + 46`; these are not even congruent modulo `p`.
This is a compatibility finding, not evidence that this input occurs in an
actual authentication session, or a reason to silently change the runtime.

The independent model matches all 498 dispatches byte-for-byte on a seeded
canonical context, plus ten complete fixed-tail contexts. Boundary and seeded
random tests compare more than 8,000 primitive results with the runtime. This
provides a smaller exact reference for further semantic recovery, but does not
prove equivalence for every possible operand or identify the cryptographic
construction. A field-level simplification needs additional range/invariant
proofs or must preserve these compatibility corrections.

## Compact mathematical shadow

`tools/recover_transform12_formulas.py` symbolically interprets the fixed tail
in the polynomial ring `(Z/pZ)[x,y]`, where `x = in5`, `y = in87`, and
`p = 2^160 - 47`. It expands and cancels coefficients exactly, without reducing
exponents, assuming primality, or fitting formulas to sampled values. At most
75 nonzero terms occur in any intermediate polynomial; the four final
polynomials contain only nine terms in total.

Let `Kj` denote the decoded integer in constant row `j`, reduced modulo `p`.
The recovered formulas are:

```text
e = (p - 1)/2 - 40
z = x^e
t = x^(p - 2)
out71 = y
out61 = z*y
out97 = x^79*(z + y)
out27 = K483 + K482*t*y + K481*out97 + K480*out61
```

All equations in this section use arithmetic modulo `p`. The exponent `p-2`
is inverse-like, and `(p-1)/2` suggests a character-like power, but those
interpretations require additional primality and nonzero-input arguments.
The formulas alone do not establish a curve-coordinate interpretation.

**These are not byte-equivalent runtime replacements.** Even the small entry
inputs `x=y=1` cause divergence. The first loss of modular congruence is at
SSA value 429, tape word 34725: subtraction receives `2` and `p+3`. Exact
arithmetic returns `2^160-1`, whose residue is 46, rather than the modular
result `p-1`. The final slots 27, 61, and 97 then differ from the shadow;
slot 71 agrees for this witness. Both entry inputs being below `p` is therefore
insufficient to justify a modular rewrite. This does not establish that the
witness occurs in a real authentication session.

```bash
python -m tools.recover_transform12_formulas
python -m tools.recover_transform12_formulas --compare 1 1
```

The first command regenerates exact sparse polynomial coefficients. The second
locates the first divergence between independent compatibility arithmetic and
the modular shadow. Tests verify the complete coefficient identities, compare
compact formulas with both polynomial evaluation and a modular tape interpreter
on boundary/random inputs, and preserve the packed-runtime mismatch witness.
The next task is recovering input/intermediate invariants or retaining exact
corrections alongside the short mathematical structure.

## Reachability through Transform7

`tools/trace_transform7_tail.py` instruments the real Transform7 orchestration
temporarily, without changing library source. It captures the context before
dispatch 320/321 (stage 160) and after the last dispatch, validates all 249
dispatch ranges, and checks the independent exact tail against the captured
exit bytes. A second complete Transform7 run substitutes only the four compact
shadow outputs before PrepareFinalize and the downstream monoliths, then
compares the complete 72-byte destination.

The sweep uses deterministic synthetic PRNG pairs, the seed generator's bundled
base-point data, and bundled public keys `00:181B7B0847D11694` and
`01:BD426B091F08731A`. No live secrets, PLC access, or new hardware capture are
involved. The default report aggregates checks; `--details` includes per-case
checks and hashes of synthetic destinations, not raw key material. The patching
is single-threaded diagnostic instrumentation, not a runtime execution option.

```bash
python -m tools.trace_transform7_tail --random-cases 32
```

With seed `0x712`, all **111 cases** passed: three public sources, each with
five structured PRNG pairs and 32 seeded random pairs. Every observed pair of
tail-entry representatives was nonzero and below `p`. All exact-model tail
bytes matched. No intermediate lost modular congruence; shadow outputs matched
both residues and packed representatives, and substituting them left every
complete Transform7 destination unchanged. The structured pairs cover zeros,
one, all-one bits, the highest scalar bit, and alternating patterns.

This is reachability **sampling**, not proof that all reachable inputs satisfy
the needed invariants. In particular, the independently established `x=y=1`
counterexample remains a reason not to switch the runtime to compact modular
formulas. The next proof obligation is deriving constraints on the tail inputs
and intermediate representatives from the first 160 dispatch stages.

The downstream source also reveals an unused branch: slot 71 is normalized at
offset `0x6A8`, then passed to the last Monolith7 call, which writes work-buffer
regions `[0x4E0,0x528)` and `[0x498,0x4E0)`. Neither region is read again before
Transform7 returns. The live final result uses slots **27, 61, and 97** instead.
A negative-control test replaces slot 71 with zero: tail bytes differ, but the
final destination does not. Replacing live slot 27 with zero changes the final
destination, ensuring the instrumentation does not simply report success for
every substitution. Removing this dead branch is a later cleanup decision;
the runtime is unchanged. Slicing away slot 71 alone does not shorten the
1989-equation tail slice, because its dependencies are shared with live outputs.

Tests also verify scalar-bit dispatch selection and restoration of the patched
dispatcher after both normal execution and exceptions.

## Verification

Tests compare all 498 decoded programs byte-for-byte with the tape interpreter,
exercise aliased assignments, trace selected outputs, and compare the composed
second phase with all 89 runtime dispatches using mixed branch choices. The
catalogue test verifies prefix coverage, the excluded suffix, and all identical
branch pairs. Malformed ranges and buffer references are rejected.

The catalogue records SHA-256 hashes of both binary resources, so reports can
be associated with the exact analyzed revision. Preserve the HarpoS7 attribution
and `LICENSE-HarpoS7` when reusing the derived equations or tooling.
