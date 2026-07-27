# GIS Intake Assistant

Streamlit research assistant for Evolution Drafting property intake. It identifies
the project jurisdiction, reuses verified research sources, discovers additional
GIS/zoning/code links, and optionally surfaces special-condition research sources.

The app narrows research; it does not make final zoning, hazard, environmental,
or compliance determinations.

## Run locally

From the project directory:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Run the automated regression suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run non-writing visual QA:

```powershell
.\.venv\Scripts\python.exe -m streamlit run tests\ui_preview.py
```

Run repeatable live QA against public civic-building addresses:

```powershell
.\.venv\Scripts\python.exe -m tests.live_qa
```

Add `--extended` to include zoning, setback, and one Special Conditions search.
The live QA script does not connect to or write to Google Sheets.

## Source library matching

The `GIS Sources` tab keeps the original nine columns and appends two optional
columns:

```text
city
jurisdiction_level
```

Supported jurisdiction levels:

```text
county
city
state
regional
unknown
```

Matching order is:

1. Exact county and state.
2. Exact city and state.
3. Explicit state-level sources.

Legacy rows with a county continue to behave as county sources. Unscoped legacy,
regional, and unknown rows are not automatically shown statewide.

## Special Conditions Source Discovery

The optional on-demand panel searches for research sources covering:

- Flood/floodplain
- Wind/storm requirements
- Wildfire risk
- Coastal/shoreland restrictions
- Historic districts
- Zoning overlays
- Wetlands
- Septic/well constraints
- Steep slopes/landslides
- Environmental/special hazard areas

`Source found` means a locality-matching government source was discovered.
`Needs verification` identifies a national screening source. Neither status means
the condition applies to the project parcel.

## Project structure

```text
app.py                    Streamlit orchestration
modules/config.py         Product and data constants
modules/geocoder.py       Address lookup and county fallback
modules/google_sheets.py  Source library persistence and matching
modules/search.py         GIS, zoning, and code discovery
modules/source_names.py   Cached URL-to-name suggestions
modules/conditions.py     Special Conditions source discovery
modules/ui.py             Reusable Streamlit UI
tests/                    Automated, visual, and live QA
documentation/            Handoffs, design references, and release notes
versions/backups/         Script backups captured before edits
```

## Security

Local Streamlit secrets remain excluded by `.gitignore`. Never commit:

```text
.streamlit/secrets.toml
.env
.env.local
credentials.json
service_account.json
*.pem
```

The Google private-key newline normalization in `modules/google_sheets.py` is
required for Streamlit Cloud and must remain in place.
