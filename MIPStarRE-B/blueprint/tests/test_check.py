"""Adversarial tests for the deterministic QPBT blueprint checker."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("blueprint_check", ROOT / "check.py")
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)
PDF_SPEC = importlib.util.spec_from_file_location("blueprint_check_pdf", ROOT / "check_pdf.py")
assert PDF_SPEC and PDF_SPEC.loader
check_pdf = importlib.util.module_from_spec(PDF_SPEC)
PDF_SPEC.loader.exec_module(check_pdf)


def load(name: str):
    return json.loads((ROOT / "metadata" / name).read_text(encoding="utf-8"))


class BlueprintCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nodes = load("nodes.json")
        self.gaps = load("gaps.json")
        self.externals = load("external-sources.json")

    def errors(self, nodes=None, gaps=None, externals=None):
        return check.validate_data(
            nodes or self.nodes, gaps or self.gaps, externals or self.externals
        )

    def test_canonical_metadata_is_valid_and_every_target_reachable(self) -> None:
        self.assertEqual([], self.errors())
        graph = check.graph_document(self.nodes)
        self.assertEqual(len(self.nodes["nodes"]), len(graph["topological_order"]))
        for target in self.nodes["targets"].values():
            self.assertIn(target, graph["topological_order"])

    def test_every_target_name_and_contract_is_validated(self) -> None:
        for target_name in sorted(check.TARGET_KEYS):
            with self.subTest(target=target_name):
                bad = copy.deepcopy(self.nodes)
                bad["targets"][target_name] = "NOT-A-NODE"
                self.assertTrue(any(
                    f"targets.{target_name} must name an existing node" in error
                    for error in self.errors(nodes=bad)
                ))

        missing_key = copy.deepcopy(self.nodes)
        del missing_key["targets"]["binary"]
        self.assertTrue(any("targets must use the exact keys" in error
                            for error in self.errors(nodes=missing_key)))

        missing_contract = copy.deepcopy(self.nodes)
        del missing_contract["required_target_spines"]["completeness"]
        self.assertTrue(any("required_target_spines must use the exact keys" in error
                            for error in self.errors(nodes=missing_contract)))

        weakened_contract = copy.deepcopy(self.nodes)
        weakened_contract["required_target_spines"]["canonical_complexity"].remove(
            "K03B-LOW-DEGREE-COMPLEXITY"
        )
        self.assertTrue(any("canonical reachability contract" in error
                            for error in self.errors(nodes=weakened_contract)))

    def test_binary_and_complexity_targets_cannot_be_detached(self) -> None:
        cases = (
            ("B01-BINARY", "F10-PAULI-BINARY", "binary"),
            ("K04-GAME-COMPLEXITY", None, "canonical_complexity"),
        )
        for node_id, removed_dependency, target_name in cases:
            with self.subTest(node=node_id):
                bad = copy.deepcopy(self.nodes)
                node = next(node for node in bad["nodes"] if node["id"] == node_id)
                node["prerequisites"] = (
                    [] if removed_dependency is None else
                    [dep for dep in node["prerequisites"] if dep != removed_dependency]
                )
                by_id = {item["id"]: item for item in bad["nodes"]}
                prerequisites = {item["id"]: set(item["prerequisites"])
                                 for item in bad["nodes"]}
                node["transitive_definitions"] = check.definition_ancestor_ids(
                    node_id, by_id, prerequisites
                )
                self.assertTrue(any(
                    f"{target_name} target misses required spine" in error
                    for error in self.errors(nodes=bad)
                ))

    def test_minimal_skeleton_proof_debt_is_exact(self) -> None:
        expected = {
            "stage": "minimal",
            "sorry_count": 1,
            "sorry_declarations": ["MIPStarRE.QPBT.pauliSoundness"],
        }
        self.assertEqual(expected, self.nodes["skeleton_plan"])
        for mutation in (
            {**expected, "stage": "complete"},
            {**expected, "sorry_count": 2},
            {**expected, "sorry_declarations": ["MIPStarRE.QPBT.helper"]},
        ):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(self.nodes)
                bad["skeleton_plan"] = mutation
                self.assertTrue(any("exact minimal-skeleton proof debt" in error
                                    for error in self.errors(nodes=bad)))

    def test_duplicate_ids_and_lean_names_are_rejected(self) -> None:
        bad = copy.deepcopy(self.nodes)
        bad["nodes"][1]["id"] = bad["nodes"][0]["id"]
        bad["nodes"][1]["lean"]["names"] = bad["nodes"][0]["lean"]["names"]
        errors = self.errors(nodes=bad)
        self.assertTrue(any("duplicate node id" in error for error in errors))
        self.assertTrue(any("duplicate planned Lean declaration" in error for error in errors))

    def test_cycle_is_rejected(self) -> None:
        bad = copy.deepcopy(self.nodes)
        first = bad["nodes"][0]
        second = bad["nodes"][1]
        first["prerequisites"] = [second["id"]]
        second["prerequisites"] = [first["id"]]
        self.assertTrue(any("dependency cycle" in error for error in self.errors(nodes=bad)))

    def test_unknown_edge_and_missing_soundness_spine_are_rejected(self) -> None:
        bad = copy.deepcopy(self.nodes)
        soundness = next(node for node in bad["nodes"] if node["id"] == "S01-SOUNDNESS")
        soundness["prerequisites"] = []
        bad["nodes"][0]["prerequisites"] = ["NOT-A-NODE"]
        errors = self.errors(nodes=bad)
        self.assertTrue(any("unknown prerequisites" in error for error in errors))
        self.assertTrue(any("misses required spine" in error for error in errors))

    def test_repaired_node_requires_gap_and_reciprocal_link(self) -> None:
        bad = copy.deepcopy(self.nodes)
        repaired = next(node for node in bad["nodes"] if node["id"] == "A01-INDICATOR")
        repaired["gap_ids"] = []
        errors = self.errors(nodes=bad)
        self.assertTrue(any("repaired internal node must cite a gap" in error for error in errors))
        self.assertTrue(any("missing reciprocal link" in error for error in errors))

    def test_external_pin_must_include_exact_version(self) -> None:
        bad = copy.deepcopy(self.externals)
        bad["sources"][0]["arxiv"] = "1904.05870"
        self.assertTrue(any("arXiv version is not exact" in error
                            for error in self.errors(externals=bad)))

    def test_external_pin_contract_fields_must_agree(self) -> None:
        bad = copy.deepcopy(self.externals)
        tensor = next(source for source in bad["sources"] if source["id"] == "EXT-TENSOR")
        tensor["version"] = "v2"
        tensor["pin_contract"]["source_url"] = "https://arxiv.org/src/2111.08131v2"
        errors = self.errors(externals=bad)
        self.assertTrue(any("version disagrees" in error for error in errors))
        self.assertTrue(any("pin contract disagrees" in error for error in errors))

        missing = copy.deepcopy(self.externals)
        tensor = next(source for source in missing["sources"] if source["id"] == "EXT-TENSOR")
        del tensor["pin_contract"]
        self.assertTrue(any("published pin requires a pin contract" in error
                            for error in self.errors(externals=missing)))

    def test_tensor_external_contract_is_immutable(self) -> None:
        for version in ("v2", "v4"):
            with self.subTest(version=version):
                bad = copy.deepcopy(self.externals)
                tensor = next(source for source in bad["sources"]
                              if source["id"] == "EXT-TENSOR")
                arxiv = f"2111.08131{version}"
                tensor.update({
                    "arxiv": arxiv,
                    "version": version,
                    "url": f"https://arxiv.org/abs/{arxiv}",
                })
                tensor["pin_contract"].update({
                    "versioned_id": arxiv,
                    "metadata_url": f"https://arxiv.org/abs/{arxiv}",
                    "source_url": f"https://arxiv.org/src/{arxiv}",
                })
                self.assertTrue(any("authoritative contract must remain exact" in error
                                    for error in self.errors(externals=bad)))

        mutations = {
            "generic status": ("status", "pinned"),
            "authority": ("pin_contract.authority", "publisher mirror"),
            "last revised": ("pin_contract.last_revised", "2022-12-07"),
            "release": ("pin_contract.release", "draft"),
            "verification": ("pin_contract.verification_basis", "unverified"),
        }
        for name, (path, value) in mutations.items():
            with self.subTest(name=name):
                bad = copy.deepcopy(self.externals)
                tensor = next(source for source in bad["sources"]
                              if source["id"] == "EXT-TENSOR")
                if path.startswith("pin_contract."):
                    tensor["pin_contract"][path.removeprefix("pin_contract.")] = value
                else:
                    tensor[path] = value
                self.assertTrue(any("authoritative contract must remain exact" in error
                                    for error in self.errors(externals=bad)))

        downgraded = copy.deepcopy(self.externals)
        tensor = next(source for source in downgraded["sources"]
                      if source["id"] == "EXT-TENSOR")
        tensor["status"] = "pinned"
        del tensor["pin_contract"]
        self.assertTrue(any("authoritative contract must remain exact" in error
                            for error in self.errors(externals=downgraded)))

        renamed = copy.deepcopy(self.externals)
        next(source for source in renamed["sources"]
             if source["id"] == "EXT-TENSOR")["id"] = "EXT-TENSOR-RENAMED"
        self.assertTrue(any("authoritative external source missing: EXT-TENSOR" in error
                            for error in self.errors(externals=renamed)))

    def test_unresolved_soundness_external_is_rejected(self) -> None:
        bad = copy.deepcopy(self.externals)
        tensor = next(source for source in bad["sources"] if source["id"] == "EXT-TENSOR")
        tensor["status"] = "provisional-until-review"
        self.assertTrue(any("soundness-critical external source EXT-TENSOR is unresolved" in error
                            for error in self.errors(externals=bad)))

    def test_transitive_definitions_are_exact_definition_ancestor_closure(self) -> None:
        soundness = next(node for node in self.nodes["nodes"] if node["id"] == "S01-SOUNDNESS")
        by_id = {node["id"]: node for node in self.nodes["nodes"]}
        self.assertTrue(soundness["transitive_definitions"])
        self.assertTrue(all(by_id[node_id]["kind"] == "definition"
                            for node_id in soundness["transitive_definitions"]))

        missing = copy.deepcopy(self.nodes)
        next(node for node in missing["nodes"]
             if node["id"] == "S01-SOUNDNESS")["transitive_definitions"].pop()
        self.assertTrue(any("definition-ancestor closure" in error
                            for error in self.errors(nodes=missing)))

        theorem_injected = copy.deepcopy(self.nodes)
        next(node for node in theorem_injected["nodes"]
             if node["id"] == "R05-ROBUSTNESS")["transitive_definitions"].append(
                 "A15-UNITARY"
             )
        self.assertTrue(any("definition-ancestor closure" in error
                            for error in self.errors(nodes=theorem_injected)))

    def test_graph_derives_transitive_definitions(self) -> None:
        graph = check.graph_document(self.nodes)
        soundness = next(node for node in graph["nodes"] if node["id"] == "S01-SOUNDNESS")
        prerequisites = {node["id"]: set(node["prerequisites"])
                         for node in self.nodes["nodes"]}
        by_id = {node["id"]: node for node in self.nodes["nodes"]}
        expected = check.definition_ancestor_ids("S01-SOUNDNESS", by_id, prerequisites)
        self.assertEqual(expected, soundness["transitive_definitions"])

    def test_source_faithful_magic_square_edges(self) -> None:
        by_id = {node["id"]: node for node in self.nodes["nodes"]}
        prerequisites = {node_id: set(node["prerequisites"])
                         for node_id, node in by_id.items()}

        self.assertEqual(
            {"F03-MEASUREMENT", "F04-DISTANCE"},
            prerequisites["E01-ORTHO"],
        )
        self.assertEqual({"G02-GAME"}, prerequisites["G03-COMPLETENESS"])
        completeness_ancestors = check.dependency_ancestors(
            "G03-COMPLETENESS", prerequisites
        )
        self.assertIn("F08-MAGIC-GAME", completeness_ancestors)
        self.assertNotIn("E02-MAGIC-SQUARE", completeness_ancestors)

    def test_paper_index_repairs_and_complexity_anchors_are_explicit(self) -> None:
        by_id = {node["id"]: node for node in self.nodes["nodes"]}

        binary_conversion = by_id["F10-PAULI-BINARY"]
        self.assertIn("every natural tensor length L", binary_conversion["statement"])
        self.assertIn("j ranges through k, not q", binary_conversion["encoding"])
        self.assertIn("a_j", binary_conversion["encoding"])
        self.assertIn("G14", binary_conversion["gap_ids"])
        self.assertIn("G14", by_id["B01-BINARY"]["gap_ids"])

        observables = by_id["A04-WIN-OBS"]
        self.assertIn("r_X/r_Z", observables["encoding"])
        self.assertIn("G15", observables["gap_ids"])

        canonical = by_id["K03-INTRO-COMPLEXITY"]
        self.assertIn("integer tuple (q,m,d)", canonical["statement"])
        self.assertNotIn("finite-field representation", canonical["statement"])

        complexity = by_id["K04-GAME-COMPLEXITY"]
        for dependency in ("K03A-FIELD-ARITHMETIC", "K03B-LOW-DEGREE-COMPLEXITY"):
            self.assertIn(dependency, complexity["prerequisites"])
        self.assertIn("exactly the three displayed complexity items", complexity["encoding"])
        self.assertNotIn("sampler", complexity["statement"].lower())
        self.assertNotIn("question/answer", complexity["statement"].lower())

    def test_lean_api_compatibility_contract_is_explicit(self) -> None:
        by_id = {node["id"]: node for node in self.nodes["nodes"]}

        field = by_id["F01-FIELD"]
        self.assertIn("GaloisField 2 k", field["statement"])
        for instance in ("Field", "Fintype", "DecidableEq", "CharP"):
            self.assertIn(instance, field["encoding"])
        self.assertNotIn("FieldModel", json.dumps(field, sort_keys=True))

        measurement = by_id["F03-MEASUREMENT"]
        self.assertIn("MIPStarRE.Quantum.Measurement", measurement["encoding"])
        self.assertIn("do not open", measurement["encoding"])
        self.assertIn("universe uOutcome uCoord", measurement["boundary_hypotheses"])
        self.assertIn("[Fintype Outcome]", measurement["boundary_hypotheses"])

        strategy = by_id["F04-DISTANCE"]
        self.assertIn("EuclideanSpace", strategy["encoding"])
        self.assertIn("WithLp 2", strategy["encoding"])
        self.assertIn("norm-one", strategy["encoding"])
        self.assertIn("MIPStarRE.QPBT.BipartiteIsometry", strategy["lean"]["names"])
        self.assertIn("MIPStarRE.QPBT.BipartiteIsometry.conjugate",
                      strategy["lean"]["names"])
        self.assertIn("universe uAlice uBob", strategy["boundary_hypotheses"])

        parameters = by_id["G01-PARAMETERS"]
        self.assertIn("q=2^k", parameters["statement"])
        self.assertIn("Odd k", parameters["encoding"])
        self.assertIn("Dvd.dvd params.m params.q", parameters["encoding"])
        self.assertIn("not an alias of LDT.Parameters", parameters["encoding"])
        self.assertNotIn("LDT", parameters["lean"]["module"])

        game = by_id["G02-GAME"]
        for phrase in ("sigma types", "uniform finite POVM alphabet", "PMF"):
            self.assertIn(phrase, game["encoding"])
        self.assertIn("universe uType uQuestion uAnswer", game["boundary_hypotheses"])

        extraction = by_id["A15-UNITARY"]
        self.assertIn("MIPStarRE.QPBT.Realizes", extraction["lean"]["names"])
        self.assertIn("MIPStarRE.QPBT.SquaredRealizes", extraction["lean"]["names"])
        for family in ("Alice-X", "Alice-Z", "Bob-X", "Bob-Z"):
            self.assertIn(family, extraction["encoding"])
        self.assertIn("one squared mapped-state norm bound <= delta",
                      extraction["encoding"])
        self.assertIn("unsquared mapped-state norm bound", extraction["encoding"])
        self.assertIn("each <= delta", extraction["encoding"])

        robustness = by_id["R05-ROBUSTNESS"]
        soundness = by_id["S01-SOUNDNESS"]
        self.assertIn("SquaredRealizes", robustness["statement"])
        self.assertIn("normExtraction_ofSquared", robustness["statement"])
        self.assertIn("unsquared Realizes", robustness["statement"])
        self.assertIn("Real.rpow", robustness["encoding"])
        self.assertIn("Real.rpow", soundness["encoding"])
        self.assertEqual(["MIPStarRE.QPBT.pauliSoundness"], soundness["lean"]["names"])
        self.assertEqual(["N01-NAIMARK", "R05-ROBUSTNESS"], soundness["prerequisites"])
        self.assertIn("No bridge, extraction, witness, or projectivity assumption",
                      soundness["boundary_hypotheses"])

    def test_lean_plan_uses_breakable_identifier_macro(self) -> None:
        node = next(node for node in self.nodes["nodes"] if node["id"] == "F08-MAGIC-GAME")
        rendered = check.render_entry(node, [])
        self.assertIn(
            r"\BlueprintIdentifier{MIPStarRE.QPBT.magicSquareStrategyOfAnticommuting}",
            rendered,
        )
        self.assertIn(r"\linebreak", rendered)

    def test_rendering_is_deterministic(self) -> None:
        first = check.outputs(self.nodes, self.gaps, self.externals)
        second = check.outputs(copy.deepcopy(self.nodes), copy.deepcopy(self.gaps),
                               copy.deepcopy(self.externals))
        self.assertEqual(first, second)

    def test_source_anchor_checks_label_and_original_line_mapping(self) -> None:
        node = copy.deepcopy(self.nodes["nodes"][0])
        node["source"] = {
            "path": "references/2001.04383v3/sections/dependencies/sample.tex",
            "label": "def:sample",
            "generated_lines": [2, 2],
            "original_lines": [101, 101],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sections/dependencies").mkdir(parents=True)
            (root / "sections/dependencies/sample.tex").write_bytes(
                b"header\r\n\\label{def:sample}\r\n"
            )
            manifest = {
                "collections": [{
                    "output_directory": "dependencies",
                    "slices": [["sample", 100, 101]],
                }]
            }
            (root / "split-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            doc = {"nodes": [node]}
            self.assertEqual([], check.validate_sources(doc, root))
            node["source"]["original_lines"] = [100, 100]
            self.assertTrue(any("mapping mismatch" in error
                                for error in check.validate_sources(doc, root)))
            node["source"]["original_lines"] = [101, 101]
            node["source"]["label"] = "def:absent"
            self.assertTrue(any("label" in error for error in check.validate_sources(doc, root)))
            self.assertTrue(any(
                "source root lacks split manifest" in error
                for error in check.validate_sources(doc, root / "standalone-stage-3")
            ))


class BlueprintPdfCheckTests(unittest.TestCase):
    def test_bbox_rejects_zero_pages(self) -> None:
        pages, errors = check_pdf.validate_bbox("<html><body><doc/></body></html>")
        self.assertEqual(0, pages)
        self.assertEqual(["document contains no pages"], errors)

    def test_bbox_rejects_zero_area_word_boxes(self) -> None:
        xml = """<html><body><doc><page width="100" height="200">
          <word xMin="10" yMin="20" xMax="10" yMax="30">zero-width</word>
          <word xMin="20" yMin="40" xMax="30" yMax="40">zero-height</word>
        </page></doc></body></html>"""
        pages, errors = check_pdf.validate_bbox(xml)
        self.assertEqual(1, pages)
        self.assertEqual(2, len(errors))
        self.assertTrue(all("zero-area word box" in error for error in errors))

    def test_bbox_rejects_text_past_every_physical_page_edge(self) -> None:
        xml = """<?xml version="1.0"?>
        <html xmlns="http://www.w3.org/1999/xhtml"><body><doc>
          <page width="100" height="200">
            <flow><block><line>
              <word xMin="-1" yMin="20" xMax="10" yMax="21">left</word>
              <word xMin="90" yMin="40" xMax="101" yMax="41">right</word>
              <word xMin="20" yMin="-1" xMax="30" yMax="2">bottom</word>
              <word xMin="40" yMin="199" xMax="50" yMax="201">top</word>
            </line></block></flow>
          </page>
        </doc></body></html>"""
        pages, errors = check_pdf.validate_bbox(xml)
        self.assertEqual(1, pages)
        self.assertEqual(4, len(errors))
        for edge in ("left", "right", "bottom", "top"):
            self.assertTrue(any(f"crosses {edge} page boundary" in error
                                for error in errors))

    def test_bbox_rejects_malformed_or_nonfinite_geometry(self) -> None:
        xml = """<html><body><doc><page width="100" height="200">
          <word xMin="10" yMin="1" xMax="1" yMax="2">inverted</word>
          <word xMin="nan" yMin="1" xMax="10" yMax="2">nonfinite</word>
          <word xMin="1" yMin="1" xMax="10">missing</word>
        </page><page width="-1" height="200"/></doc></body></html>"""
        pages, errors = check_pdf.validate_bbox(xml)
        self.assertEqual(2, pages)
        self.assertEqual(4, len(errors))
        self.assertTrue(any("inverted word box" in error for error in errors))
        self.assertTrue(any("non-finite word box" in error for error in errors))
        self.assertTrue(any("malformed word box" in error for error in errors))
        self.assertTrue(any("invalid page dimensions" in error for error in errors))

    def test_bbox_rejects_overlap_and_accepts_adjacent_text(self) -> None:
        collision_xml = """<html><body><doc><page width="100" height="200">
          <word xMin="10" yMin="20" xMax="30" yMax="30">source-anchor</word>
          <word xMin="25" yMin="20" xMax="40" yMax="30">disposition</word>
        </page></doc></body></html>"""
        pages, errors = check_pdf.validate_bbox(collision_xml)
        self.assertEqual(1, pages)
        self.assertEqual(1, len(errors))
        self.assertIn("text boxes overlap (5.000 x 10.000 points)", errors[0])
        self.assertIn("'source-anchor' and 'disposition'", errors[0])

        xml = """<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>
          <page width="100" height="200">
            <word xMin="1" yMin="1" xMax="50" yMax="2">first</word>
            <word xMin="50" yMin="1" xMax="100" yMax="2">second</word>
          </page>
        </doc></body></html>"""
        pages, errors = check_pdf.validate_bbox(xml)
        self.assertEqual(1, pages)
        self.assertEqual([], errors)
        self.assertEqual([], check_pdf.extracted_identifier_errors(
            "magicSquareStrategyOf\nAnticommuting",
            ["magicSquareStrategyOfAnticommuting"],
        ))

    def test_bbox_overlap_threshold_is_strict_and_decimal_exact(self) -> None:
        cases = (
            ("x", "9.9001", "0", "accepts just below", 0),
            ("x", "9.9", "0", "accepts exact threshold", 0),
            ("x", "9.8999", "0", "rejects just above", 1),
            ("y", "9", "9.9001", "accepts just below", 0),
            ("y", "9", "9.9", "accepts exact threshold", 0),
            ("y", "9", "9.8999", "rejects just above", 1),
        )
        for axis, x_min, y_min, description, expected_errors in cases:
            with self.subTest(axis=axis, position=description):
                xml = f"""<html><body><doc><page width="100" height="200">
                  <word xMin="0" yMin="0" xMax="10" yMax="10">first</word>
                  <word xMin="{x_min}" yMin="{y_min}" xMax="20" yMax="20">second</word>
                </page></doc></body></html>"""
                pages, errors = check_pdf.validate_bbox(xml)
                self.assertEqual(1, pages)
                self.assertEqual(expected_errors, len(errors))


if __name__ == "__main__":
    unittest.main()
