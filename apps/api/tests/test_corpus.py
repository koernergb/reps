from pathlib import Path

import pytest
import yaml

from app.corpus.loader import CorpusError, evaluate_expression, get_corpus, load_corpus
from app.corpus.schema import ProblemDef
from app.corpus.validate import coverage, execute, lint

CORPUS_DIR = Path(__file__).resolve().parents[3] / "packages" / "problem-corpus"


def copy_corpus(tmp_path: Path) -> Path:
    target = tmp_path / "corpus"
    (target / "problems").mkdir(parents=True)
    (target / "exercises").mkdir()
    (target / "taxonomy.yaml").write_text((CORPUS_DIR / "taxonomy.yaml").read_text())
    for path in (CORPUS_DIR / "problems").rglob("*.yaml"):
        (target / "problems" / path.name).write_text(path.read_text())
    return target


def problem_yaml(slug: str) -> dict[str, object]:
    path = next((CORPUS_DIR / "problems").rglob(f"{slug}.yaml"))
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


def test_repository_corpus_passes_lint() -> None:
    report = lint(get_corpus())
    assert report.errors == []


def test_corpus_meets_milestone_two_size_and_coverage() -> None:
    corpus = get_corpus()
    report = coverage(corpus)
    assert report["problems"] >= 25
    assert report["uncovered_capabilities"] == []
    for topic in (
        "arrays-hashing",
        "two-pointers",
        "sliding-window",
        "stack",
        "binary-search",
        "linked-list",
        "trees",
        "heap",
        "graphs",
        "dp-1d",
    ):
        assert report["by_topic"][topic] >= 2, topic
    for problem in corpus.problems.values():
        assert problem.definition.wrong_solutions, problem.definition.slug


def test_schema_rejects_unbounded_timeouts_and_missing_hints() -> None:
    data = problem_yaml("pair-sum-indices")
    with pytest.raises(ValueError):
        ProblemDef.model_validate({**data, "per_test_timeout_s": 60})
    with pytest.raises(ValueError):
        ProblemDef.model_validate({**data, "hints": ["only one"]})
    with pytest.raises(ValueError):
        ProblemDef.model_validate({**data, "unknown_field": True})


def test_lint_detects_dangling_references_cycles_and_duplicates(tmp_path: Path) -> None:
    root = copy_corpus(tmp_path)
    pair = problem_yaml("pair-sum-indices")
    pair["prerequisites"] = ["subarray-sum-equals-k"]
    pair["related"] = ["does-not-exist"]
    tests = pair["hidden_tests"]
    assert isinstance(tests, list)
    pair["hidden_tests"] = [*tests, tests[0]]
    (root / "problems" / "pair-sum-indices.yaml").write_text(yaml.safe_dump(pair))
    report = lint(load_corpus(root))
    joined = "\n".join(report.errors)
    assert "dangling problem reference does-not-exist" in joined
    assert "circular prerequisites" in joined
    assert "duplicate test input" in joined


def test_lint_detects_public_reference_exposure(tmp_path: Path) -> None:
    root = copy_corpus(tmp_path)
    pair = problem_yaml("pair-sum-indices")
    pair["statement"] = str(pair["statement"]) + "\ncomplement = target - value\n"
    (root / "problems" / "pair-sum-indices.yaml").write_text(yaml.safe_dump(pair))
    report = lint(load_corpus(root))
    assert any("exposes reference line" in error for error in report.errors)


def test_duplicate_slugs_fail_to_load(tmp_path: Path) -> None:
    root = copy_corpus(tmp_path)
    pair = problem_yaml("pair-sum-indices")
    (root / "problems" / "copy.yaml").write_text(yaml.safe_dump(pair))
    with pytest.raises(CorpusError, match="duplicate problem slug"):
        load_corpus(root)


def test_expressions_have_no_dangerous_builtins() -> None:
    assert evaluate_expression("[list(range(3))]") == [[0, 1, 2]]
    with pytest.raises(NameError):
        evaluate_expression("__import__('os')")
    with pytest.raises(NameError):
        evaluate_expression("open('/etc/passwd')")


def test_execution_validation_catches_mistakes_for_the_intended_reason() -> None:
    corpus = get_corpus()
    report = execute(corpus, only={"balanced-delimiters", "longest-unique-substring"})
    assert report.errors == []


def test_execution_validation_rejects_a_broken_reference(tmp_path: Path) -> None:
    root = copy_corpus(tmp_path)
    data = problem_yaml("max-depth")
    data["reference_solution"] = "def max_depth(root):\n    return 1\n"
    (root / "problems" / "max-depth.yaml").write_text(yaml.safe_dump(data))
    report = execute(load_corpus(root), only={"max-depth"})
    assert any("reference solution failed" in error for error in report.errors)


def test_execution_validation_rejects_uncaught_wrong_solution(tmp_path: Path) -> None:
    root = copy_corpus(tmp_path)
    data = problem_yaml("max-depth")
    wrong = data["wrong_solutions"]
    assert isinstance(wrong, list)
    wrong[0]["code"] = data["reference_solution"]
    (root / "problems" / "max-depth.yaml").write_text(yaml.safe_dump(data))
    report = execute(load_corpus(root), only={"max-depth"})
    assert any("do not catch" in error for error in report.errors)
