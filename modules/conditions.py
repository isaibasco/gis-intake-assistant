"""On-demand discovery of official special-condition research sources."""

from urllib.parse import urlparse

import streamlit as st
from ddgs import DDGS

from modules.search import is_bad_result


CONDITION_SPECS = (
    {
        "key": "flood",
        "label": "Flood / Floodplain",
        "query": "floodplain flood hazard map",
        "signals": ("flood", "floodplain", "fema", "nfhl"),
        "fallback": {
            "source_name": "FEMA Flood Map Service Center",
            "source_url": "https://msc.fema.gov/portal/home",
        },
    },
    {
        "key": "wind_storm",
        "label": "Wind / Storm Requirements",
        "query": "wind design criteria storm hazard building requirements",
        "signals": ("wind", "storm", "hurricane", "tornado", "design criteria"),
        "fallback": {
            "source_name": "FEMA Resilience Analysis and Planning Tool",
            "source_url": (
                "https://www.fema.gov/emergency-managers/practitioners/"
                "resilience-analysis-and-planning-tool"
            ),
        },
    },
    {
        "key": "wildfire",
        "label": "Wildfire Risk",
        "query": "wildfire risk map planning",
        "signals": ("wildfire", "wildland", "fire hazard", "wui"),
        "fallback": {
            "source_name": "USDA Wildfire Risk to Communities",
            "source_url": (
                "https://research.fs.usda.gov/firelab/products/dataandtools/"
                "wildfire-risk-communities"
            ),
        },
    },
    {
        "key": "coastal",
        "label": "Coastal / Shoreland",
        "query": "coastal shoreland restrictions hazard map",
        "signals": ("coastal", "shoreland", "shoreline", "sea level", "storm surge"),
        "fallback": {
            "source_name": "NOAA Coastal Flood Exposure Mapper",
            "source_url": "https://www.coast.noaa.gov/floodexposure/",
        },
    },
    {
        "key": "historic",
        "label": "Historic District",
        "query": "historic district preservation map",
        "signals": ("historic", "preservation", "national register"),
        "fallback": {
            "source_name": "National Register of Historic Places Map",
            "source_url": (
                "https://www.nps.gov/maps/full.html"
                "?mapId=7ad17cc9-b808-4ff8-a2f9-a99909164466"
            ),
        },
    },
    {
        "key": "overlay",
        "label": "Zoning Overlay District",
        "query": "zoning overlay district official map",
        "signals": ("overlay", "zoning district", "special district"),
        "fallback": None,
    },
    {
        "key": "wetlands",
        "label": "Wetlands",
        "query": "wetlands inventory map",
        "signals": ("wetland", "nwi", "waters of the united states"),
        "fallback": {
            "source_name": "U.S. Fish & Wildlife Service Wetlands Mapper",
            "source_url": (
                "https://www.fws.gov/program/national-wetlands-inventory/"
                "wetlands-mapper"
            ),
        },
    },
    {
        "key": "septic_well",
        "label": "Septic / Well Constraints",
        "query": "health department septic well permit requirements",
        "signals": ("septic", "onsite wastewater", "well permit", "well water"),
        "fallback": {
            "source_name": "EPA SepticSmart",
            "source_url": "https://www.epa.gov/septic/septicsmart",
        },
    },
    {
        "key": "steep_slope",
        "label": "Steep Slope / Landslide",
        "query": "steep slope landslide hazard map",
        "signals": ("steep slope", "landslide", "slope hazard"),
        "fallback": {
            "source_name": "USGS Landslide Inventory and Susceptibility Map",
            "source_url": (
                "https://www.usgs.gov/tools/"
                "us-landslide-inventory-and-susceptibility-map"
            ),
        },
    },
    {
        "key": "environmental",
        "label": "Environmental / Special Hazard Area",
        "query": "environmental hazard area official map",
        "signals": (
            "environmental",
            "hazard area",
            "brownfield",
            "superfund",
            "contamination",
        ),
        "fallback": {
            "source_name": "EPA EnviroAtlas Interactive Map",
            "source_url": (
                "https://enviroatlas.epa.gov/enviroatlas/interactivemap/"
            ),
        },
    },
)


def _is_government_url(source_url):
    hostname = (urlparse(source_url).hostname or "").lower().rstrip(".")
    return (
        hostname.endswith(".gov")
        or hostname.endswith(".mil")
        or hostname.endswith(".us")
    )


def _result_matches_locality(result, city, county):
    combined_text = " ".join(
        str(result.get(field, "")).lower()
        for field in ("title", "href", "body")
    )
    county_key = county.strip().lower()
    locality_terms = [
        city.strip().lower(),
        county_key,
        county_key.replace(" county", ""),
    ]
    locality_terms = [term for term in locality_terms if len(term) >= 3]
    return any(term in combined_text for term in locality_terms)


def _result_matches_condition(result, signals):
    combined_text = " ".join(
        str(result.get(field, "")).lower()
        for field in ("title", "href", "body")
    )
    return any(signal in combined_text for signal in signals)


def _local_source_from_results(results, spec, city, county):
    for result in results:
        source_url = str(result.get("href", "")).strip()
        if not source_url or is_bad_result(result):
            continue
        if not _is_government_url(source_url):
            continue
        if not _result_matches_locality(result, city, county):
            continue
        if not _result_matches_condition(result, spec["signals"]):
            continue

        return {
            "source_name": (
                str(result.get("title", "")).strip()
                or f"{spec['label']} government source"
            ),
            "source_url": source_url,
            "status": "Source found",
            "scope": "Local or state government candidate",
        }
    return None


def _discover_condition_sources(city, county, state):
    place_parts = [part.strip() for part in (city, county, state) if part.strip()]
    place_query = " ".join(f'"{part}"' for part in place_parts)
    discovered = []

    try:
        ddgs_context = DDGS()
    except Exception:
        ddgs_context = None

    try:
        for spec in CONDITION_SPECS:
            sources = []
            if ddgs_context is not None:
                try:
                    results = ddgs_context.text(
                        f"{place_query} official {spec['query']}",
                        max_results=8,
                    )
                    local_source = _local_source_from_results(
                        results,
                        spec,
                        city,
                        county,
                    )
                    if local_source:
                        sources.append(local_source)
                except Exception:
                    pass

            fallback = spec["fallback"]
            if fallback and not any(
                source["source_url"] == fallback["source_url"]
                for source in sources
            ):
                sources.append({
                    **fallback,
                    "status": "Needs verification",
                    "scope": "National screening source",
                })

            discovered.append({
                "key": spec["key"],
                "label": spec["label"],
                "sources": sources,
            })
    finally:
        if ddgs_context is not None:
            close = getattr(ddgs_context, "close", None)
            if callable(close):
                close()

    return discovered


@st.cache_data(ttl=86_400, show_spinner=False)
def discover_condition_sources(city, county, state):
    """Discover source leads without making parcel-level determinations."""
    return _discover_condition_sources(city, county, state)
