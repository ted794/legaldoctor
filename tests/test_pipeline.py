from regpang.pipeline import Evidence, StageResult, run


class FakeStage:
    def __init__(self, name, evidence=True):
        self.name = name
        self.label = name
        self.evidence = evidence

    def __call__(self, state):
        ev = [Evidence(kind="user_input", title="t")] if self.evidence else []
        return StageResult(stage=self.name, summary=self.name, evidence=ev)


def test_runs_all_stages_with_evidence():
    state = run("x", stages=[FakeStage("a"), FakeStage("b")])
    assert list(state.results) == ["a", "b"]
    assert state.halted_at is None


def test_halts_when_no_evidence():
    state = run("x", stages=[FakeStage("a"), FakeStage("b", evidence=False), FakeStage("c")])
    assert list(state.results) == ["a"]
    assert state.halted_at == "b"


def test_default_stages_halt_at_first_todo():
    state = run("x")
    assert state.halted_at == "decompose"
