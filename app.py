from flask import Flask, render_template, request
import folium
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from geopy.geocoders import GoogleV3
from geopy.distance import geodesic
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Google Sheets Setup
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('stony-brook-projects-1277d6088e55.json', scope)
client = gspread.authorize(creds)

# Google Geocoding API Key
geolocator = GoogleV3(api_key=os.getenv('GOOGLE_MAPS_API_KEY'))

sheet = client.open('Longislandfallsprevention_Locations').sheet1

# Load map with default location and display nearby locations
def create_map(default_location=[40.7954, -73.1952]):
    m = folium.Map(location=default_location, zoom_start=10)
    data = sheet.get_all_records()  # Fetch all data from the Google Sheet

    for idx, row in enumerate(data):
        location = [row['Latitude'], row['Longitude']]
        popup_html = f"""
        <b>{row['Location Name']}</b><br>
        Category: {row['Category']}<br>
        """
        popup = folium.Popup(popup_html, max_width=300)
        folium.Marker(location, popup=popup, tooltip="Click for details").add_to(m)
    
    return m
    

# Calculate the distance between two points
def calculate_distance(coord1, coord2):
    return geodesic(coord1, coord2).miles

# Route for displaying the map and locations
@app.route('/', methods=['GET', 'POST'])
def index():
    search_location = None
    nearby_locations = []

    if request.method == 'POST':
        search_location = request.form['location']
        location = geolocator.geocode(search_location)

        if location:
            # Create the map centered on the searched location
            map_obj = create_map([location.latitude, location.longitude])

            # Get all data from the Google Sheet
            data = sheet.get_all_records()

            # Calculate distances and find nearby locations
            for row in data:
                site_coords = (row['Latitude'], row['Longitude'])
                user_coords = (location.latitude, location.longitude)
                distance = calculate_distance(user_coords, site_coords)
                
                if distance <= 100:  # Only include locations within 50 miles
                    row['Distance'] = distance
                    nearby_locations.append(row)

            # Sort nearby locations by distance
            nearby_locations.sort(key=lambda x: x['Distance'])
        else:
            map_obj = create_map()  # Fallback if location not found

    else:
        map_obj = create_map()
        nearby_locations = sheet.get_all_records()
        search_location = 'None'


    map_html = map_obj._repr_html_()  # Convert map to HTML representation
    return render_template(
        'index.html', map=map_html, locations=nearby_locations, search_location=search_location)

if __name__ == '__main__':
    app.run(debug=True, port=5005, host='0.0.0.0')
