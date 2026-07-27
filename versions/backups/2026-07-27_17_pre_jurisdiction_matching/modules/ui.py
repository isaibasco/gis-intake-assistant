"""Streamlit styling and reusable UI helpers."""

import hashlib
import html
import json

import streamlit as st

from modules.config import SOURCE_TYPES
from modules.google_sheets import (
    restore_rejected_source,
    save_rejected_source,
    save_verified_source,
)
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

    st.iframe(
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
            background: #f8f8fb;
            color: #202124;
            gap: 0.75rem;
        }}

        @media (prefers-color-scheme: dark) {{
            .copy-row {{
                background: #171820;
                color: #f3f3f5;
            }}
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
        width="stretch",
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


def _mark_candidate_not_useful(
    href,
    title,
    county,
    state,
    source_type,
    full_address,
):
    saved, message = save_rejected_source(
        county=county,
        state=state,
        source_type=source_type,
        source_name=title,
        source_url=href,
        full_address=full_address,
    )

    if saved:
        lookup_result = st.session_state.get("lookup_result")
        if lookup_result:
            for candidate_group in (
                "general_candidates",
                "zoning_candidates",
                "setback_candidates",
            ):
                lookup_result[candidate_group] = [
                    candidate
                    for candidate in lookup_result.get(candidate_group, [])
                    if candidate.get("href", "").strip() != href.strip()
                ]

            rejected_sources = lookup_result.setdefault("rejected_sources", [])
            if not any(
                source.get("source_url", "").strip() == href.strip()
                for source in rejected_sources
            ):
                rejected_sources.append({
                    "source_type": source_type,
                    "source_name": title,
                    "source_url": href,
                })

        st.session_state["candidate_feedback"] = ("success", message)
    else:
        st.session_state["candidate_feedback"] = ("warning", message)


def _candidate_group_for_source_type(source_type):
    return {
        "parcel_gis": "general_candidates",
        "assessor": "general_candidates",
        "zoning_map": "zoning_candidates",
        "zoning_ordinance": "setback_candidates",
        "setback_reference": "setback_candidates",
    }.get(source_type, "general_candidates")


def _restore_not_useful_source(href, title, source_type, full_address):
    restored, message = restore_rejected_source(
        source_url=href,
        full_address=full_address,
    )

    if restored:
        lookup_result = st.session_state.get("lookup_result")
        if lookup_result:
            lookup_result["rejected_sources"] = [
                source
                for source in lookup_result.get("rejected_sources", [])
                if source.get("source_url", "").strip() != href.strip()
            ]

            candidate_group = _candidate_group_for_source_type(source_type)
            candidates = lookup_result.setdefault(candidate_group, [])
            if not any(
                candidate.get("href", "").strip() == href.strip()
                for candidate in candidates
            ):
                candidates.append({"title": title, "href": href})

        st.session_state["candidate_feedback"] = ("success", message)
    else:
        st.session_state["candidate_feedback"] = ("warning", message)


def display_candidate_feedback():
    feedback = st.session_state.pop("candidate_feedback", None)
    if feedback:
        feedback_type, message = feedback
        getattr(st, feedback_type)(message)


def display_candidates(candidates, county, state, source_type, full_address):
    if candidates:
        for i, candidate in enumerate(candidates, 1):
            title = candidate.get("title", "Untitled result")
            href = candidate.get("href", "").strip()
            safe_title = html.escape(title)
            safe_href = html.escape(href, quote=True)
            button_key = hashlib.sha256(
                f"{source_type}|{href}".encode("utf-8")
            ).hexdigest()[:16]

            link_column, action_column = st.columns([0.76, 0.24], gap="small")
            with link_column:
                st.markdown(
                    (
                        f"<div class='candidate-link'>{i}. "
                        f"<a href='{safe_href}' target='_blank'>{safe_title}</a></div>"
                    ),
                    unsafe_allow_html=True,
                )
            with action_column:
                st.button(
                    "Not useful",
                    key=f"reject_candidate_{button_key}",
                    help="Hide this URL whenever this same entered address is searched.",
                    on_click=_mark_candidate_not_useful,
                    args=(href, title, county, state, source_type, full_address),
                    type="tertiary",
                    icon=":material/thumb_down:",
                    width="stretch",
                )
    else:
        st.caption("No high-confidence suggestions found. Use fallback search if needed.")


def render_rejected_sources(rejected_sources, full_address):
    """Show address-scoped rejected links with a reversible restore action."""
    if not rejected_sources:
        return

    with st.expander(
        f"Not useful for this address ({len(rejected_sources)})",
        expanded=False,
    ):
        st.caption(
            "These links stay hidden only for this entered address. "
            "Restore a link if you want it included again."
        )

        for source in rejected_sources:
            title = str(source.get("source_name", "")).strip() or "Untitled result"
            href = str(source.get("source_url", "")).strip()
            source_type = str(source.get("source_type", "")).strip()
            if not href:
                continue

            safe_title = html.escape(title)
            safe_href = html.escape(href, quote=True)
            button_key = hashlib.sha256(
                f"{full_address}|{source_type}|{href}".encode("utf-8")
            ).hexdigest()[:16]

            link_column, action_column = st.columns([0.76, 0.24], gap="small")
            with link_column:
                st.markdown(
                    (
                        "<div class='candidate-link'>"
                        f"<a href='{safe_href}' target='_blank'>{safe_title}</a>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
            with action_column:
                st.button(
                    "Restore",
                    key=f"restore_candidate_{button_key}",
                    help="Allow this URL to appear again for this entered address.",
                    on_click=_restore_not_useful_source,
                    args=(href, title, source_type, full_address),
                    type="tertiary",
                    icon=":material/undo:",
                    width="stretch",
                )


def render_manual_county_form(pending_lookup):
    """Ask for an optional county without restarting the project lookup."""
    st.info(
        "Automatic county detection is unavailable. "
        "Enter the county if known, or continue without it."
    )
    st.caption(f"Project retained: {pending_lookup['full_address']}")

    with st.form("manual_county_form"):
        manual_county = st.text_input(
            "County (optional)",
            placeholder="Example: Jefferson County",
            key="manual_county_input",
        )
        continue_search = st.form_submit_button("Continue Search")

    return manual_county, continue_search


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

        div.stButton > button[kind="tertiary"],
        button[data-testid="stBaseButton-tertiary"] {
            border: 1px solid rgba(255, 255, 255, 0.16);
            background: transparent;
            color: inherit;
            padding: 0.25rem 0.45rem;
            font-size: 0.75rem;
            opacity: 0.78;
        }

        div.stButton > button[kind="tertiary"]:hover,
        button[data-testid="stBaseButton-tertiary"]:hover {
            border-color: #ff9b42;
            color: #ffb86b;
            opacity: 1;
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
