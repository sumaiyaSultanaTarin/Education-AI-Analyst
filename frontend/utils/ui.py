"""Shared visual polish for every page — call inject_base_styles() once near
the top of each page (right after st.set_page_config), then page_header()
instead of st.title() and status_badge() instead of a plain f-string.

Kept to safe, well-known Streamlit CSS hooks (.stButton>button,
[data-testid="stMetric*"], footer) rather than deep DOM selectors tied to a
specific Streamlit build, since those change across versions and pinning to
them would make this brittle against streamlit>1.51 bumps.
"""

import streamlit as st

_STATUS_COLORS: dict[str, tuple[str, str]] = {
    # label -> (text color, background)
    "planned": ("#475569", "#F1F5F9"),
    "completed": ("#1D4ED8", "#DBEAFE"),
    "awaiting_approval": ("#B45309", "#FEF3C7"),
    "report_ready": ("#15803D", "#DCFCE7"),
    "pass": ("#15803D", "#DCFCE7"),
    "fail": ("#B91C1C", "#FEE2E2"),
    "approved": ("#15803D", "#DCFCE7"),
    "rejected": ("#B91C1C", "#FEE2E2"),
    "retry": ("#B45309", "#FEF3C7"),
}
_DEFAULT_COLOR = ("#334155", "#F1F5F9")


def inject_base_styles() -> None:
    st.markdown(
        """
        <style>
        /* Tighter top padding so the header sits closer to the sidebar toggle. */
        .block-container { padding-top: 2.2rem; padding-bottom: 3rem; }

        /* Page header (see page_header() below). */
        .eaa-header { display: flex; align-items: center; gap: 0.75rem;
            margin-bottom: 1.4rem; padding-bottom: 1rem;
            border-bottom: 1px solid rgba(49, 51, 63, 0.1); }
        .eaa-header-icon { font-size: 2rem; line-height: 1; }
        .eaa-header-title { font-size: 1.6rem; font-weight: 700; line-height: 1.2;
            color: inherit; }
        .eaa-header-subtitle { font-size: 0.92rem; color: rgba(49, 51, 63, 0.6);
            margin-top: 0.15rem; }

        /* Status pill (see status_badge() below). */
        .eaa-badge { display: inline-block; padding: 0.15rem 0.7rem;
            border-radius: 999px; font-size: 0.82rem; font-weight: 600; }

        /* Buttons: rounder, subtle lift on hover instead of the flat default. */
        .stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {
            border-radius: 8px; transition: transform 0.08s ease, box-shadow 0.15s ease;
        }
        .stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {
            transform: translateY(-1px); box-shadow: 0 4px 10px rgba(79, 70, 229, 0.15);
        }

        /* Metric tiles: give them a card so a row of metrics reads as one unit. */
        div[data-testid="stMetric"] { background: #F5F6FA; border-radius: 10px;
            padding: 0.9rem 1rem; border: 1px solid rgba(49, 51, 63, 0.06); }

        /* Alerts (success/info/warning/error): rounder corners, less boxy. */
        div[data-testid="stAlertContainer"] { border-radius: 10px; }

        /* Tables: rounded corners so they match the card language everywhere else. */
        div[data-testid="stTable"], div[data-testid="stDataFrame"] {
            border-radius: 10px; overflow: hidden;
        }

        /* Drop the "Made with Streamlit" footer — pure chrome for a local demo app. */
        footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: str | None = None) -> None:
    subtitle_html = f'<div class="eaa-header-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="eaa-header">
            <span class="eaa-header-icon">{icon}</span>
            <div>
                <div class="eaa-header-title">{title}</div>
                {subtitle_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(label: str | None) -> str:
    """Returns HTML for an inline colored pill — pass to st.markdown(..., unsafe_allow_html=True)."""
    if not label:
        label = "unknown"
    color, background = _STATUS_COLORS.get(label, _DEFAULT_COLOR)
    return f'<span class="eaa-badge" style="color:{color};background:{background};">{label}</span>'
