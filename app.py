import streamlit as st
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

GIS_PORTALS = {
    ("mesa county", "colorado"): {
        "name": "Mesa County GIS Viewer",
        "url": "https://emap.mesacounty.us/viewer/",
    }
}

st.set_page_config(page_title="GIS Intake Assistant", layout="wide")

st.title("GIS Intake Assistant")
st.write("Enter a project address to find the likely GIS / parcel research source.")

project_address = st.text_input("Project Address", placeholder="Example: 123 Main St")
city = st.text_input("City", placeholder="Example: Grand Junction")
state = st.text_input("State", placeholder="Example: Colorado")

project_type = st.selectbox(
    "Project Type",
    [
        "Not selected",
        "New Build",
        "Addition",
        "Renovation",
        "Interior Alteration",
        "Occupancy Change",
        "Other",
    ],
)

full_address = f"{project_address}, {city}, {state}"

if st.button("Find GIS Portal"):
    if not project_address or not city or not state:
        st.error("Please enter the project address, city, and state.")
    else:
        geolocator = Nominatim(user_agent="gis_intake_assistant")

        try:
            location = geolocator.geocode(full_address, addressdetails=True, timeout=10)

            if location:
                st.success("Location found.")

                address_data = location.raw.get("address", {})
                detected_county = address_data.get("county", "")
                detected_state = address_data.get("state", "")

                county_key = detected_county.lower()
                state_key = detected_state.lower()
                portal = GIS_PORTALS.get((county_key, state_key))

                st.subheader("Project Intake")
                st.write(f"Project Type: {project_type}")
                st.write(f"Entered Address: {full_address}")

                st.subheader("Confirmed Location")
                st.write(location.address)

                st.subheader("Detected Area")
                st.write(f"County: {detected_county}")
                st.write(f"State: {detected_state}")

                st.subheader("GIS Portal")
                if portal:
                    st.markdown(f"[{portal['name']}]({portal['url']})")
                else:
                    fallback_query = f"{detected_county} {detected_state} GIS parcel viewer"
                    search_query = fallback_query.replace(" ", "+")
                    google_search = f"https://www.google.com/search?q={search_query}"
                    st.warning("No direct GIS portal saved yet for this county/state.")
                    st.markdown(f"[Search for {detected_county} GIS Portal]({google_search})")
                    
            else:
                st.warning("No address result found. Try simplifying the address.")

        except (GeocoderTimedOut, GeocoderUnavailable):
            st.error("The address lookup service timed out. Try again.")