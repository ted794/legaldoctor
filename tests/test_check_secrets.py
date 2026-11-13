import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_secrets", Path(__file__).resolve().parent.parent / "scripts" / "check_secrets.py"
)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


def test_real_value_detected():
    hits = cs.scan_text("a.py", "x = 'abc123secretvalue'", [("LAW_OC", "abc123secretvalue")])
    assert hits and "LAW_OC" in hits[0] and "abc123secretvalue" not in hits[0]


def test_placeholder_ok():
    assert cs.scan_text("a.env", "LAW_OC=your-law-oc", []) == []
    assert cs.scan_text("a.py", 'os.getenv("LINER_API_KEY", "")', []) == []


def test_generic_assignment_flagged():
    assert cs.scan_text("a.env", "LINER_API_KEY=abcd1234efgh5678", [])
