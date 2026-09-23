# Monolith7: exact recovery of two output triplets

This is a deliberately **partial** analysis of the pinned, generated Family-0
Monolith7. The runtime implementation and on-wire behavior are unchanged.

Monolith7 consumes 24 little-endian source words and produces 36 destination
words. The exact models cover output words 3–5 and 15–17: 192 of the 1,152
output bits.

## Recovered formula

Every bit of words 15–17 is one of 63 distinct Boolean functions
of at most ten selected source bits:

```text
destination[word].bit[bit] = LUT_f( selected source[word].bit values )
```

The selected source-bit references and truth-table function ID for all 96
output bits are recorded in `tools/monolith7_tail_model.json`. The independent
analysis-only evaluator is `tools/monolith7_tail_model.py`. Some output bits
are constant; others depend on same-position or neighboring source-bit lanes.
These are the last three words of the first 18-word output passed through
`monolith7_with_copy`. Their backward slices each contain only 29 generated
assignments and read source words 5, 15, and 21–23.

Words 3–5 have much larger backward slices: 193 generated assignments per
word, reading 17 source words. Nevertheless, their 96 output bits reduce to
68 distinct normalized algebraic normal forms (ANFs), each involving at most
14 essential source bits. The exact per-bit formula is:

```text
assignment = selected source-bit values packed in selector order
destination[word].bit[bit] = XOR_{term in ANF_f} AND_{i in term} assignment.bit[i]
```

The 68 shared functions and 96 source-bit selectors are saved in
`tools/monolith7_middle_model.json`; the independent evaluator is
`tools/monolith7_middle_model.py`. A term mask of zero denotes the constant one.
The factored JSON model is about 13.4 KB versus about 102 KB for the entire generated
Monolith7 Python file. This is a compact *partial* mathematical description,
not an identification of the algorithm's original cryptographic design.
No model here covers the other 30 output words.

## Shared conditional-selection and majority structure

The 68 functions for words 3–5 further decompose into eight shared cores:

```text
choose(a,b,c)          = b XOR ((a XOR b) AND c)
majority(a,b,c)        = (a AND b) XOR (a AND c) XOR (b AND c)
xor2(a,b)             = a XOR b
xor3(a,b,c)           = a XOR b XOR c
mux_xor(a,b,c,d)      = choose(a,b,c) XOR d
gated_choose(a,b,c,d) = a AND choose(b,c,d)
gated_majority(a,b,c,d) = a AND majority(b,c,d)
majority_xor(a,b,c,d) = a XOR majority(b,c,d)
```

`choose` selects `a` when `c` is one and `b` otherwise. `majority` is one
when at least two inputs are one. Input permutations and inversions account
for variants of these cores. Every saved function needs at most five core
calls followed by an ANF with at most four terms. The 2,324 monomials in the
previous shared ANFs become 190 outer terms plus 25 terms in the eight shared
cores; the model also records 211 core calls across the 68 functions.

For example, output word 3 bit 8 originally has 55 ANF monomials. Its recovered
formula is (`s[w].bit[b]` denotes one source bit):

```text
r = mux_xor(s[6].bit[0], s[7].bit[0], s[8].bit[0], s[0].bit[2])
m = s[1].bit[14] AND majority(NOT s[10].bit[8], s[9].bit[8], s[11].bit[8])
t = m XOR mux_xor(NOT s[9].bit[9], s[11].bit[9], s[10].bit[9], s[1].bit[15])
destination[3].bit[8] = NOT (r OR t)
```

Inspect the source-bit selectors and named formula for any recovered bit:

```bash
python -m tools.recover_monolith7_middle --formula 3 8
```

The reusable `tools/decompose_boolean_polynomial.py` groups each ANF by
monomials in the inputs outside a candidate subset. If the nonconstant part
of every subset coefficient is the same function `Q`, the ANF is exactly
`A XOR Q*B`. Replacing that subset with `Q` removes inputs from the outer
function. Repeating the process discovers the shared cores; exhaustive small
truth tables recognize each core under input permutation and inversion.
Every factored function is expanded back into its unique original ANF during
recovery, so the structural interpretation is checked algebraically.

## Further per-bit analysis

`tools/analyze_symbolic_monolith.py` can inspect any supported single-file
generated output bit. It follows the versioned backward slice, uses the
conservative bit trace to select candidate inputs, and symbolically evaluates
the complete Boolean function with a reduced ordered binary decision diagram
(ROBDD). Its unique algebraic normal form (ANF) reveals exact essential inputs,
term count, and degree. For example:

```bash
python -m tools.analyze_symbolic_monolith 7 15 20
python -m tools.analyze_symbolic_monolith 7 15 20 --json --monomials
```

Whole-word BDD construction for Monolith7 can grow beyond the analysis cap
because it carries hundreds of candidate source bits at once. Per-bit analysis
keeps this exact and tractable. Many remaining output bits have denser ANFs;
the reusable analyzer provides a way to select further small targets,
not a claim that the complete Monolith7 has been simplified.

## Equivalence and limits

Both checked-in models are deterministically regenerated from their selected
bits in the pinned generated source. Verify them with:

```bash
python -m tools.recover_monolith7_tail --verify tools/monolith7_tail_model.json
python -m tools.recover_monolith7_middle --verify tools/monolith7_middle_model.json
```

The test suite compares every saved truth table or ANF and selector with the
symbolic derivation, checks the upstream known-answer vectors, and differentially
compares seeded random inputs against the generated implementation. The
decomposition tests use exhaustive truth tables for
small functions, including a composed conditional-selection/majority formula.
The generic analyzer is also checked on selected bits outside the recovered
groups. Equivalence is to the
pinned generated Python within the supported uint32 expression and sound
backward-slice model; it is not a statement about every Siemens DLL or PLC.
