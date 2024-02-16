import streamlit as st
import pandas as pd
import pandas.io.sql as sqlio
import altair as alt
import folium
from streamlit_folium import st_folium
from db import conn_str
from dotenv import load_dotenv

df = sqlio.read_sql_query("SELECT * FROM events", conn_str)
st.write(df)
st.title("Seattle Events")

# Chart 1: Most common event categories
st.header("Most Common Event Categories")
category_counts = df['category'].value_counts()
st.bar_chart(category_counts)

# Chart 2: Events count by month
st.header("Events Count by Month")
df['date'] = pd.to_datetime(df['date'])
df['month'] = df['date'].dt.month
month_counts = df['month'].value_counts().sort_index()
st.line_chart(month_counts)

# Chart 3: Events count by day of the week
st.header("Events Count by Day of the Week")
df['weekday'] = df['date'].dt.day_name()
weekday_counts = df['weekday'].value_counts()
st.bar_chart(weekday_counts)

# Map: Events locations
st.header("Events Locations on Map")

# Filter out rows with missing latitude or longitude values
df = df.dropna(subset=['latitude', 'longitude'])

m = folium.Map(location=[47.6062, -122.3321], zoom_start=12)
for index, event in df.iterrows():
    folium.Marker([event['latitude'], event['longitude']], popup=event['venue']).add_to(m)
st_folium(m, width=1200, height=600)

st.sidebar.header("Data Filters")

# Dropdown to filter category
selected_category = st.sidebar.selectbox("Select Event Category", df['category'].unique())
filtered_df = df[df['category'] == selected_category]

# Date range selector for event date
date_range = st.sidebar.date_input("Select Date Range", [df['date'].min(), df['date'].max()])
date_range = [pd.to_datetime(date, utc=True) for date in date_range]  # Convert to UTC Timestamp objects
filtered_df = filtered_df[(filtered_df['date'] >= date_range[0]) & (filtered_df['date'] <= date_range[1])]

# Filter location
selected_location = st.sidebar.selectbox("Select Event Location", df['location'].unique())
filtered_df = filtered_df[filtered_df['location'] == selected_location]

# Filter weather
selected_weather = st.sidebar.selectbox("Select Weather Condition", df['weather_condition'].unique())
filtered_df = filtered_df[filtered_df['weather_condition'] == selected_weather]

# Display filtered data
st.subheader("Filtered Events Data")
st.write(filtered_df)