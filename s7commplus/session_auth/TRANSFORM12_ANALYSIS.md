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

## Verification

Tests compare all 498 decoded programs byte-for-byte with the tape interpreter,
exercise aliased assignments, trace selected outputs, and compare the composed
second phase with all 89 runtime dispatches using mixed branch choices. The
catalogue test verifies prefix coverage, the excluded suffix, and all identical
branch pairs. Malformed ranges and buffer references are rejected.

The catalogue records SHA-256 hashes of both binary resources, so reports can
be associated with the exact analyzed revision. Preserve the HarpoS7 attribution
and `LICENSE-HarpoS7` when reusing the derived equations or tooling.
