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

The 68 shared ANFs and 96 source-bit selectors are saved in
`tools/monolith7_middle_model.json`; the independent evaluator is
`tools/monolith7_middle_model.py`. An empty term denotes the constant one.
The JSON model is about 18 KB versus about 102 KB for the entire generated
Monolith7 Python file. This is a compact *partial* mathematical description,
not an identification of the algorithm's original cryptographic design.
No model here covers the other 30 output words.

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
compares seeded random inputs against the generated implementation. It
also checks selected bits outside the recovered groups, so the generic
analyzer is not tested only on its easiest target. Equivalence is to the
pinned generated Python within the supported uint32 expression and sound
backward-slice model; it is not a statement about every Siemens DLL or PLC.
