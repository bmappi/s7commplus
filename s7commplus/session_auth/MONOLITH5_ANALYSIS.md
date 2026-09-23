# Monolith5: bit-lane dependency map

This is an analysis of the pinned, generated Family-0 Monolith5, not a runtime
replacement or a claim about the proprietary DLL. Source and destination are
little-endian 32-bit words, numbered from zero.

Monolith5 consumes 54 source words and produces 12 output words. Its generated
body is mostly bitwise logic, but unlike Monolith11 it contains fixed shifts
and multiplications by two. The bitwise-only truth-table method therefore does
not apply directly. `tools/trace_session_auth_bits.py` follows every output
bit through the versioned backward slice, including constant masks, logical
right shifts, left shifts, and power-of-two multiplication modulo 2³².

For every output word, bits 0, 1, 30, and 31 have **no source-bit dependency**.
They are zero in the generated implementation's zero-input vector and in the
included perturbation tests. Output word 6 also has no source dependency at
bit 2. These are structural observations, not field-format assignments.

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
and 36–38. These are conservative *bit-level* dependencies: cancellation can
remove an input, so the table is not a minimal support proof. It does show
that the 18–36 source words in the earlier word-level slices can be narrowed
to specific source-bit lanes for each output bit.

Run the detailed trace with:

```bash
python -m tools.trace_session_auth_bits 5 0
python -m tools.trace_session_auth_bits 5 0 --json
```

The test suite checks all 12 output-word maps, verifies constant/mask/shift
handling on small expressions, and flips 100 seeded source bits through the
generated Monolith5. Any output bit that changes must list that source bit in
the trace. This is a check against missed dependencies, not proof that every
listed dependency is essential. A compact equivalent expression will require
further algebraic reduction and independent equivalence testing.
