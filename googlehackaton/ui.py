import streamlit as st
import asyncio
import folium
from streamlit_folium import folium_static
from datetime import datetime
import pytz
from src.agent import TripAgent
import time
import requests
from shapely.geometry import LineString, Point
from shapely.ops import substring
from pyproj import Transformer
from walking_path import get_astar_path, trim_segment_to_point

# One-off transformer, UTM32 → WGS84
TRANSFORMER_25832_to_4326 = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
# Set page title and layout
st.set_page_config(page_title="Trip Planner", layout="wide")
st.title("Trip Planner")

# Initialize session state variables if they don't exist
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'trip_data' not in st.session_state:
    st.session_state.trip_data = None

if 'trip_agent' not in st.session_state:
    st.session_state.trip_agent = TripAgent()
    st.session_state.app = st.session_state.trip_agent.create_graph()

if 'processing' not in st.session_state:
    st.session_state.processing = False
    
if 'user_query' not in st.session_state:
    st.session_state.user_query = ""
    
if 'wheelchair_user' not in st.session_state:
    st.session_state.wheelchair_user = False
    
if 'visually_impaired' not in st.session_state:
    st.session_state.visually_impaired = False

# Save user input to session state without causing rerun
def set_user_input():
    st.session_state.user_query = st.session_state.widget_input
    st.session_state.processing = True
    st.session_state.chat_history.append({"role": "user", "content": st.session_state.widget_input})

# Function to create map with route
def create_route_map(trip_data):
    """
    Draws a Folium map of the whole itinerary.
    • Transit legs use simple straight polylines (your original logic).
    • Foot legs call the A* wheelchair/vision friendly service and plot
      the returned geometry segment-by-segment.
    """
    if not trip_data or 'trip' not in trip_data:
        return None

    # --- base map & markers --------------------------------------------------
    center_lat = (trip_data['origin_lat'] + trip_data['destination_lat']) / 2
    center_lon = (trip_data['origin_long'] + trip_data['destination_long']) / 2
    trip_map = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    folium.Marker(
        [trip_data['origin_lat'], trip_data['origin_long']],
        popup=trip_data['origin'],
        icon=folium.Icon(color="green", icon="play", prefix="fa")
    ).add_to(trip_map)
    folium.Marker(
        [trip_data['destination_lat'], trip_data['destination_long']],
        popup=trip_data['destination'],
        icon=folium.Icon(color="red", icon="stop", prefix="fa")
    ).add_to(trip_map)

    # --- colour palette (transit legs keep original behaviour) ---------------
    colours = {"foot": "blue", "metro": "red", "bus": "green",
               "tram": "orange", "train": "purple"}

    # ------------------------------------------------------------------------
    for leg_idx, leg in enumerate(trip_data['trip']['legs']):
        mode = leg['mode'].lower()

        # ---------- 1.  WALKING LEG  ----------------------------------------
        if mode == "foot":
            # Query A* service
            route_data = get_astar_path(
                start_lon=leg['fromPlace']['longitude'],
                start_lat=leg['fromPlace']['latitude'],
                end_lon=leg['toPlace']['longitude'],
                end_lat=leg['toPlace']['latitude']
            )
            print(route_data)

            if not route_data:
                # fall back to straight line if service fails
                points = [
                    [leg['fromPlace']['latitude'], leg['fromPlace']['longitude']],
                    [leg['toPlace']['latitude'], leg['toPlace']['longitude']]
                ]
                folium.PolyLine(points,
                                color=colours["foot"],
                                weight=5,
                                opacity=0.7,
                                popup=f"Walk: {leg['fromPlace']['name']} → {leg['toPlace']['name']}"
                                ).add_to(trip_map)
                continue

            # Assemble detailed geometry
            for seg_no, segment in enumerate(route_data):
                coords_utm = segment['geom_geojson']['coordinates']
                line_utm = LineString(coords_utm)

                # Trim first and last segment so they snap exactly to the OTP coords
                if seg_no == 0:
                    start_utm_pt = Point(TRANSFORMER_25832_to_4326.transform(
                        leg['fromPlace']['longitude'], leg['fromPlace']['latitude']))
                    line_utm = trim_segment_to_point(line_utm, start_utm_pt, trim_start=True)
                elif seg_no == len(route_data) - 1:
                    end_utm_pt = Point(TRANSFORMER_25832_to_4326.transform(
                        leg['toPlace']['longitude'], leg['toPlace']['latitude']))
                    line_utm = trim_segment_to_point(line_utm, end_utm_pt, trim_start=False)

                # Re-project every vertex: (x,y) → (lat,lon)
                coords_latlon = [TRANSFORMER_25832_to_4326.transform(x, y)[::-1]
                                 for x, y in line_utm.coords]

                gatetype   = segment.get('gatetype', 'N/A')
                image_url  = segment.get('bildefil1')
                popup_html = (f"<b>{gatetype}</b><br>"
                              f"{f'<img src=\"{image_url}\" width=\"250\">' if image_url else '<i>No image</i>'}")

                folium.PolyLine(
                    coords_latlon,
                    color=colours["foot"],
                    weight=4,
                    opacity=0.8,
                    tooltip=gatetype,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(trip_map)

        # ---------- 2.  TRANSIT (unchanged)  ---------------------------------
        else:
            colour = colours.get(mode, "gray")
            points = [
                [leg['fromPlace']['latitude'], leg['fromPlace']['longitude']],
                [leg['toPlace']['latitude'],  leg['toPlace']['longitude']]
            ]

            # Intermediate marker (keep your original rule)
            if leg_idx not in (0, len(trip_data['trip']['legs']) - 1):
                folium.Marker(
                    points[0],
                    popup=leg['fromPlace']['name'],
                    icon=folium.Icon(color="blue", icon="exchange", prefix="fa")
                ).add_to(trip_map)

            folium.PolyLine(
                points,
                color=colour,
                weight=5,
                opacity=0.7,
                popup=f"{mode.capitalize()}: {leg['fromPlace']['name']} → {leg['toPlace']['name']}"
            ).add_to(trip_map)

    return trip_map

# Function to format trip details as a readable message
def format_trip_details(trip_data):
    if not trip_data or 'trip' not in trip_data:
        return "Could not plan trip. Please try again with more details."
    
    trip = trip_data['trip']
    
    # Format total duration in minutes
    total_duration_mins = trip['duration'] // 60
    
    message = f"**Trip Summary:**\n\n"
    message += f"* From: {trip_data['origin']}\n"
    message += f"* To: {trip_data['destination']}\n"
    message += f"* Total duration: {total_duration_mins} minutes\n\n"
    
    message += "**Route:**\n\n"
    
    for i, leg in enumerate(trip['legs'], 1):
        # Format times
        start_time = datetime.fromisoformat(leg['expectedStartTime'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(leg['expectedEndTime'].replace('Z', '+00:00'))
        
        # Format leg type
        mode = leg['mode'].capitalize()
        if leg['line'] and leg['line']['publicCode']:
            mode += f" {leg['line']['publicCode']}"
            if leg['line']['name']:
                mode += f" ({leg['line']['name']})"
        
        # Format distance
        distance_km = leg['distance'] / 1000
        
        message += f"{i}. **{mode}**: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n"
        message += f"   From: {leg['fromPlace']['name']} → To: {leg['toPlace']['name']}\n"
        message += f"   Distance: {distance_km:.2f} km\n\n"
    
    return message

# Create two main columns - chat and map
col1, col2 = st.columns([3, 2])

# Display map in the right column
with col2:
    st.subheader("Route Map")
    map_placeholder = st.empty()
    
    # Display map if we have trip data
    if st.session_state.trip_data is not None:
        trip_map = create_route_map(st.session_state.trip_data)
        if trip_map:
            with map_placeholder:
                folium_static(trip_map, width=500, height=500)

# Display chat history in the left column
with col1:
    st.subheader("Chat")
    chat_container = st.container(height=400)
    
    with chat_container:
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.chat_message("user").write(message["content"])
            else:
                st.chat_message("assistant").write(message["content"])
    
    # Show loading message if processing
    if st.session_state.processing:
        with st.chat_message("assistant"):
            st.write("Planning your trip...")
    
    # Add accessibility toggles
    col_wheel, col_vision = st.columns(2)
    with col_wheel:
        st.session_state.wheelchair_user = st.toggle("Rullestolbruker", value=st.session_state.wheelchair_user)
    with col_vision:
        st.session_state.visually_impaired = st.toggle("Svaksynt", value=st.session_state.visually_impaired)
    
    # Input for new messages
    st.chat_input("Hvor vil du reise?", key="widget_input", on_submit=set_user_input, disabled=st.session_state.processing)

# Handle trip planning in the background
if st.session_state.processing and st.session_state.user_query:
    with st.spinner("Planning your trip..."):
        # Create question dictionary with accessibility preferences
        user_query = st.session_state.user_query
        handicap_info = []
        
        if st.session_state.wheelchair_user:
            handicap_info.append("wheelchair user")
        if st.session_state.visually_impaired:
            handicap_info.append("visually impaired")
            
        if handicap_info:
            user_query += " (NB: I am a/an " + "/".join(handicap_info) + ".)"
            
        question = {"question": user_query}
        
        # Run the async function using a loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        trip_data = loop.run_until_complete(st.session_state.app.ainvoke(question))
        
        # Store the trip data in session state
        st.session_state.trip_data = trip_data
        
        # Format response
        response_text = format_trip_details(trip_data)
        
        # Add assistant response to chat history
        st.session_state.chat_history.append({"role": "assistant", "content": response_text})
        
        # Reset processing flag
        st.session_state.processing = False
        st.session_state.user_query = ""
        
        # Force refresh to update UI
        st.rerun()
