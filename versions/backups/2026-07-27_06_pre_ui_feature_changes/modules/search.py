"""Public source discovery, filtering, and duplicate suppression."""

from ddgs import DDGS


def is_bad_result(result):
    href = result.get("href", "").lower()
    title = result.get("title", "").lower()

    blocked_terms = [
        "wikipedia", "wikidata", "facebook", "reddit", "linkedin", "youtube",
        "zillow", "realtor.com", "redfin", "homes.com",
    ]

    return any(term in f"{title} {href}" for term in blocked_terms)


def result_matches_place(result, city, county, state):
    title = result.get("title", "").lower()
    href = result.get("href", "").lower()
    body = result.get("body", "").lower()
    combined_text = f"{title} {href} {body}"

    city_key = city.strip().lower()
    county_key = county.strip().lower()
    county_short = county_key.replace(" county", "")
    state_key = state.strip().lower()

    place_terms = [city_key, county_key, county_short, state_key]
    place_terms = [term for term in place_terms if term]

    return any(term in combined_text for term in place_terms)


def search_candidates(query, city, county, state, max_results=3, mode="general"):
    results = []

    try:
        with DDGS() as ddgs:
            search_results = ddgs.text(query, max_results=15)

            for result in search_results:
                if is_bad_result(result):
                    continue

                if not result_matches_place(result, city, county, state):
                    continue

                title = result.get("title", "").lower()
                href = result.get("href", "").lower()
                body = result.get("body", "").lower()
                combined_text = f"{title} {href} {body}"

                if mode == "zoning":
                    must_have_zoning = any(term in combined_text for term in [
                        "zoning", "zone district", "zoning map",
                        "zoning viewer", "zoning ordinance", "land use",
                    ])
                    must_be_map_or_official = any(term in combined_text for term in [
                        "map", "maps", "viewer", "pdf", "arcgis",
                        "municode", ".gov", "planning",
                    ])
                    if not (must_have_zoning and must_be_map_or_official):
                        continue
                else:
                    allowed_keywords = [
                        "gis", "parcel", "assessor", "property",
                        "map", "maps", "viewer", "arcgis",
                    ]
                    if not any(keyword in combined_text for keyword in allowed_keywords):
                        continue

                results.append(result)

                if len(results) == max_results:
                    break

    except Exception:
        pass

    return results


def search_general_sources(city, county, state):
    query = f"{county} {state} official GIS parcel viewer"
    return search_candidates(query, city, county, state, max_results=3, mode="general")


def search_zoning_sources(city, county, state):
    queries = [
        f"{city} {state} official zoning map",
        f"{county} {state} official zoning map PDF",
        f"{city} {state} zoning viewer",
        f"{county} {state} zoning ordinance map",
    ]

    results = []
    seen_urls = set()

    for query in queries:
        candidates = search_candidates(query, city, county, state, max_results=3, mode="zoning")
        for candidate in candidates:
            href = candidate.get("href", "")
            if href and href not in seen_urls:
                results.append(candidate)
                seen_urls.add(href)

            if len(results) == 3:
                return results

    return results


def search_setback_sources(city, county, state):
    queries = [
        f'"{city}" "{state}" zoning ordinance',
        f'"{city}" "{state}" development code',
        f'"{city}" "{state}" land development code',
        f'"{city}" "{state}" setback requirements',
        f'"{county}" "{state}" zoning ordinance',
    ]

    results = []
    seen_urls = set()

    try:
        with DDGS() as ddgs:
            for query in queries:
                search_results = ddgs.text(query, max_results=15)

                for result in search_results:
                    if is_bad_result(result):
                        continue

                    if not result_matches_place(result, city, county, state):
                        continue

                    href = result.get("href", "").lower()
                    title = result.get("title", "").lower()
                    body = result.get("body", "").lower()
                    combined_text = f"{title} {href} {body}"

                    if not href or href in seen_urls:
                        continue

                    has_code_signal = any(term in combined_text for term in [
                        "zoning ordinance",
                        "zoning code",
                        "development code",
                        "land development code",
                        "municipal code",
                        "code of ordinances",
                        "setback",
                        "setbacks",
                        "yard requirements",
                        "minimum yard",
                    ])

                    is_official_or_code_source = any(term in href for term in [
                        ".gov",
                        "municode",
                        "ecode360",
                        "codelibrary",
                        "amlegal",
                        "library.municode",
                        "citycode",
                        "planning",
                    ])

                    is_bad_source = any(term in href for term in [
                        ".doc",
                        ".docx",
                        "legalmatch",
                        "wikipedia",
                        "wikidata",
                        "facebook",
                        "reddit",
                        "linkedin",
                        "youtube",
                        "zillow",
                        "realtor.com",
                        "redfin",
                        "homes.com",
                        "news",
                        "blog",
                    ])

                    if not has_code_signal:
                        continue

                    if not is_official_or_code_source:
                        continue

                    if is_bad_source:
                        continue

                    results.append(result)
                    seen_urls.add(href)

                    if len(results) == 3:
                        return results

    except Exception:
        pass

    return results


def remove_saved_duplicates(candidates, match):
    if match.empty:
        return candidates

    saved_urls = set(match["source_url"].astype(str).str.strip())
    return [
        candidate for candidate in candidates
        if candidate.get("href", "").strip() not in saved_urls
    ]
