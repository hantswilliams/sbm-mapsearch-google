# Basic Flask - Maps - Google Sheets Web Application

## Description
This is a basic web application that uses Flask, Google Maps, and Google Sheets. The application reads data from a Google Sheet and displays it on a map. The application also allows users to add new data to the Google Sheet.

## Installation
1. Clone the repository
2. Install the required packages
```
pip install -r requirements.txt
```
3. Create a Google Sheet and share it with the service account email address
4. Create a service account and download the JSON key file
5. Update the app.py file with the path to the JSON key file
6. Run the application
```
python app.py
```

## Embedding Deployed App into WordPress
- The app can be embedded into a WordPress site using an iframe
- Create a new page in WordPress
- Switch to the HTML editor
- Add the following code to embed the app, as a example:
```html
<iframe src="https://sbm-falls-map-714433739872.us-central1.run.app/" width="100%" height="800px"></iframe>
```

## Note - Google Sheets
- https://docs.gspread.org/en/latest/oauth2.html#enable-api-access-for-a-project
- Go to your spreadsheet and share it with a client_email from the json key file that is generated. Just like you do with any other Google account. If you don’t do this, you’ll get a `gspread.exceptions.SpreadsheetNotFound` exception when trying to access this spreadsheet from your application or a script.
- In my current setup/json file it looks like:

```json
  "client_email": "googlesheets-access@stony-brook-projects.iam.gserviceaccount.com",
```

- The current google sheet link is under hantsawilliams@gmail.com, and here is the link <a href="https://docs.google.com/spreadsheets/d/1IQe_EHFO-LmR89WRVZDaTHfR4ybwL0DukCT4m3iN8Dk/edit?gid=0#gid=0 target=_blank">here</a>