import pandas as pd
import requests
import os

url = "https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/"
headers = {"User-Agent": "Mozilla/5.0"}

# 1. Fetch live data
response = requests.get(url, headers=headers)
df_live = pd.read_html(response.text)[0]

# 2. Map columns and filter from Sept 1, 2026
df_live = df_live[['Company', 'Close Date', 'Listing Date', 'Issue Price', 'Open Price on Listing (Rs.)', 'Close Price on Listing Date (Rs.)']]
df_live.columns = ['Company Name', 'IPO Close Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']

df_live['Date_Temp'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
cutoff_date = pd.to_datetime('2026-09-01')
df_live = df_live[(df_live['Date_Temp'] >= cutoff_date) | (df_live['Date_Temp'].isna())]
df_live.drop(columns=['Date_Temp'], inplace=True)
df_live.set_index('Company Name', inplace=True)

# 3. Upsert with existing CSV archive
csv_file = 'ipo_tracker.csv'
if os.path.exists(csv_file):
    df_existing = pd.read_csv(csv_file)
    df_existing.set_index('Company Name', inplace=True)
    df_final = df_live.combine_first(df_existing)
else:
    df_final = df_live

# 4. Save the master file
df_final.reset_index().to_csv(csv_file, index=False)
