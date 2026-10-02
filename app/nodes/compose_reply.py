"""compose_reply.py — Node 6: render the selected SOP deterministically."""

from app.policy_reply import render_policy_reply


def compose_reply_node(state: dict) -> dict:
    """
    Render exactly the selected SOP guidance plus the fetched values that
    established it. This prevents unsupported advice or numbers from reaching
    the user.
    """
    return {
        **state,
        "reply": render_policy_reply(state),
        "reply_source": "policy_template",
    }
