# Scalar-stage semantic recovery

These checkout-only tools recover polynomial identities, not replacement
runtime cryptography. Never supply live keys, challenges or PRNG material.

```sh
python -m tools.recover_scalar_curve
python -m tools.recover_scalar_shadow --stage 1 --branch 0 --formulas
python -m tools.recover_scalar_shadow --catalogue
python -m tools.recover_scalar_encodings --summary
python -m tools.prove_transform12_residue_defects
python -m tools.trace_scalar_defects --effective-scalar 0
```

## What is established

All 320 first-phase branch programs can be expanded into sparse polynomials in
their four/five live entry residues, over the ring Z/pZ, p = 2^160 - 47. The
catalogue regenerates all 56,497 live instructions and hashes each complete
coefficient list. Tests independently interpret the modular tape numerically
for every branch; the first two stages additionally match manually written
short formulas by **complete coefficient equality**, not sampled fitting.

The curve-shaped formulas use a = -1 and b = constant table row 58:

```
b = 0xfdec56a0f1a148a7ca6f04463a24f5f56c3f3a4f
y² = x³ - x + b
```

The unmodified reference base point in Transform7's data satisfies this
equation. The discriminant is a unit modulo p. Neither observation establishes
that all protocol inputs are on this curve or proves primality of p.

## First stage: conditional setup shadow

X is the source x-coordinate; Y = source_y | 4 and R = prng1 | 4.
Compose the actual setup AST's conditional affine expressions, without probes
or interpolation. The source-derived carry corrections are excluded here;
the existing exact setup model remains authoritative.

Let s = Y²R⁴ and define homogeneous x-doubling:

```
N(X,Z) = X⁴ + 2X²Z² - 8bXZ³ + Z⁴
D(X,Z) = 4Z(X³ - XZ² + bZ³)
```

First scalar bit 0:

```
slot1  = Y⁴ D(X,1) + s²
slot44 = Y⁴ N(X,1)
slot82 = (X+1)s
slot83 = s
```

First scalar bit 1:

```
slot1 = s; slot44 = Xs; slot82 = R⁸; slot83 = 0
```

Both leave slot94 = X. Decode pairs as
`(slot44, slot1-slot83²)` and `(slot82-slot83, slot83)`.
These are the doubled/base pair for bit0, and base/infinity pair for bit1,
subject to the usual nondegeneracy conditions for projective point meaning.
Y here is a scale, **not** the unmodified reference point's y-coordinate.

## Second stage: unconditional polynomial coordinate change

Write entry slots as `slot1=Z+V², slot44=X, slot82=U+V, slot83=V,
slot94=t`. This is a bijective change of polynomial coordinates.

```
H = XV-UZ
A = 2(XV+UZ)(XU-ZV) + 4bZ²V² - tH²
J = (XU+ZV)² - 4bZV(XV+UZ)
Q = J-tA
```

A/H² has the differential-addition form when t is the difference point's
x-coordinate. Q is retained explicitly; it is not zero for arbitrary entries.
Complete symbolic substitution proves Q=0 after **either conditional
first-stage shadow branch**, without inverses or nonzero assumptions.

Branch0 exits:

```
slot19 = N(X,Z)+H⁴+Q; slot27 = D(X,Z)
slot31 = A+H²;        slot85 = H²
```

Branch1 exits:

```
slot19 = A+D(U,V)²;     slot27 = H²
slot31 = N(U,V)+D(U,V)+Q; slot85 = D(U,V)
```

Both preserve slot94=t. With Q=0, the shared exit decoder is
`(slot19-slot85², slot27)` and `(slot31-slot85, slot85)`.
Branch0 doubles the first pair and adds the two pairs; branch1 adds them and
doubles the second pair. This establishes a two-stage descending x-only
ladder interpretation of the modular shadow. The complete stage recovery
below extends it through the remaining encodings.

The decoded second-stage exits also preserve Q=0. For each branch the tool
expands Q(next) into 760 terms and divides by Q(entry), obtaining a 267-term
quotient and **zero remainder**. It multiplies the quotient back to check the
complete identity. Thus `Q(next)=Q(entry)*quotient` holds as a polynomial ring
identity, with no coordinate inverses or primality assumption. This proves
propagation through the second stage; the generic relation proof below
extends propagation through the remaining recovered encodings.

## Exact-runtime negative controls

The existing legal setup carry witness still contradicts the unconditional
affine setup prediction, even with the unmodified **on-curve reference base
point** as source. An on-curve restriction alone therefore does not eliminate
the setup problem. A new witness reaches the second scalar stage from
accepted synthetic Transform7 inputs `source_x=2^128+48, source_y=0, prng1=0`
and scalar prefix `00`. At tape word25470, addition of `p-2` and `source_x`
returns **140**, while the modular result is **2^128+46**. Exit slots19 and31
then disagree with the modular polynomials. Tests reproduce both stage exits
byte-for-byte using the original Transform12 interpreter.

This is a synthetic API-domain witness, **not an on-curve or vendored-key
witness**. It disproves unrestricted runtime replacement; it does not show
that an actual key exchange hits this edge. Source/tool hashes accompany the
regenerated report. No production algorithm, wire behavior, generated kernel
or binary fixture is changed.

## Complete scalar shadow

`recover_scalar_encodings` now recovers **all 158 intermediate encodings**,
not just the first two stages. Discovery solves symbolic coefficient equations
jointly across both branches, modulo Q. Every accepted decoder has an exact
polynomial inverse; both encoder/decoder compositions are checked. A separate
check applies it to the **unreduced source polynomials**, proves ideal
membership, and multiplies the quotient back to reconstruct the difference.
Including initialization and the final outputs, there are 1,278 source
coordinate identities. The generic ladder preserves Q by two polynomial
ideal identities, so the condition established at initialization propagates
through all intermediate stages under modular-shadow semantics.

There are 78 branch inversions in the intermediate stages. The first stage
is not inverted; the last stage is inverted and retains the second point.
Initialize `P0=(xY,Y), P1=(R²,0)`, with Y and R already forced as above.
Each compact step doubles one point and differentially adds the pair.
The descending point indices yield the effective scalar:

```
effective = selector XOR 0xf8e62e8673b79ca477a1d36333b1c0de6c706448
tail slot5 = projective denominator Z
tail slot87 = projective numerator N
```

`scalar_ladder_model` implements the short formulas. Independent tests
interpret the complete modular tape and compare both final representatives,
including their projective scaling. The scalar-mask identity is also checked
as an integer index recurrence, without a curve group-order assumption.
The regenerated report contains every decoder/encoder, source/tool hashes,
identity quotient hashes and a complete encoding digest.

## Primitive defect model and source-AST proof

`transform12_residue_defects` retains exact uint160 representatives with
explicit deviations from ordinary ring arithmetic:

- Addition's correction is **94-2^128**, precisely when `a+b >= 2^160` and
  its low128 part is at least `2^128-47`.
- Subtraction's residue correction is **47**, precisely when `a-b < -p`.
- Multiplication preserves residues throughout the uint160 input domain.
  Three ordinary high160 folds reproduce its representative; after the second
  fold the value is below `2^160+2209`, so the final low-word correction cannot
  lose a carry.

The optional development-only Z3 command proves six obligations against the
**actual AST of the checkout integer model**: addition/subtraction lifted
representatives, multiplication's three-fold representative and three fold
bounds. It abstracts the initial product to an arbitrary uint320 value,
making the fold theorem stronger than the input-product domain. All six are
UNSAT. This is **not** a generated-kernel SMT proof: correspondence between
that integer model and packed runtime remains separately tested, including
new boundary/random packed primitive controls.

## Exact projective representatives: counterexamples

For the unmodified on-curve reference point, PRNG1=0 and effective scalar0,
the exact scalar trace encounters three addition defects, first at stage79,
tape word36796. It retains tail denominator **p**, congruent to zero, and a
different numerator from the compact model. Thus the ordinary nonzero inverse
precondition is disproved by an accepted reachable source input.

Effective scalars1 and2 preserve the same affine curve point but disagree in
the required projective representatives. The final 72 output bytes disagree.
Replacing zero tail results61/97 with p repairs scalar0's output but **fails
for scalars1 and2** (also 3,4,16 in exploratory checks). These are retained
negative controls, not candidates for a production fallback rule.

We therefore have a complete compact **modular scalar shadow**, but not an
equivalent compact exact authentication algorithm. The remaining obstacle is
recovering a self-contained representative/defect schedule, plus proving final
encoded-output correspondence. On-curve validity, Q=0 and the correct affine
point do not suffice. The following transport model explains the tested
projective-scale mismatches, but does not yet recover the schedule. No runtime
algorithm, generated source, binary fixture or wire behavior is changed.

## Symbolic carry transport and event-assisted scale replay

Run `python -m tools.transport_scalar_defects --effective-scalar 0`.
The tool lifts every live SSA operation at an observed defect-bearing stage
into a sparse polynomial in independent correction variables. It injects an
error at each observed addition/subtraction site and retains nonlinear terms;
it does not interpolate corrections or assume that every error is a scale.
Inputs at the stage boundary are fixed numerical representatives, so these
are **local symbolic identities**, not identities over all possible inputs.
Assigning the actual carry corrections reconstructs every exact exit residue.
Missing, duplicated, foreign or operation-mismatched sites are tested controls.

For the on-curve reference point with PRNG1=0 and effective scalar0:

- Stage79's two independent errors cancel completely at the decoded boundary,
  for all values of the injected errors. Both point scales remain 1. This does
  not mean their representative effects are irrelevant to later predicates.
- Stage80's error leaves the first point unchanged. The second point's
  coordinates are `(C+E,0)`, where `C=47^4 * 2^128`
  (`1660469400499131922331423267767258137845825536`).
  Its scale relative to the error-free stage is `s=1+E/C` modulo p.
  C is a unit; with the actual `E=94-2^128`, s is also a unit.

This constant has a readable origin: stage79's second point is
`(47*2^32,0)`, and stage80 doubles it to `((47*2^32)^4,0)`.
That fourth power is below p, so C needs no reduction. The corrected numerator
is therefore `(47^4-1)*2^128+94`. This uses the recovered boundary and doubling
identity; it does not require a primality or Fermat-theorem assumption.

Cross-product identities alone are not sufficient: a zero vector can have
zero cross product without representing a point. The report therefore also
checks a full coordinate scale identity and tests whether the actual scale is
a unit. Degenerate and point-distorting negative controls are retained.

The subsequent homogeneous propagation is compact:

```
ladder bit0: (a,b) -> (a^4, a^2*b^2)
ladder bit1: (a,b) -> (a^2*b^2, b^4)
```

Complete monomial degrees prove these scaling rules for arbitrary scales.
The replay compares decoded exact coordinates against the scaled compact
ladder at **all 160 boundaries**, not just the final affine point. Tested
effective scalars include 0,1,2,3,4,16, a longer suffix, `2^79-1` and a
full-width scalar. Every tested boundary agrees. Retaining observed tail tags
also reconstructs the exact uint160 tail, including denominator p versus0.

There is a further closed expression. Conditional on scales `(1,s)` after
stage80 and no later nontrivial corrections, with effective scalar
`0 <= n < 2^79`, the final second-point scale is

```
s ** (2^79 * (2^79 - n)) modulo p
```

More generally, after m suffix bits, put q=2^m. Starting with exponent pair
`(0,1)`, its exponents are `(q*(q-n-1), q*(q-n))`. Each effective bit e uses
ladder bit `1-e`; substitution of `q'=2q, n'=2n+e` directly preserves both
integer branch recurrences. There is no prime-modulus or curve-group-order
assumption and no exponent reduction. The tool compares the closed expression
against the complete scale replay when the observed schedule permits it.

**Boundary of this scale replay:** it still executes the exact SSA to observe the
carry sites, corrections and representative tags. Agreement therefore does
not establish a self-contained compact exact algorithm, a global proof of
the observed schedule, a byte-equivalent runtime replacement, or PLC
interoperability. Unsupported/non-scaling corrections are reported explicitly
rather than silently forced into a scale model. The next research task is
recovering those carry predicates/tags without the original full trace, then
proving correspondence through the representation-sensitive final output.
The following predictor removes that exact-trace dependency, but not the
source-dependent guard/tag machinery.

## Carry prediction without a full exact arithmetic trace

Run `python -m tools.predict_scalar_defects --effective-scalar 0`.
The new evaluator supplies residues from source-derived sparse polynomials.
For a canonical uint160 encoding, a residue greater than46 has exactly one
representative. Only residues0..46 can be either r or p+r.

Two cheap **necessary** conditions exclude impossible carry defects before
requesting operand representatives:

```
add: ordinary result residue in [47,92], OR
     residue >= 2^128 and low128(residue) < 47
sub: operand residues a < b <= 46
```

The evaluator visits guards in source order. If a necessary condition holds,
it obtains the operand representatives, checks the actual carry predicate,
and injects the detected correction into the result polynomial. Descendant
polynomials and cached residues/tags are repaired before later guards run.
This preserves nonlinear interactions between multiple defects. There is no
full exact-instruction-trace fallback or pre-recorded event schedule.

Ambiguous representatives are resolved on demand with lift bits. Conditional
on the operation's **corrected** residue r being0..46, the p-lift bit is:

```
add: a+b >= p
sub: a-b >= p OR a-b < -p
mul: a*b >= p
representative = r + p*lift_bit
```

Zero residues allow further pruning: addition returns p iff either operand is
positive, multiplication iff both are positive, and subtraction iff a>b.
A nonzero residue already proves positivity without resolving its lift bit.
These rules preserve p versus0 and p+r versus r, rather than normalizing them
away. None calls the old integer-model or lifted arithmetic executor.

One consequence is an **exact** compact multiplication formula, implemented
as `compact_multiply` (the three-fold oracle is retained separately):

```python
product = a * b
r = product % p
result = r + (p if r <= 46 and product >= p else 0)
```

Folds preserve the residue; lifts above46 are unique; the product-threshold
lemma selects the small lift. This is not merely a modular-shadow formula.
Packed runtime boundary/random controls include noncanonical inputs and
small-positive outputs, such as `(p-1)^2 -> p+1`, not1.

`python -m tools.prove_scalar_predicate_guards` proves **11** obligations
against the actual guard/lift Python AST and integer-model AST: both necessary
guards, unique/ambiguous lift bounds, ordinary-sum residue bounds, three small
lift rules and three zero-tag rules. Multiplication abstracts a*b to an
arbitrary uint320 product, just as the existing fold proof does. All are UNSAT;
UNKNOWN remains a failure. These are primitive-domain lemmas, **not** a
whole-predictor or generated-kernel SMT certificate. The small guard compiler
rejects unfamiliar expressions and ignored statements.

For the reference point, PRNG1=0 and effective scalar0, the full evaluator
predicts the three known carry events and exact **72-byte Transform7 output**.
It represents 29,168 source instructions including the fixed tail, but calls
no legacy arithmetic executor; it uses 279 zero-tag rules, eight potential
guard sites and 22 repaired source nodes. These counts are case-specific, not
a worst-case bound or performance guarantee. Source polynomials and the lazy
tag dependency graph are still retained. Tail events also carry unique SSA
identities because stitched original tape addresses may repeat.

Tests exercise all320 scalar branches with2,560 boundary/random layouts,
all160 exact boundaries on selected complete runs, arbitrary synthetic sources,
native full outputs for all three bundled public sources, and negative
controls with missing guards and canonical-only tags. They explicitly forbid
calls to all six old primitive executor functions in the new evaluator.

## Unreduced source recurrence after Q is lost

Run `python -m tools.recover_scalar_relation_terms`.
Direct comparisons of complete, unreduced polynomial coefficient dictionaries
recover the following source law for **arbitrary** decoded stage coordinates:

```
ordinary differential ladder step
if stage in 1..15 or 144..159:
    doubled numerator += Q  (modulo p)
```

The denominator and differentially added point are unchanged by this Q term.
The final stage observes only the retained second point. There are **1,268**
unconditional intermediate/final coordinate identities, plus the existing ten
initial identities conditional on the source-derived setup shadow. Unlike
the earlier proofs modulo Q, these retain the error term rather than requiring
Q=0. Numerical controls include states with nonzero Q.

## Concrete limit: field/scale state cannot replace representative history

A verified **synthetic on-curve** source point is:

```
x = 2^128 + 48
y = 917984300236617229462155822449362250189314875415
PRNG1 = selector = 0
```

The curve equation is checked exactly; no primality assumption is needed to
verify this candidate. It is not a captured PLC public key. Stage1's two
addition defects at words25470/25476 turn Q from zero to nonzero. After the
complete scalar phase, both the exact and ordinary-shadow denominators are
units, but their projective cross product is
`1307426275097508917995851978661085928554276274481`, **not zero**.
Thus their affine points differ: no rescaling repairs the ordinary ladder.
The new predictor agrees byte-for-byte with the original Transform7 on this
input, including the full72-byte result.

There is also an information-loss control at a synthetic valid stage boundary.
Take decoded coordinates `(16,0,4*x,4)` with fixed difference x above; Q=0.
Under the initial encoder, changing raw slots1/44 from16 to p+16 leaves every
decoded coordinate and Q identical. Yet the next source stage has additional
carry defects, including a subtraction correction47, and its second point
changes. Reachability of both boundary lifts from complete Transform7 is not
asserted. This proves that coordinates/Q alone do not determine the general
exact stage transition: representative bits cannot simply be discarded.

The current limit is a **source-independent compact exact rewrite**, not
offline reproduction of the open code. Ordinary curve multiplication,
projective-scale correction, canonical-only lifts and dropping relation terms
all have concrete negative controls. A richer source-dependent polynomial/tag
evaluator now reproduces the tested complete outputs. Standalone primitive
guard/tag rules are derived below; compressing entire stage transitions remains
unresolved. An exploratory
all-independent-error expansion at stage80 succeeds with138 error variables
and542 terms in its largest decoded coordinate; this is not a feasible-guard
proof and does not remove those dependencies. No mathematical impossibility
claim, hardware validation, runtime substitution or independent acceptance
claim follows. Further research needs new structural factoring/synthesis of
the guard/tag transitions; a PLC is not required for that mathematical task.

## Standalone residue/lift primitive rules

`scalar_representative_rules.py` removes source dependencies from each primitive.
An exact uint160 representative is `(r,t)` with canonical residue `0<=r<p`
and Boolean lift `t`; `t=1` is legal only for `r<=46`. Its integer value is
`r+p*t`. This bit is necessary, not redundant geometric state.

For addition write `s=ra+rb`, `k=ta+tb`, and `B=2^128`. The defect predicate is:

| Lift count | Necessary and sufficient addition defect |
| --- | --- |
| 0 | `s>=p+47` and `s mod B>=B-47` |
| 1 | `s>=47` and `s mod B<47` |
| 2 | `s>=47` |

If defective, add `94-B` to the field sum; the output lift is always zero.
Otherwise the output lift is true exactly when:

- `k=0` and `p<=s<p+47`;
- `k=1` and either `s<47` or `s>=p`;
- `k=2` and `s<47`.

For subtraction the defect is exactly `not ta and tb and ra<rb`. Add47 to
`ra-rb` in that case. The output lift is true for this defect, or for
`ta and not tb and ra>=rb`. No reconstructed uint160 subtraction is needed.

For multiplication let `v=ra*rb`, `r=v mod p`. The output lift is true iff
`r<=46`, both exact operands are positive, and
`ta or tb or v>=p`. Operand positivity is `ri!=0 or ti`. Thus all three
primitives have an exact residue/bit normal form; only multiplication needs a
field product, and no repeated high160 folds are required.

`prove_scalar_representative_rules.py` compiles the actual single-return
Python guard/tag AST and actual integer-model arithmetic AST. Six core obligations
are UNSAT across all uint160 input pairs: both defect predicates, both corrected
expression bounds, and both complete addition/subtraction representatives.
Addition obligations partition the lift count exhaustively into0/1/2; every
case must be UNSAT. Signed162-bit source compilation suffices for these
uint160 sums/differences; multiplication keeps its separate322-bit proof.
The source compiler sizes conditional integer literals from its operand width.
The corrected expressions lie in `(-p,2p)`, so one conditional canonical fold
is sufficient in the proof. This is not a multiplication, packing, generated
kernel, or whole-ladder SMT certificate. The multiplication formula follows
the existing residue-preservation/unique-lift/product-threshold lemmas and is
also checked against the independent three-fold oracle and packed runtime.

`scalar_representative_program.py` uses only these primitives to execute the
recovered source graph, then the existing setup/finalizer research models. It
reproduces full72-byte outputs and every boundary in the permanent controls,
including the on-curve point-changing carry example. Tests cover all320 source
branches with2240 boundary/random layouts, every small-residue/lift pair,
direct packed primitive comparisons, and negative controls for discarded lifts
and suppressed defects. Patching old arithmetic and polynomial executors to
throw does not stop this evaluator. The polynomial predictor now uses the
same standalone rules at potential carry sites, while retaining its separate
residue-polynomial and lazy-tag machinery.

This is a primitive-level exact simplification, not a source-independent
four-coordinate ladder. It still executes each selected source instruction;
compressing those instructions and their tag dependencies at stage level is
the next research boundary. No runtime replacement or hardware claim follows.

## Bounded stage carry/tag/output plans

`scalar_stage_plan.py` combines source field operations at compile time into
sparse polynomial formulas. Every potentially defective addition/subtraction
introduces a separate correction variable `e<SSA>`. Its value is decided in
source order: zero or `94-2^128` for addition, zero or47 for subtraction.
Products of these variables retain nonlinear carry interactions. Unlike the
earlier predictor, detecting a correction does not rebuild source descendants.

Simple exact constant folding/CSE would eliminate only9 of58486 instructions
across both alternatives of160 stages and the fixed tail. Independent-error
polynomials fit ordinary stages, but unrestricted expansion exceeds4096 terms
at the initial stage and fixed tail. The new compiler introduces formula
anchors `f<index>` when expansion would exceed a declared term/work bound.
Anchors refer only to earlier bindings. They do not invoke an older arithmetic
executor or assume a curve relation. A bound as small as two terms still works;
larger bounds trade fewer anchors for larger expressions, not guaranteed speed.

Three constant carry exclusions, checked by additional actual-predicate AST
SMT obligations, eliminate safe correction variables:

- Addition with either constant operand `c<=2^128-47` cannot lose the upper
  carry: its sum is below the first defective total `2^160+2^128-47`.
- Subtraction with a constant second operand `c<=p` cannot wrap twice.
- Subtraction with a constant first operand `c>=47` cannot wrap twice.

The addition bound has a concrete outside-boundary control: with
`c=2^128-46`, adding `2^160-1` does defect, returning94 instead of the ordinary
residue `2^128`. Disabling that guard or forgetting representative lifts changes
outputs. The primitive-rule solver now requires all9 obligations to be UNSAT;
UNKNOWN or timeout remains failure.

Across all320 source stage alternatives,20129 guards remain and1584 constant
carry sites are excluded. With the default256-term limit, the preliminary
all-stage compilation required252 anchors (at most13 in one stage); the fixed
tail requires more. These are plan-specific structure counts, not a ratio of
runtime cost saved. In the public-base-point effective-scalar-zero full-output
control, three real defects remain unchanged and only four guards need exact
carry/lift decisions. Necessary guard formulas are still evaluated for the
other retained sites. No faster-performance claim is made.

The independent structural validator recomputes correction frontiers, checks
anchor acyclicity, checks guard/input/tag inventories and enforces polynomial
bounds. Every carry guard refers only to earlier, already-finalized correction
values; every source field refers at most to its own correction. Thus lazily
cached anchor and field values need no runtime invalidation. This is a
structural check, **not an algebraic-equivalence or whole-compiler SMT proof**.
Output fields above46 have unique representatives; ambiguous small fields
retain on-demand source-dependent lift rules, including the proved zero-tag
shortcuts. The source tag dependency metadata is compiled once, not replayed
as a complete numerical arithmetic program.

The permanent controls cover all320 alternatives with2560 boundary/random
layouts, exact output and carry-event equality, all scalar boundaries, full
72-byte results, arbitrary sources, the on-curve point-changing carry example,
and term bounds2/8/64/256. Runtime evaluation also succeeds when old arithmetic,
the earlier SSA/polynomial executors, and polynomial construction/repair helpers
are patched to throw. Corrupted frontiers, forward correction reads and anchor
cycles fail the structural checks.

For readability, ``python -m tools.scalar_stage_plan --stage 80 --branch 1``
prints named output field equations, anchors, carry-site tape provenance and
field carry dependencies. `s<slot>` is an input residue, `e<SSA>` a correction,
and `f<index>` a bounded formula anchor. Field-only carry dependencies do not
include every indirect dependency of the carry decisions or lift rules; they
must not be mistaken for a complete exact-representative dependency trace.

This advances stage-level reconstruction from an instruction interpreter to
bounded carry/tag/output formulas, including the difficult initial and tail
groups. The plans are still source-specific and retain many guards and some
lift dependencies. Compressing their feasible guard conditions and translating
them into a small, independently understandable stage recurrence remains open.
Runtime code, wire behavior, binary fixtures and hardware-validation boundaries
are unchanged.
