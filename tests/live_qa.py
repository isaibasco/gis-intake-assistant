"""Optional live QA using public civic addresses and no Google Sheet access."""

import argparse
import json

from modules.conditions import _discover_condition_sources
from modules.geocoder import finalize_location_result, lookup_location
from modules.search import (
    search_general_sources,
    search_setback_sources,
    search_zoning_sources,
)


PUBLIC_CASES = (
    ("200 E Colfax Ave, Denver, Colorado", "Denver", "Colorado"),
    ("131 E Main St, Dandridge, Tennessee", "Dandridge", "Tennessee"),
    ("3500 Pan American Dr, Miami, Florida", "Miami", "Florida"),
)


def _hosts(candidates):
    hosts = []
    for candidate in candidates:
        parts = str(candidate.get("href", "")).split("/")
        if len(parts) > 2:
            hosts.append(parts[2])
    return hosts


def run_live_qa(extended=False):
    report = []
    resolved_cases = []

    for address, city, state in PUBLIC_CASES:
        location = finalize_location_result(lookup_location(address, state))
        general = search_general_sources(
            city,
            location["county"],
            location["state"],
        )
        entry = {
            "address": address,
            "confirmed_address": location["confirmed_address"],
            "city": city,
            "county": location["county"],
            "state": location["state"],
            "lookup_status": location["lookup_status"],
            "warning": location["warning"],
            "gis_candidate_count": len(general),
            "gis_candidate_hosts": _hosts(general),
        }
        report.append(entry)
        resolved_cases.append((entry, location))

    if extended:
        for entry, location in resolved_cases[1:]:
            city = entry["city"]
            county = location["county"]
            state = location["state"]
            zoning = search_zoning_sources(city, county, state)
            setbacks = search_setback_sources(city, county, state)
            entry.update({
                "zoning_candidate_count": len(zoning),
                "zoning_candidate_hosts": _hosts(zoning),
                "setback_candidate_count": len(setbacks),
                "setback_candidate_hosts": _hosts(setbacks),
            })

        miami_entry, miami_location = resolved_cases[-1]
        condition_results = _discover_condition_sources(
            miami_entry["city"],
            miami_location["county"],
            miami_location["state"],
        )
        miami_entry["special_conditions"] = {
            "category_count": len(condition_results),
            "categories_with_sources": sum(
                bool(condition["sources"])
                for condition in condition_results
            ),
            "local_government_source_count": sum(
                source["status"] == "Source found"
                for condition in condition_results
                for source in condition["sources"]
            ),
            "national_screening_source_count": sum(
                source["status"] == "Needs verification"
                for condition in condition_results
                for source in condition["sources"]
            ),
        }

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Also run zoning, setback, and Special Conditions discovery.",
    )
    arguments = parser.parse_args()
    print(json.dumps(run_live_qa(extended=arguments.extended), indent=2))
