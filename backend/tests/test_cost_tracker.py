from core.cost_tracker import record_usage
from graph.state import new_state


def test_record_usage_stores_keyed_by_agent_and_model():
    state = new_state(session_id="s1", goal="test")

    record_usage(state, "qa_critic", {"model": "m1:free", "tokens_in": 10, "tokens_out": 2, "cost_usd": 0.0})

    assert state["token_usage"] == {
        "qa_critic:m1:free": {"model": "m1:free", "tokens_in": 10, "tokens_out": 2, "cost_usd": 0.0}
    }


def test_record_usage_accumulates_repeat_calls_for_same_agent_and_model():
    state = new_state(session_id="s1", goal="test")

    record_usage(state, "qa_critic", {"model": "m1:free", "tokens_in": 10, "tokens_out": 2, "cost_usd": 0.0})
    record_usage(state, "qa_critic", {"model": "m1:free", "tokens_in": 5, "tokens_out": 1, "cost_usd": 0.0})

    assert state["token_usage"]["qa_critic:m1:free"] == {
        "model": "m1:free", "tokens_in": 15, "tokens_out": 3, "cost_usd": 0.0
    }


def test_record_usage_keeps_different_agents_separate():
    state = new_state(session_id="s1", goal="test")

    record_usage(state, "qa_critic", {"model": "m1:free", "tokens_in": 10, "tokens_out": 2, "cost_usd": 0.0})
    record_usage(state, "vision_ocr", {"model": "m1:free", "tokens_in": 20, "tokens_out": 3, "cost_usd": 0.0})

    assert len(state["token_usage"]) == 2
    assert state["token_usage"]["qa_critic:m1:free"]["tokens_in"] == 10
    assert state["token_usage"]["vision_ocr:m1:free"]["tokens_in"] == 20


def test_record_usage_is_a_noop_when_usage_is_none():
    state = new_state(session_id="s1", goal="test")

    record_usage(state, "qa_critic", None)

    assert state["token_usage"] == {}
