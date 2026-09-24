"""Compile source-specific scalar stages into bounded field/carry formulas.

Explicit correction variables preserve nonlinear interactions. Polynomial
anchors bound expansion at compile time. Runtime visits carry guards and lazy
lift dependencies, not arithmetic instructions or repair traversals. This is
still a source-specific research plan, NOT an independent compact curve ladder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from s7commplus.session_auth.family0._generated.data import TRANSFORM7_DATA, TRANSFORM12_BIG_INT_DATA
from tools import scalar_representative_rules as rules
from tools import transform12_integer_model as packing
from tools.decompile_transform12 import Instruction, Operand, Program, external_operands
from tools.predict_scalar_defects import addition_possible, subtraction_possible
from tools.recover_scalar_encodings import scalar_xor_mask
from tools.recover_transform12_phase1 import recover as stages
from tools.trace_scalar_defects import Defect
from tools.transform7_reference import finalize, tail_program
from tools.transform7_setup_integer import model as setup

P = rules.MODULUS
Monomial = tuple[tuple[int, int], ...]  # Sparse (variable ID, exponent) pairs.
Polynomial = dict[Monomial, int]


@dataclass(frozen=True)
class Binding:
    kind: str  # input, correction, or anchor
    index: int


@dataclass(frozen=True)
class Guard:
    instruction: Instruction
    before: Polynomial
    operands: tuple[Polynomial, Polynomial]


@dataclass(frozen=True)
class Plan:
    program: Program
    tag_sources: dict[int, Instruction]
    input_slots: tuple[int, ...]
    fields: dict[int, Polynomial]
    guards: tuple[Guard, ...]
    bindings: tuple[Binding, ...]
    anchors: tuple[Polynomial, ...]
    frontiers: tuple[int, ...]
    excluded_guards: int
    max_terms: int


@dataclass(frozen=True)
class Evaluation:
    outputs: dict[int, int]
    defects: tuple[Defect, ...]
    defect_values: tuple[int, ...]
    guards: int
    potential_guards: int
    anchors_evaluated: int
    fields_evaluated: int
    tag_rules: int


def constant(operand: Operand) -> int:
    offset = operand.index * 24
    return packing.decode(TRANSFORM12_BIG_INT_DATA[offset : offset + 24])


def fixed(value: int) -> Polynomial:
    value %= P
    return {(): value} if value else {}


def variable(index: int) -> Polynomial:
    return {((index, 1),): 1}


def combine(a: Polynomial, b: Polynomial, sign: int = 1) -> Polynomial:
    result = dict(a)
    for monomial, coefficient in b.items():
        value = (result.get(monomial, 0) + sign * coefficient) % P
        if value:
            result[monomial] = value
        else:
            result.pop(monomial, None)
    return result


def product(a: Polynomial, b: Polynomial, max_terms: int) -> Polynomial:
    if len(a) * len(b) > max_terms * 16:
        raise ValueError("polynomial work bound exceeded")
    result: Polynomial = {}
    for first, ac in a.items():
        for second, bc in b.items():
            powers = dict(first)
            for index, exponent in second:
                powers[index] = powers.get(index, 0) + exponent
            monomial = tuple(sorted(powers.items()))
            value = (result.get(monomial, 0) + ac * bc) % P
            if value:
                result[monomial] = value
            else:
                result.pop(monomial, None)
            if len(result) > max_terms:
                raise ValueError("polynomial term bound exceeded")
    return result


def operation(name: str, a: Polynomial, b: Polynomial, max_terms: int) -> Polynomial:
    if name in ("add", "subtract"):
        result = combine(a, b, -1 if name == "subtract" else 1)
    elif name in ("multiply", "square"):
        result = product(a, b, max_terms)
    else:
        raise ValueError("unsupported source operation")
    if len(result) > max_terms:
        raise ValueError("polynomial term bound exceeded")
    return result


def carry_safe(instruction: Instruction) -> bool:
    if instruction.operation not in ("add", "subtract"):
        return True
    a, b = instruction.operands[0], instruction.operands[-1]
    if instruction.operation == "add":
        return any(o.kind == "constant" and rules.addition_constant_safe(constant(o)) for o in (a, b))
    return (
        b.kind == "constant"
        and rules.subtraction_right_constant_safe(constant(b))
        or a.kind == "constant"
        and rules.subtraction_left_constant_safe(constant(a))
    )


@lru_cache(maxsize=4)
def compile_plan(program: Program, max_terms: int = 256) -> Plan:
    if type(max_terms) is not int or max_terms < 2:
        raise ValueError("polynomial term bound must be at least two")
    slots = tuple(o.index for o in external_operands(program) if o.kind == "input")
    bindings = [Binding("input", s) for s in slots]
    frontiers = [-1 for _ in slots]
    fields: dict[int, Polynomial] = {}
    guards = []
    anchors: list[Polynomial] = []
    anchor_keys: dict[tuple[tuple[Monomial, int], ...], int] = {}
    input_variables = {s: variable(i) for i, s in enumerate(slots)}
    excluded = 0

    def resolve(operand: Operand) -> Polynomial:
        if operand.kind == "value":
            return fields[operand.index]
        if operand.kind == "input":
            return input_variables[operand.index]
        return fixed(constant(operand))

    def frontier(poly: Polynomial) -> int:
        return max((frontiers[v] for m in poly for v, _ in m), default=-1)

    def anchor(poly: Polynomial) -> Polynomial:
        if not poly or len(poly) == 1 and next(iter(poly)) == ():
            return poly
        key = tuple(sorted(poly.items()))
        if key not in anchor_keys:
            index = len(bindings)
            anchor_keys[key] = index
            bindings.append(Binding("anchor", len(anchors)))
            frontiers.append(frontier(poly))
            anchors.append(poly)
        return variable(anchor_keys[key])

    for instruction in program.instructions:
        a, b = resolve(instruction.operands[0]), resolve(instruction.operands[-1])
        if max(frontier(a), frontier(b)) >= instruction.value:
            raise ValueError("source SSA is not in acyclic correction order")
        try:
            before = operation(instruction.operation, a, b, max_terms)
        except ValueError as error:
            if instruction.operation not in ("add", "subtract", "multiply", "square"):
                raise error
            a, b = anchor(a), anchor(b)
            before = operation(instruction.operation, a, b, max_terms)
        if carry_safe(instruction):
            fields[instruction.value] = before
            excluded += instruction.operation in ("add", "subtract")
        else:
            if len(before) == max_terms:
                before = anchor(before)
            guards.append(Guard(instruction, before, (a, b)))
            index = len(bindings)
            bindings.append(Binding("correction", instruction.value))
            frontiers.append(instruction.value)
            fields[instruction.value] = combine(before, variable(index))
    plan = Plan(
        program,
        {i.value: i for i in program.instructions},
        slots,
        fields,
        tuple(guards),
        tuple(bindings),
        tuple(anchors),
        tuple(frontiers),
        excluded,
        max_terms,
    )
    validate_order(plan)
    return plan


def validate_order(plan: Plan) -> None:
    """Independent structural check, not an algebraic-equivalence certificate.

    Every anchor refers backward; every guard refers only to finalized earlier
    corrections. This is the invariant that makes runtime caches repair-free.
    """
    frontiers: list[int] = []

    def frontier(poly: Polynomial, available: int) -> int:
        if len(poly) > plan.max_terms:
            raise ValueError("formula exceeds its declared term bound")
        result = -1
        for monomial, coefficient in poly.items():
            if type(coefficient) is not int or not 0 < coefficient < P or tuple(sorted(monomial)) != monomial:
                raise ValueError("noncanonical formula")
            seen = set()
            for variable_id, exponent in monomial:
                if type(variable_id) is not int or not 0 <= variable_id < available:
                    raise ValueError("formula contains a forward variable reference")
                if type(exponent) is not int or exponent <= 0 or variable_id in seen:
                    raise ValueError("noncanonical formula monomial")
                seen.add(variable_id)
                result = max(result, frontiers[variable_id])
        return result

    expected_guards = tuple(i for i in plan.program.instructions if not carry_safe(i))
    if tuple(g.instruction for g in plan.guards) != expected_guards:
        raise ValueError("carry guard inventory mismatch")
    if plan.tag_sources != {i.value: i for i in plan.program.instructions} or set(plan.fields) != set(plan.tag_sources):
        raise ValueError("source field/tag inventory mismatch")
    inputs: list[int] = []
    corrections: list[int] = []
    anchors: list[int] = []
    for variable_id, binding in enumerate(plan.bindings):
        if binding.kind == "input":
            inputs.append(binding.index)
            frontiers.append(-1)
        elif binding.kind == "correction":
            corrections.append(binding.index)
            frontiers.append(binding.index)
        elif binding.kind == "anchor":
            if binding.index != len(anchors) or binding.index >= len(plan.anchors):
                raise ValueError("anchor inventory mismatch")
            anchors.append(binding.index)
            frontiers.append(frontier(plan.anchors[binding.index], variable_id))
        else:
            raise ValueError("unsupported formula binding")
    if tuple(inputs) != plan.input_slots or tuple(corrections) != tuple(i.value for i in expected_guards):
        raise ValueError("formula input/correction inventory mismatch")
    if len(anchors) != len(plan.anchors) or tuple(frontiers) != plan.frontiers:
        raise ValueError("formula frontier inventory mismatch")
    for guard in plan.guards:
        if max(frontier(p, len(frontiers)) for p in (guard.before, *guard.operands)) >= guard.instruction.value:
            raise ValueError("guard depends on an unresolved correction")
    for value, poly in plan.fields.items():
        if frontier(poly, len(frontiers)) > value:
            raise ValueError("source field depends on a future correction")


def evaluate(plan: Plan, state: dict[int, int], index: int = 160, bit: int = 0) -> Evaluation:
    if bit not in (0, 1) or set(state) != set(plan.input_slots):
        raise ValueError("stage input layout or branch mismatch")
    inputs = {s: rules.Representative.from_integer(v) for s, v in state.items()}
    instructions = plan.tag_sources
    corrections: dict[int, int] = {}
    anchors: dict[int, int] = {}
    fields: dict[int, int] = {}
    representatives: dict[int, int] = {}
    tags = 0

    def field(poly: Polynomial) -> int:
        total = 0
        for monomial, coefficient in poly.items():
            term = coefficient
            for variable_id, exponent in monomial:
                binding = plan.bindings[variable_id]
                if binding.kind == "input":
                    value = inputs[binding.index].residue
                elif binding.kind == "correction":
                    if binding.index not in corrections:
                        raise ValueError("formula reads an unresolved correction")
                    value = corrections[binding.index] % P
                elif binding.kind == "anchor":
                    if binding.index not in anchors:
                        anchors[binding.index] = field(plan.anchors[binding.index])
                    value = anchors[binding.index]
                else:
                    raise ValueError("unsupported formula binding")
                term = term * pow(value, exponent, P) % P
            total += term
        return total % P

    def residue(operand: Operand) -> int:
        if operand.kind == "input":
            return inputs[operand.index].residue
        if operand.kind == "constant":
            return constant(operand) % P
        if operand.index not in fields:
            fields[operand.index] = field(plan.fields[operand.index])
        return fields[operand.index]

    def representative(operand: Operand) -> int:
        nonlocal tags
        if operand.kind == "input":
            return state[operand.index]
        if operand.kind == "constant":
            return constant(operand)
        if operand.index not in representatives:
            value = residue(operand)
            if value > 46:
                representatives[operand.index] = value
            else:
                instruction = instructions[operand.index]
                first, last = instruction.operands[0], instruction.operands[-1]
                if value == 0:

                    def positive(o: Operand) -> bool:
                        return residue(o) != 0 or representative(o) != 0

                    if instruction.operation in ("multiply", "square"):
                        lifted = positive(first) and positive(last)
                    elif instruction.operation == "add":
                        lifted = positive(first) or positive(last)
                    else:
                        lifted = representative(first) > representative(last)
                    representatives[operand.index] = P if lifted else 0
                else:
                    a = rules.Representative.from_integer(representative(first))
                    b = rules.Representative.from_integer(representative(last))
                    if instruction.operation in ("multiply", "square"):
                        lifted = (
                            (a.residue != 0 or a.lifted)
                            and (b.residue != 0 or b.lifted)
                            and (a.lifted or b.lifted or a.residue * b.residue >= P)
                        )
                    elif instruction.operation == "add":
                        lifted = rules.addition_tag(
                            a.residue + b.residue, int(a.lifted) + int(b.lifted), corrections.get(operand.index, 0) != 0
                        )
                    else:
                        lifted = rules.subtraction_tag(a.residue, b.residue, a.lifted, b.lifted)
                    representatives[operand.index] = value + (P if lifted else 0)
                tags += 1
        return representatives[operand.index]

    events = []
    event_values = []
    potentials = 0
    for guard in plan.guards:
        instruction = guard.instruction
        if instruction.operation == "add":
            possible = addition_possible(field(guard.before))
        else:
            possible = subtraction_possible(field(guard.operands[0]), field(guard.operands[1]))
        correction = 0
        if possible:
            potentials += 1
            a, b = (representative(o) for o in instruction.operands)
            result, correction = (rules.add if instruction.operation == "add" else rules.subtract)(
                rules.Representative.from_integer(a), rules.Representative.from_integer(b)
            )
            if correction:
                events.append(
                    Defect(index, bit, instruction.tape_index, instruction.operation, (a, b), result.integer(), correction)
                )
                event_values.append(instruction.value)
        corrections[instruction.value] = correction
    outputs = {s: representative(o) for s, o in plan.program.outputs}
    return Evaluation(outputs, tuple(events), tuple(event_values), len(plan.guards), potentials, len(anchors), len(fields), tags)


def full_output(x: int, y: int, prng1: int, scalar: int, max_terms: int = 256) -> tuple[bytes, tuple[Evaluation, ...]]:
    for value in (x, y, prng1, scalar):
        rules.Representative.from_integer(value)
    state = dict(zip(stages()[0].inputs, setup(x, y, prng1).slots))
    rows = []
    for stage in stages():
        bit = scalar >> (159 - stage.index) & 1
        row = evaluate(compile_plan(stage.choices[bit], max_terms), state, stage.index, bit)
        state = row.outputs
        rows.append(row)
    tail = evaluate(compile_plan(tail_program(), max_terms), state)
    return finalize(tail.outputs), tuple(rows) + (tail,)


def describe(plan: Plan) -> dict[str, object]:
    """Readable output equations and error provenance, without input material."""
    validate_order(plan)
    names = tuple({"input": "s", "correction": "e", "anchor": "f"}[b.kind] + str(b.index) for b in plan.bindings)

    def render(poly: Polynomial) -> str:
        terms = []
        for monomial, coefficient in sorted(poly.items()):
            coefficient = coefficient if coefficient <= P // 2 else coefficient - P
            factors = [names[v] + (f"**{exponent}" if exponent != 1 else "") for v, exponent in monomial]
            if coefficient != 1 or not factors:
                factors.insert(0, str(coefficient))
            terms.append("*".join(factors))
        return "(" + " + ".join(terms or ["0"]) + ") % p"

    def error_dependencies(poly: Polynomial) -> tuple[int, ...]:
        errors = set()
        for monomial in poly:
            for v, _ in monomial:
                binding = plan.bindings[v]
                if binding.kind == "correction":
                    errors.add(binding.index)
                elif binding.kind == "anchor":
                    errors.update(anchor_errors(binding.index))
        return tuple(sorted(errors))

    @lru_cache(maxsize=None)
    def anchor_errors(index: int) -> tuple[int, ...]:
        return error_dependencies(plan.anchors[index])

    def operand_field(operand: Operand) -> Polynomial:
        if operand.kind == "value":
            return plan.fields[operand.index]
        if operand.kind == "constant":
            return fixed(constant(operand))
        variable_id = plan.bindings.index(Binding("input", operand.index))
        return variable(variable_id)

    return {
        "scope": "source-specific field equations, explicit carry provenance; representative lift rules remain separate; NOT compact curve algorithm",
        "modulus": P,
        "symbol_legend": "s<slot>: input residue; e<SSA>: carry correction modulo p; f<index>: bounded formula anchor",
        "source_instructions": len(plan.program.instructions),
        "excluded_constant_carry_sites": plan.excluded_guards,
        "max_terms": plan.max_terms,
        "anchors": {f"f{i}": render(poly) for i, poly in enumerate(plan.anchors)},
        "carry_sites": [
            {
                "symbol": f"e{g.instruction.value}",
                "tape_index": g.instruction.tape_index,
                "operation": g.instruction.operation,
                "possible_corrections": (0, arithmetic_correction(g.instruction.operation)),
            }
            for g in plan.guards
        ],
        "outputs": {
            str(slot): {
                "field_formula": render(operand_field(operand)),
                "carry_dependencies": error_dependencies(operand_field(operand)),
                "lift_dependency": (operand.kind, operand.index),
                "representative_rule": "r is unique above46; otherwise retain the source-dependent p-lift bit",
            }
            for slot, operand in plan.program.outputs
        },
    }


def arithmetic_correction(operation: str) -> int:
    return 94 - (1 << 128) if operation == "add" else 47


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effective-scalar", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--prng1", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--max-terms", type=int, default=256)
    parser.add_argument(
        "--stage", type=int, choices=range(160), help="describe one stage instead of evaluating a synthetic input"
    )
    parser.add_argument("--branch", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    if not 0 <= args.effective_scalar < 1 << 160 or not 0 <= args.prng1 < 1 << 160 or args.max_terms < 2:
        parser.error("unsigned160 synthetic inputs and a term bound of at least two required")
    if args.stage is not None:
        print(json.dumps(describe(compile_plan(stages()[args.stage].choices[args.branch], args.max_terms)), indent=2))
        return
    x, y = (int.from_bytes(TRANSFORM7_DATA[o : o + 20], "little") for o in (0xD8, 0xEC))
    output, rows = full_output(x, y, args.prng1, args.effective_scalar ^ scalar_xor_mask(), args.max_terms)
    from tools.predict_scalar_defects import source_hashes

    hashes = source_hashes()
    hashes["tools/scalar_stage_plan.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "scope": "source-specific bounded carry/tag/output formulas; NOT independent compact ladder or whole-pipeline SMT proof",
                "destination_hex": output.hex(),
                "defects": [e.__dict__ for row in rows for e in row.defects],
                "full_numeric_instruction_replay": False,
                "polynomial_repairs": 0,
                "guard_formulas": sum(row.guards for row in rows),
                "potential_guards": sum(row.potential_guards for row in rows),
                "anchors_evaluated": sum(row.anchors_evaluated for row in rows),
                "fields_evaluated": sum(row.fields_evaluated for row in rows),
                "tag_rules": sum(row.tag_rules for row in rows),
                "max_terms": args.max_terms,
                "source_sha256": hashes,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
