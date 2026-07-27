"""Cached URL metadata and readable fallback names for verified sources."""

import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import streamlit as st


MAX_METADATA_BYTES = 131_072
TITLE_TIMEOUT_SECONDS = 4


class _TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.open_graph_title = ""

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = {str(key).lower(): value for key, value in attrs if key}

        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            property_name = str(
                attributes.get("property") or attributes.get("name") or ""
            ).lower()
            if property_name == "og:title" and not self.open_graph_title:
                self.open_graph_title = str(attributes.get("content") or "")

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self):
        return " ".join(self.title_parts)


def _normalize_url(source_url):
    source_url = source_url.strip()
    if source_url and "://" not in source_url:
        return f"https://{source_url}"
    return source_url


def _is_public_address(address):
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _is_safe_public_url(source_url):
    parsed = urlparse(source_url)
    hostname = parsed.hostname

    if parsed.scheme not in {"http", "https"} or not hostname:
        return False

    hostname = hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".local", ".internal")):
        return False

    try:
        address_info = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError:
        return False

    addresses = {item[4][0] for item in address_info}
    return bool(addresses) and all(_is_public_address(address) for address in addresses)


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        redirected_url = urljoin(request.full_url, new_url)
        if not _is_safe_public_url(redirected_url):
            raise URLError("Redirect target is not a public HTTP(S) URL.")
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            redirected_url,
        )


def _clean_title(value):
    value = html.unescape(value or "")
    return re.sub(r"\s+", " ", value).strip()


def _fetch_page_metadata(source_url):
    normalized_url = _normalize_url(source_url)
    if not _is_safe_public_url(normalized_url):
        return "", ""

    request = Request(
        normalized_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; GISIntakeAssistant/0.3; "
                "+property-research-source-name)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    opener = build_opener(_SafeRedirectHandler())

    with opener.open(request, timeout=TITLE_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            return "", ""

        encoding = response.headers.get_content_charset() or "utf-8"
        page = response.read(MAX_METADATA_BYTES).decode(encoding, errors="replace")

    parser = _TitleParser()
    parser.feed(page)
    return _clean_title(parser.title), _clean_title(parser.open_graph_title)


def _friendly_words(value):
    value = unquote(value)
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    value = re.sub(r"[_\-.]+", " ", value)
    value = re.sub(
        r"(?i)(county|city|town|village|parish|borough)$",
        r" \1",
        value,
    )
    words = re.sub(r"\s+", " ", value).strip().split()

    formatted = []
    for word in words:
        if word.lower() in {"gis", "pdf"}:
            formatted.append(word.upper())
        else:
            formatted.append(word.title())
    return " ".join(formatted)


def name_from_url(source_url):
    """Generate a readable fallback name from a URL without fetching it."""
    normalized_url = _normalize_url(source_url)
    parsed = urlparse(normalized_url)
    hostname = (parsed.hostname or "").lower()
    path_parts = [
        part for part in parsed.path.split("/")
        if part and part.lower() not in {"index.html", "index.htm"}
    ]

    lowered_parts = [part.lower() for part in path_parts]
    if "code_of_ordinances" in lowered_parts:
        code_index = lowered_parts.index("code_of_ordinances")
        jurisdiction_parts = path_parts[:code_index]
        while jurisdiction_parts and jurisdiction_parts[-1].lower() in {"codes", "code"}:
            jurisdiction_parts.pop()
        if jurisdiction_parts:
            jurisdiction = _friendly_words(jurisdiction_parts[-1])
            return f"{jurisdiction} Code of Ordinances"

    domain_parts = [
        part for part in hostname.split(".")
        if part and part not in {"www", "com", "org", "net", "gov", "us"}
    ]
    generic_domains = {"arcgis", "municode", "ecode360", "codelibrary", "amlegal"}
    organization_parts = [
        part for part in domain_parts
        if part not in {"gis", "maps", "map", "library"} and part not in generic_domains
    ]

    organization = _friendly_words(organization_parts[-1]) if organization_parts else ""
    has_gis_signal = any(
        part in {"gis", "maps", "map"} for part in domain_parts + lowered_parts
    )

    if organization and has_gis_signal:
        return f"{organization} GIS"
    if organization:
        return organization

    meaningful_path = [
        part for part in path_parts
        if part.lower() not in {"viewer", "home", "public", "apps", "app"}
    ]
    if meaningful_path:
        return _friendly_words(meaningful_path[-1])

    return "Property Research Source"


def choose_source_name(source_url, html_title="", open_graph_title=""):
    """Choose metadata first, then fall back to a cleaned URL-derived name."""
    for candidate in (html_title, open_graph_title):
        cleaned = _clean_title(candidate)
        if cleaned:
            return cleaned
    return name_from_url(source_url)


@st.cache_data(ttl=86_400, show_spinner=False)
def suggest_source_name(source_url):
    """Suggest a source name, tolerating blocked or unavailable webpages."""
    try:
        html_title, open_graph_title = _fetch_page_metadata(source_url)
    except Exception:
        html_title, open_graph_title = "", ""
    return choose_source_name(source_url, html_title, open_graph_title)
