"""Streamlit styling and reusable UI helpers."""

import html
import json

import streamlit as st
import streamlit.components.v1 as components

from modules.config import SOURCE_TYPES
from modules.google_sheets import save_verified_source
from modules.source_names import suggest_source_name


def render_copyable_address(address):
    """Render a selectable address with an always-visible copy button."""
    safe_address = html.escape(address)
    javascript_address = (
        json.dumps(address)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )

    components.html(
        f"""
        <style>
        html, body {{
            margin: 0;
            background: transparent;
            font-family: 'IBM Plex Mono', monospace;
        }}

        .copy-row {{
            box-sizing: border-box;
            display: flex;
            align-items: center;
            width: 100%;
            min-height: 46px;
            padding: 0.35rem 0.4rem 0.35rem 0.8rem;
            border: 1px solid rgba(255, 155, 66, 0.82);
            border-radius: 7px;
            background: rgba(128, 128, 128, 0.08);
            color: inherit;
            gap: 0.75rem;
        }}

        .address {{
            flex: 1;
            overflow-wrap: anywhere;
            user-select: text;
            font-size: 0.88rem;
            line-height: 1.35;
        }}

        .copy-button {{
            flex: 0 0 auto;
            min-width: 86px;
            min-height: 34px;
            border: 1px solid #ff9b42;
            border-radius: 6px;
            background: #11131a;
            color: #ffffff;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.78rem;
            font-weight: 600;
        }}

        .copy-button:hover {{
            color: #ffb86b;
            border-color: #ffb86b;
        }}
        </style>

        <div class="copy-row">
            <div class="address">{safe_address}</div>
            <button class="copy-button" type="button" onclick="copyAddress(this)">Copy</button>
        </div>

        <script>
        const address = {javascript_address};

        async function copyAddress(button) {{
            try {{
                await navigator.clipboard.writeText(address);
            }} catch (error) {{
                const textarea = document.createElement("textarea");
                textarea.value = address;
                textarea.style.position = "fixed";
                textarea.style.opacity = "0";
                document.body.appendChild(textarea);
                textarea.focus();
                textarea.select();
                document.execCommand("copy");
                textarea.remove();
            }}

            button.textContent = "Copied!";
            window.setTimeout(() => {{
                button.textContent = "Copy";
            }}, 1600);
        }}
        </script>
        """,
        height=54,
        scrolling=False,
    )


def display_saved_sources(match):
    source_labels = {
        "parcel_gis": "Parcel / GIS Map",
        "zoning_map": "Zoning Map",
        "assessor": "Assessor / Property Search",
        "zoning_ordinance": "Zoning Ordinance / Code",
        "setback_reference": "Setback Reference",
        "other": "Other Source",
    }

    displayed_urls = set()
    displayed_count = 0

    for source_type, label in source_labels.items():
        group = match[match["source_type"] == source_type]

        visible_rows = []
        for _, row in group.iterrows():
            url = str(row["source_url"]).strip()

            if not url or url.lower() == "nan":
                continue

            if url in displayed_urls:
                continue

            visible_rows.append(row)
            displayed_urls.add(url)

        if visible_rows:
            st.markdown(f"<div class='source-label'>{label}</div>", unsafe_allow_html=True)
            for _, row in group.iterrows():
                url = str(row["source_url"]).strip()
                if not url or url.lower() == "nan" or url not in displayed_urls:
                    continue
                st.markdown(
                    f"<div class='source-link'>↳ <a href='{row['source_url']}' target='_blank'>{row['source_name']}</a></div>",
                    unsafe_allow_html=True,
                )
                notes = str(row.get("notes", "")).strip()
                if notes and notes.lower() != "nan":
                    st.markdown(
                        f"<div class='source-note'>{notes}</div>",
                        unsafe_allow_html=True,
                    )
                displayed_count += 1
            displayed_urls = set(displayed_urls)

    return displayed_count


def display_candidates(candidates):
    if candidates:
        for i, candidate in enumerate(candidates, 1):
            title = candidate.get("title", "Untitled result")
            href = candidate.get("href", "")
            st.markdown(
                f"<div class='candidate-link'>{i}. <a href='{href}' target='_blank'>{title}</a></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No high-confidence suggestions found. Use fallback search if needed.")


def _handle_source_url_change():
    source_url = st.session_state.get("save_source_url", "").strip()
    current_name = st.session_state.get("save_source_name", "").strip()
    previous_suggestion = st.session_state.get("last_auto_source_name", "")

    if not source_url:
        st.session_state["source_name_suggestion_status"] = ""
        return

    if current_name and current_name != previous_suggestion:
        st.session_state["source_name_suggestion_status"] = (
            "The source name was left unchanged because you edited it."
        )
        return

    suggestion = suggest_source_name(source_url)
    if suggestion:
        st.session_state["save_source_name"] = suggestion
        st.session_state["last_auto_source_name"] = suggestion
        st.session_state["source_name_suggestion_status"] = (
            "Suggested from the source URL. Review or edit before saving."
        )


def _save_source(detected_county, detected_state):
    source_type = st.session_state.get("save_source_type", SOURCE_TYPES[0])
    source_name = st.session_state.get("save_source_name", "").strip()
    source_url = st.session_state.get("save_source_url", "").strip()
    notes = st.session_state.get("save_source_notes", "").strip()

    if not source_name or not source_url:
        st.session_state["save_source_feedback"] = (
            "error",
            "Please enter both source name and source URL.",
        )
        return

    saved, message = save_verified_source(
        county=detected_county,
        state=detected_state,
        source_type=source_type,
        source_name=source_name,
        source_url=source_url,
        notes=notes,
    )
    st.session_state["save_source_feedback"] = (
        "success" if saved else "warning",
        message,
    )

    if saved:
        st.session_state["save_source_type"] = SOURCE_TYPES[0]
        st.session_state["save_source_name"] = ""
        st.session_state["save_source_url"] = ""
        st.session_state["save_source_notes"] = ""
        st.session_state["last_auto_source_name"] = ""
        st.session_state["source_name_suggestion_status"] = ""


def render_save_source_form(detected_county, detected_state):
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    with st.expander("＋ Save verified source", expanded=False):
        st.caption("Save only after confirming the link is official and useful.")

        feedback = st.session_state.pop("save_source_feedback", None)
        if feedback:
            feedback_type, message = feedback
            getattr(st, feedback_type)(message)

        st.selectbox(
            "Source Type",
            SOURCE_TYPES,
            key="save_source_type",
        )

        st.text_input(
            "Source URL",
            placeholder="Paste verified source URL here",
            key="save_source_url",
            on_change=_handle_source_url_change,
        )

        st.text_input(
            "Source Name",
            placeholder="Suggested automatically after you paste a URL",
            key="save_source_name",
        )

        suggestion_status = st.session_state.get("source_name_suggestion_status", "")
        if suggestion_status:
            st.caption(suggestion_status)

        st.text_input(
            "Notes",
            placeholder="Optional. Example: Official zoning PDF / parcel viewer / assessor search",
            key="save_source_notes",
        )

        st.button(
            "Save Source",
            on_click=_save_source,
            args=(detected_county, detected_state),
        )


def apply_styles():
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

        <style>
        html, body, [data-testid="stAppViewContainer"], h1, h2, h3, h4, h5, h6,
        p, label, div[data-testid="stMarkdownContainer"],
        input, textarea, button, a {
            font-family: 'IBM Plex Mono', monospace !important;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 4rem;
            padding-left: 4rem;
            padding-right: 4rem;
            max-width: none;
        }

        h1 {
            font-size: 2.45rem;
            letter-spacing: -0.04em;
            font-weight: 700;
            margin-bottom: 0.6rem;
        }

        h2 {
            font-size: 1.75rem;
            font-weight: 700;
            letter-spacing: -0.03em;
        }

        h3 {
            font-size: 1.15rem;
            font-weight: 700;
        }

        p, .stCaption {
            font-size: 0.95rem;
        }

        div.stButton > button,
        div.stFormSubmitButton > button {
            border: 1px solid #ff9b42;
            background: #11131a;
            color: #ffffff;
            padding: 0.62rem 1.2rem;
            border-radius: 8px;
            font-weight: 600;
        }

        div.stButton > button:hover,
        div.stFormSubmitButton > button:hover {
            border-color: #ffb86b;
            color: #ffb86b;
        }

        .section-divider {
            border-top: 1px solid rgba(255, 255, 255, 0.16);
            margin: 2rem 0 1.75rem 0;
        }

        .source-label {
            font-weight: 700;
            margin-top: 1rem;
            margin-bottom: 0.35rem;
            color: #ffffff;
            font-size: 1rem;
        }

        .source-link,
        .candidate-link {
            padding: 0.25rem 0;
            font-size: 0.95rem;
            line-height: 1.55;
        }

        .source-note {
            opacity: 0.72;
            font-size: 0.82rem;
            margin-left: 1rem;
            margin-bottom: 0.45rem;
            line-height: 1.45;
        }

        div[data-testid="stExpander"] details {
            border: 1px solid rgba(49, 205, 93, 0.78) !important;
            border-radius: 8px !important;
            background: rgba(255, 255, 255, 0.012);
        }

        div[data-testid="stExpander"] summary {
            font-weight: 600;
        }

        .feedback-button {
            position: fixed;
            right: 2.25rem;
            bottom: 1.75rem;
            z-index: 999;
            border: 1px solid #6ea8ff;
            color: #dce9ff;
            background: #11131a;
            padding: 0.6rem 1.2rem;
            border-radius: 4px;
            text-align: center;
            width: 180px;
            font-size: 0.78rem;
            letter-spacing: 0.08em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
