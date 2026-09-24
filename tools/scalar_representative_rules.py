"""Standalone exact uint160 arithmetic using field residues and one lift bit.

Research only: no source SSA, tape, curve assumptions, or runtime changes.
A lift bit is legal only for residues 0..46. The three-fold product oracle
remains independent; this model uses a modular product and a Boolean lift.
"""

from __future__ import annotations

from dataclasses import dataclass

from tools import transform12_residue_defects as arithmetic

MODULUS = arithmetic.P


def addition_constant_safe(c: int) -> bool:
    """Either uint160 operand is this constant: a defect is impossible."""
    return c <= arithmetic.LOW_LIMIT - 47


def subtraction_right_constant_safe(c: int) -> bool:
    """Subtracting a constant at most p cannot require a second wrap."""
    return c <= MODULUS


def subtraction_left_constant_safe(c: int) -> bool:
    """A constant first operand at least47 prevents a second wrap."""
    return c >= 47


def addition_defect(s: int, k: int) -> bool:
    """s is the residue sum; k is the number of lifted operands."""
    return (
        k == 0
        and s >= MODULUS + 47
        and s % arithmetic.LOW_LIMIT >= arithmetic.LOW_LIMIT - 47
        or k == 1
        and s >= 47
        and s % arithmetic.LOW_LIMIT < 47
        or k == 2
        and s >= 47
    )


def addition_tag(s: int, k: int, defective: bool) -> bool:
    """A defective sum is never p-lifted; the remaining cases are intervals."""
    return not defective and (k == 0 and MODULUS <= s < MODULUS + 47 or k == 1 and (s < 47 or s >= MODULUS) or k == 2 and s < 47)


def subtraction_defect(a: int, b: int, ta: bool, tb: bool) -> bool:
    """Exactly the canonical-small minus larger p-lifted-small case."""
    return not ta and tb and a < b


def subtraction_tag(a: int, b: int, ta: bool, tb: bool) -> bool:
    """Positive p-lifted difference, or the exceptional second wrap."""
    return ta and not tb and a >= b or not ta and tb and a < b


@dataclass(frozen=True)
class Representative:
    residue: int
    lifted: bool = False

    def __post_init__(self) -> None:
        if type(self.residue) is not int or not 0 <= self.residue < MODULUS:
            raise ValueError("canonical residue required")
        if type(self.lifted) is not bool or self.lifted and self.residue > 46:
            raise ValueError("a Boolean lift is permitted only for residues 0..46")

    @classmethod
    def from_integer(cls, value: int) -> Representative:
        arithmetic.validate(value, 0)
        return cls(value % MODULUS, value >= MODULUS)

    def integer(self) -> int:
        return self.residue + MODULUS * self.lifted


def add(a: Representative, b: Representative) -> tuple[Representative, int]:
    s, k = a.residue + b.residue, int(a.lifted) + int(b.lifted)
    defective = addition_defect(s, k)
    correction = arithmetic.ADD_DEFECT if defective else 0
    return Representative((s + correction) % MODULUS, addition_tag(s, k, defective)), correction


def subtract(a: Representative, b: Representative) -> tuple[Representative, int]:
    correction = 47 if subtraction_defect(a.residue, b.residue, a.lifted, b.lifted) else 0
    return Representative(
        (a.residue - b.residue + correction) % MODULUS,
        subtraction_tag(a.residue, b.residue, a.lifted, b.lifted),
    ), correction


def multiply(a: Representative, b: Representative) -> Representative:
    product = a.residue * b.residue
    residue = product % MODULUS
    positive_a, positive_b = a.residue != 0 or a.lifted, b.residue != 0 or b.lifted
    lifted = residue <= 46 and positive_a and positive_b and (a.lifted or b.lifted or product >= MODULUS)
    return Representative(residue, lifted)
