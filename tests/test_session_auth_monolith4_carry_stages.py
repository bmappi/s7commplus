"""Dependency-free controls for proof accounting and generalized cone safety."""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from tools.prove_monolith4_carry_stages import abstract_cone, proof_progress, prove


class Node:
    def __init__(self, factory: Factory, operation: str, name: str, args: tuple[Node, ...], identifier: int) -> None:
        self.factory, self.operation, self.name, self.args, self.identifier = factory, operation, name, args, identifier

    def get_id(self) -> int:
        return self.identifier

    def children(self) -> tuple[Node, ...]:
        return self.args

    def decl(self) -> Any:
        return lambda *args: self.factory.make(self.operation, self.name, args)

    def evaluate(self, values: dict[str, bool]) -> bool:
        if self.operation == "var":
            return values[self.name]
        if self.operation == "const":
            return self.name == "1"
        args = [arg.evaluate(values) for arg in self.args]
        if self.operation == "and":
            return all(args)
        if self.operation == "xor":
            return sum(args) % 2 == 1
        if self.operation == "not":
            return not args[0]
        raise AssertionError("unknown test operation")


class Factory:
    def __init__(self) -> None:
        self.nodes: dict[tuple[str, str, tuple[Node, ...]], Node] = {}

    def make(self, operation: str, name: str = "", args: tuple[Node, ...] = ()) -> Node:
        key = operation, name, args
        if key not in self.nodes:
            self.nodes[key] = Node(self, operation, name, args, len(self.nodes))
        return self.nodes[key]

    def Bool(self, name: str) -> Node:
        return self.make("var", name)

    @staticmethod
    def is_true(node: Node) -> bool:
        return node.operation == "const" and node.name == "1"

    @staticmethod
    def is_false(node: Node) -> bool:
        return node.operation == "const" and node.name == "0"


def specialize(cuts: dict[int, Node], assignment: dict[str, bool]) -> dict[str, bool]:
    return {**assignment, **{f"cut_{identifier}": node.evaluate(assignment) for identifier, node in cuts.items()}}


def test_shared_cuts_and_refinement_preserve_every_original_assignment() -> None:
    factory = Factory()
    a, b, c = [factory.Bool(name) for name in ("a", "b", "c")]
    shared = factory.make("and", args=(b, c))
    root = factory.make("xor", args=(factory.make("and", args=(a, shared)), shared))
    local = frozenset({a.get_id()})
    generalized, cuts = abstract_cone(factory, root, local)
    assert set(cuts) == {shared.get_id()}
    expanded = frozenset(cuts)
    refined, refined_cuts = abstract_cone(factory, root, local, expanded)
    assert set(refined_cuts) == {b.get_id(), c.get_id()}
    exact, exact_cuts = abstract_cone(factory, root, local, expanded | refined_cuts.keys())
    assert exact is root and not exact_cuts
    for bits in itertools.product((False, True), repeat=3):
        assignment = dict(zip(("a", "b", "c"), bits))
        assert generalized.evaluate(specialize(cuts, assignment)) == root.evaluate(assignment)
        assert refined.evaluate(specialize(refined_cuts, assignment)) == root.evaluate(assignment)


def test_generalized_sat_can_be_spurious_and_constants_are_not_cut() -> None:
    factory = Factory()
    a, b = factory.Bool("a"), factory.Bool("b")
    double_not = factory.make("not", args=(factory.make("not", args=(b,)),))
    root = factory.make("xor", args=(factory.make("and", args=(a, b)), factory.make("and", args=(a, double_not))))
    generalized, cuts = abstract_cone(factory, root, frozenset({a.get_id()}))
    assert len(cuts) == 2
    assert all(not root.evaluate(dict(zip(("a", "b"), bits))) for bits in itertools.product((False, True), repeat=2))
    assert generalized.evaluate({"a": True, f"cut_{b.get_id()}": True, f"cut_{double_not.get_id()}": False})
    for value in ("0", "1"):
        constant = factory.make("const", value)
        result, constant_cuts = abstract_cone(factory, constant, frozenset())
        assert result is constant and not constant_cuts


def test_progress_never_counts_beyond_a_gap_or_completes_a_partial_run() -> None:
    assert proof_progress([], 0, 169) == (0, False)
    assert proof_progress([{"proved": True}] * 2, 0, 169) == (1, False)
    rows = [{"proved": True}] * 31 + [{"proved": False}, {"proved": True}]
    assert proof_progress(rows, 0, 169) == (30, False)
    assert proof_progress([{"proved": True}] * 169, 0, 169) == (168, True)
    assert proof_progress([{"proved": True}] * 168, 0, 168) == (167, False)
    assert proof_progress([{"proved": True}] * 5, 10, 15) == (0, False)


@pytest.mark.parametrize(
    "kwargs", ({"timeout_ms": 0}, {"refinements": -1}, {"start": -1}, {"stop": 170}, {"start": 5, "stop": 5})
)
def test_prover_rejects_invalid_limits_before_loading_optional_solver(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="positive timeout"):
        prove(**kwargs)
