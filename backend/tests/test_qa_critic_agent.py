from agents.qa_critic_agent import QACriticAgent
from graph.state import new_state


class _FakeLLMClient:
    def __init__(self, reply):
        self._reply = reply

    def chat(self, messages, **kwargs):
        return self._reply

    def get_last_usage(self):
        return None


def _state_with_report(tmp_path):
    state = new_state(session_id="s1", goal="test")
    report_path = tmp_path / "report.docx"
    report_path.write_text("fake docx")
    state["agent_outputs"]["report_generator"] = {
        "report": {"path": str(report_path), "citation_count": 1, "citations": []}
    }
    return state


def test_review_passes_when_llm_says_pass(tmp_path):
    agent = QACriticAgent(llm_client=_FakeLLMClient("PASS"))
    state = agent.review(_state_with_report(tmp_path))

    assert state["agent_outputs"]["qa_critic"]["status"] == "pass"
    assert state["agent_outputs"]["qa_critic"]["attempts"] == 1


def test_review_fails_when_llm_flags_an_issue(tmp_path):
    agent = QACriticAgent(llm_client=_FakeLLMClient("FAIL: score claim isn't supported"))
    state = agent.review(_state_with_report(tmp_path))

    assert state["agent_outputs"]["qa_critic"]["status"] == "fail"
    assert state["agent_outputs"]["qa_critic"]["forced"] is False


def test_review_forces_pass_after_max_attempts(tmp_path):
    agent = QACriticAgent(llm_client=_FakeLLMClient("FAIL: still wrong"))
    state = _state_with_report(tmp_path)
    state["agent_outputs"]["qa_critic"] = {"status": "fail", "feedback": "x", "attempts": 1, "forced": False}

    state = agent.review(state)

    assert state["agent_outputs"]["qa_critic"]["attempts"] == 2
    assert state["agent_outputs"]["qa_critic"]["status"] == "pass"
    assert state["agent_outputs"]["qa_critic"]["forced"] is True


def test_review_fails_when_no_report_exists():
    agent = QACriticAgent(llm_client=_FakeLLMClient("PASS"))
    state = new_state(session_id="s1", goal="test")

    state = agent.review(state)

    assert state["agent_outputs"]["qa_critic"]["status"] == "fail"
    assert "No report" in state["agent_outputs"]["qa_critic"]["feedback"]


def test_review_records_token_usage_when_client_reports_it(tmp_path):
    class _MeteredLLMClient:
        last_usage = {"model": "fake/model", "tokens_in": 40, "tokens_out": 8, "cost_usd": 0.0}

        def chat(self, messages, **kwargs):
            return "PASS"

    agent = QACriticAgent(llm_client=_MeteredLLMClient())
    state = agent.review(_state_with_report(tmp_path))

    assert len(state["token_usage"]) == 1
    assert list(state["token_usage"].values())[0] == _MeteredLLMClient.last_usage


def test_review_passes_through_on_llm_failure(tmp_path):
    class _BrokenLLMClient:
        def chat(self, messages, **kwargs):
            raise RuntimeError("model unavailable")

    agent = QACriticAgent(llm_client=_BrokenLLMClient())
    state = agent.review(_state_with_report(tmp_path))

    assert state["agent_outputs"]["qa_critic"]["status"] == "pass"


def test_review_records_token_usage_on_success(tmp_path):
    class _MeteredLLMClient:
        def chat(self, messages, **kwargs):
            return "PASS"

        def get_last_usage(self):
            return {"model": "some-model:free", "tokens_in": 120, "tokens_out": 15, "cost_usd": 0.0}

    agent = QACriticAgent(llm_client=_MeteredLLMClient())
    state = agent.review(_state_with_report(tmp_path))

    usage = state["token_usage"]["qa_critic:some-model:free"]
    assert usage == {"model": "some-model:free", "tokens_in": 120, "tokens_out": 15, "cost_usd": 0.0}


def test_review_passes_through_when_no_llm_client_configured(tmp_path, monkeypatch):
    """Regression test: get_llm_client() itself can raise (e.g. no
    OPENROUTER_API_KEY set) — that must degrade to a passed-through verdict
    like any other LLM failure, not propagate out of review()."""

    def _broken_get_llm_client():
        raise RuntimeError("no OPENROUTER_API_KEY configured")

    monkeypatch.setattr("agents.qa_critic_agent.get_llm_client", _broken_get_llm_client)

    agent = QACriticAgent(llm_client=None)
    state = agent.review(_state_with_report(tmp_path))

    assert state["agent_outputs"]["qa_critic"]["status"] == "pass"
    assert state["token_usage"] == {}


def test_review_does_not_record_usage_on_llm_failure(tmp_path):
    class _BrokenLLMClient:
        def chat(self, messages, **kwargs):
            raise RuntimeError("model unavailable")

        def get_last_usage(self):
            # Would be a bug if this got recorded — it's stale data from
            # some earlier unrelated call, not from this failed attempt.
            return {"model": "stale-model", "tokens_in": 999, "tokens_out": 999, "cost_usd": 0.0}

    agent = QACriticAgent(llm_client=_BrokenLLMClient())
    state = agent.review(_state_with_report(tmp_path))

    assert state["token_usage"] == {}
