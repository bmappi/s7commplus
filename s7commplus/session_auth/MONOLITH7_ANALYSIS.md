# Monolith7: exact recovery of one output triplet

This is a deliberately **partial** analysis of the pinned, generated Family-0
Monolith7. The runtime implementation and on-wire behavior are unchanged.

Monolith7 consumes 24 little-endian source words and produces 36 destination
words. Output words 15–17 are the last three words of the first 18-word output
passed through `monolith7_with_copy`. Their backward slices each contain only
29 generated assignments and read source words 5, 15, and 21–23.

## Recovered formula

Every bit of these three output words is one of 63 distinct Boolean functions
of at most ten selected source bits:

```text
destination[word].bit[bit] = LUT_f( selected source[word].bit values )
```

The selected source-bit references and truth-table function ID for all 96
output bits are recorded in `tools/monolith7_tail_model.json`. The independent
analysis-only evaluator is `tools/monolith7_tail_model.py`. Some output bits
are constant; others depend on same-position or neighboring source-bit lanes.
This model does **not** cover the other 33 Monolith7 output words.

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
keeps this exact and tractable. Output words outside this triplet have denser
ANFs; the reusable analyzer provides a way to select further small targets,
not a claim that the complete Monolith7 has been simplified.

## Equivalence and limits

The checked-in tail model is deterministically regenerated from all 96 bits
of the pinned generated source. Verify it with:

```bash
python -m tools.recover_monolith7_tail --verify tools/monolith7_tail_model.json
```

The test suite compares every saved truth table and selector with the symbolic
derivation, checks the upstream known-answer vector, and differentially
compares 100 seeded random inputs against the generated implementation. It
also checks selected bits outside the recovered triplet, so the generic
analyzer is not tested only on its easiest target. Equivalence is to the
pinned generated Python within the supported uint32 expression and sound
backward-slice model; it is not a statement about every Siemens DLL or PLC.
