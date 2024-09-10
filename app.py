from flask import Flask, render_template, request
import folium
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from geopy.geocoders import GoogleV3
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Google Sheets Setup
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('stony-brook-projects-1277d6088e55.json', scope)
client = gspread.authorize(creds)

# Replace 'YOUR_GOOGLE_API_KEY' with your actual API key
geolocator = GoogleV3(api_key=os.getenv('GOOGLE_MAPS_API_KEY'))

# Check if client is authenticated
print(client)

sheet = client.open('Longislandfallsprevention_Locations').sheet1

# Load map with default location
def create_map(default_location=[40.7128, -74.0060]):
    m = folium.Map(location=default_location, zoom_start=10)
    data = sheet.get_all_records()  # Fetch all data from the Google Sheet

    for row in data:
        location = [row['Latitude'], row['Longitude']]
        popup = folium.Popup(f"<b>{row['Location Name']}</b><br>{row['Details']}", max_width=300)
        folium.Marker(location, popup=popup).add_to(m)
    
    return m

# Route for displaying the map
@app.route('/', methods=['GET', 'POST'])
def index():
    search_location = None

    if request.method == 'POST':
        search_location = request.form['location']
        location = geolocator.geocode(search_location)
        if location:
            map_obj = create_map([location.latitude, location.longitude])
        else:
            map_obj = create_map()  # Fallback if location is not found
    else:
        map_obj = create_map()

    map_html = map_obj._repr_html_()  # Convert map to HTML representation
    return render_template('index.html', map=map_html)

if __name__ == '__main__':
    app.run(debug=True, port=5005, host='0.0.0.0')
