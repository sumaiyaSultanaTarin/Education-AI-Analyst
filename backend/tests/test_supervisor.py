from agents.supervisor import SupervisorAgent
from graph.state import new_state


def test_create_plan_produces_a_placeholder_step_referencing_the_goal():
    agent = SupervisorAgent()
    state = new_state(session_id="s1", goal="Summarize Q3 results")

    state = agent.create_plan(state)

    assert len(state["plan"]) == 1
    assert state["plan"][0]["status"] == "pending"
    assert "Summarize Q3 results" in state["plan"][0]["description"]


def test_create_plan_records_a_message():
    agent = SupervisorAgent()
    state = new_state(session_id="s1", goal="test")

    state = agent.create_plan(state)

    assert len(state["messages"]) == 1
    assert state["messages"][0]["from_agent"] == "supervisor"
