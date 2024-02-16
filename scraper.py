import re
import json
import datetime
from zoneinfo import ZoneInfo
import html

import requests

from db import get_db_conn


URL = 'https://visitseattle.org/events/page/'
URL_LIST_FILE = './data/links.json'
URL_DETAIL_FILE = './data/data.json'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search.php'
NWS_URL_TEMPLATE = 'https://api.weather.gov/points/{latitude},{longitude}'


def get_lat_long(location):
    params = {'format': 'json', 'q': location, 'limit': 1}
    response = requests.get(NOMINATIM_URL, params=params)
    data = response.json()
    if data:
        return data[0]['lat'], data[0]['lon']
    return None, None


def get_weather_data(latitude, longitude):
    url = NWS_URL_TEMPLATE.format(latitude=latitude, longitude=longitude)
    response = requests.get(url)
    data = response.json()

    #print("Complete API response:", json.dumps(data, indent=2))

    properties = data.get('properties', {})
    forecast_url = properties.get('forecast')

    if not forecast_url:
        return {
            'condition': None,
            'temperature': None,
            'temperature_trend': None,
            'humidity': None,
            'windspeed': None,
            'winddirection': None,
        }

    forecast_response = requests.get(forecast_url)
    forecast_data = forecast_response.json()

    periods = forecast_data.get('properties', {}).get('periods', [])

    if not periods:
        return {
            'condition': None,
            'temperature': None,
            'temperature_trend': None,
            'humidity': None,
            'windspeed': None,
            'winddirection': None,
        }

    # Extracting the relevant data from the first period
    first_period = periods[0]

    return {
        'condition': first_period.get('shortForecast'),
        'temperature': first_period.get('temperature'),
        'temperature_trend': first_period.get('temperatureTrend'),
        'humidity': first_period.get('relativeHumidity', {}).get('value'),
        'windspeed': first_period.get('windSpeed'),
        'winddirection': first_period.get('windDirection'),
    }


def list_links():
    res = requests.get(URL + '1/')
    last_page_no = int(re.findall(r'bpn-last-page-link"><a href=".+?/page/(\d+?)/.+" title="Navigate to last page">', res.text)[0])

    links = []
    for page_no in range(1, last_page_no + 1):
        res = requests.get(URL + str(page_no) + '/')
        links.extend(re.findall(r'<h3 class="event-title"><a href="(https://visitseattle.org/events/.+?/)" title=".+?">.+?</a></h3>', res.text))

    json.dump(links, open(URL_LIST_FILE, 'w'))


def get_detail_page():
    links = json.load(open(URL_LIST_FILE, 'r'))
    data = []
    for link in links:
        try:
            row = {}
            res = requests.get(link)
            row['title'] = html.unescape(re.findall(r'<h1 class="page-title" itemprop="headline">(.+?)</h1>', res.text)[0])
            datetime_venue = re.findall(r'<h4><span>.*?(\d{1,2}/\d{1,2}/\d{4})</span> \| <span>(.+?)</span></h4>', res.text)[0]
            row['date'] = datetime.datetime.strptime(datetime_venue[0], '%m/%d/%Y').replace(tzinfo=ZoneInfo('America/Los_Angeles')).isoformat()
            row['venue'] = datetime_venue[1].strip()
            metas = re.findall(r'<a href=".+?" class="button big medium black category">(.+?)</a>', res.text)
            row['category'] = html.unescape(metas[0])
            row['location'] = metas[1]

            # Retrieve latitude, longitude
            latitude, longitude = get_lat_long(f"{row['venue']}, Seattle")
            row['latitude'] = latitude
            row['longitude'] = longitude

            # Retrieve weather data
            if latitude and longitude:
                weather_data = get_weather_data(latitude, longitude)
                row.update(weather_data)

            data.append(row)
        except IndexError as e:
            print(f'Error: {e}')
            print(f'Link: {link}')
    json.dump(data, open(URL_DETAIL_FILE, 'w'))


def insert_to_pg():
    q = '''
    CREATE TABLE IF NOT EXISTS events (
        url TEXT PRIMARY KEY,
        title TEXT,
        date TIMESTAMP WITH TIME ZONE,
        venue TEXT,
        category TEXT,
        location TEXT,
        latitude FLOAT,
        longitude FLOAT,
        weather_condition TEXT,
        temperature FLOAT,
        temperature_trend TEXT,
        humidity FLOAT,
        windspeed TEXT,
        winddirection TEXT
    );
    '''
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(q)

    urls = json.load(open(URL_LIST_FILE, 'r'))
    data = json.load(open(URL_DETAIL_FILE, 'r'))
    for url, row in zip(urls, data):
        q = '''
        INSERT INTO events (url, title, date, venue, category, location, latitude, longitude, 
        weather_condition, temperature, temperature_trend, humidity, windspeed, winddirection)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING;
        '''
        cur.execute(q, (url, row['title'], row['date'], row['venue'], row['category'], row['location'], row['latitude'], row['longitude'],
                        row.get('condition'), row.get('temperature'), row.get('temperature_trend'), row.get('humidity'), row.get('windspeed'), row.get('winddirection')))


if __name__ == '__main__':
    list_links()
    get_detail_page()
    insert_to_pg()