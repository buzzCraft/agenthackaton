from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from datetime import datetime
import src.datamodel as dm
import requests
from datetime import datetime, timezone

def setup_model():
    # LLM with function call
    llm = ChatVertexAI(
            model_name="gemini-2.5-pro-preview-05-06",
            project="PROJECTID",
            location="us-central1",
            endpoint_version="v1",
            max_output_tokens=2000, 
            temperature=0.1,        
        )
    return llm

async def check_trip(state):
    """
    Check that state contains origin, destination, time, and handicap.
    """
    # Check if all required fields are present
    required_fields = ["origin", "destination", "time", "handicap"]
    for field in required_fields:
        if field not in state:
            print(f"Missing field: {field}")
            return "False"
    return "True"

async def extract_data(state):
    question = state.get("question")
    llm = setup_model()
    structured_llm_grader = llm.with_structured_output(dm.FindUserData)

    # Prompt
    system = """Your task is to find where the user is traveling from and to."""
    grade_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", "Given this question {question}, fill out the following fields: origin, destination, time, handicap. "
             "If the user does not specify a time, use 'Now'. If the user does not specify a handicap, use 'None'. "
             "If the user does not specify a location, use 'None'. "),
        ]
    )

    retrieval_grader = grade_prompt | structured_llm_grader
    ans = retrieval_grader.invoke({"question": question})
    state["origin"] = ans.origin
    state["destination"] = ans.destination
    state["time"] = ans.time
    state["handicap"] = ans.handicap
    return state



async def get_coordinates(state):
    """
    Retrieves the latitude and longitude for a given place name using Entur's Geocoder API.

    Parameters:
    - place_name (str): The name or address of the place to geocode.
    - client_name (str): Identifier for the client application. Replace with your application's name.

    Returns:
    - tuple: (latitude, longitude) if found, else None.
    """
    origin = state.get("origin")
    destination = state.get("destination")

    origin = origin # Strip trailing "i Oslo" if present
    if origin.endswith("i Oslo"):
        origin = origin[:-len("i Oslo")].strip()
    destination = destination
    if destination.endswith("i Oslo"):
        destination = destination[:-len("i Oslo")].strip()

    origin_coordinates = await get_coordinates_for_place(origin)
    destination_coordinates = await get_coordinates_for_place(destination)
    if origin_coordinates:
        state["origin_lat"] = origin_coordinates[0]
        state["origin_long"] = origin_coordinates[1]
    else:
        print(f"Could not find coordinates for '{origin}'.")
    if destination_coordinates:
        state["destination_lat"] = destination_coordinates[0]
        state["destination_long"] = destination_coordinates[1]
    else:
        print(f"Could not find coordinates for '{destination}'.")
    return state

async def get_coordinates_for_place(place_name):
    url = "https://api.entur.io/geocoder/v1/autocomplete"
    headers = {
        "ET-Client-Name": "Google-VertexAI-LLM-hackathon",
    }
    params = {
        "text": place_name,
        "lang": "en",
        "size": 1  # Limit to the top result
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        features = data.get("features")
        if features:
            coordinates = features[0]["geometry"]["coordinates"]
            # Entur returns coordinates in [longitude, latitude] format
            return coordinates[1], coordinates[0]
        else:
            print(f"No results found for '{place_name}'.")
            return None
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    

async def plan_trip_entur(state):
    client_name="Google-VertexAI-LLM-hackathon"
    url = "https://api.entur.io/journey-planner/v3/graphql"
    headers = {
        "Content-Type": "application/json",
        "ET-Client-Name": client_name
    }

    iso_time = datetime.now(timezone.utc).isoformat()
        


    query = f"""
    query {{
      trip(
        from: {{
          coordinates: {{ latitude: {state.get("origin_lat")}, longitude: {state.get("origin_long")} }}
        }}
        to: {{
          coordinates: {{ latitude: {state.get("destination_lat")}, longitude: {state.get("destination_long")} }}
        }}
        dateTime: "{iso_time}"
        arriveBy: {"false"}
        modes: {{
          accessMode: foot
          egressMode: foot
          directMode: foot
          transportModes: [
            {{ transportMode: bus }}
            {{ transportMode: rail }}
            {{ transportMode: tram }}
            {{ transportMode: metro }}
            {{ transportMode: water }}
          ]
        }}
      ) {{
        tripPatterns {{
          duration
          legs {{
            mode
            expectedStartTime
            expectedEndTime
            fromPlace {{
              name
              latitude
              longitude
            }}
            toPlace {{
              name
              latitude
              longitude
            }}
            distance
            line {{
              publicCode
              name
            }}
          }}
        }}
      }}
    }}
    """

    response = requests.post(url, headers=headers, json={"query": query})
    if response.status_code == 200:
        trip_data = response.json()
        state["trip"] = trip_data["data"]["trip"]["tripPatterns"][0]
        return state
    else:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")