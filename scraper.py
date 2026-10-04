import pandas as pd
import requests
import os
import io

url = "https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/"

# Robust headers to mimic a real browser and prevent 403 Forbidden blocks
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status() # Ensures the script stops if the website is down
    
    # 1. Fetch live data (Wrapped in io.StringIO to fix the pandas FutureWarning)
    df_live = pd.read_html(io.StringIO(response.text))[0]

    # 2. Map to your 6 required columns
    df_live = df_live[['Company', 'Close Date', 'Listing Date', 'Issue Price', 'Open Price on Listing (Rs.)', 'Close Price on Listing Date (Rs.)']]
    df_live.columns = ['Company Name', 'IPO Close Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']
    
    # 3. Filter for >= Sep 1, 2026
    df_live['Date_Temp'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
    cutoff_date = pd.to_datetime('2026-09-01')
    
    # Keeps rows after Sep 1 OR rows with blank dates (upcoming IPOs)
    df_live = df_live[(df_live['Date_Temp'] >= cutoff_date) | (df_live['Date_Temp'].isna())]
    df_live.drop(columns=['Date_Temp'], inplace=True)
    
    # 4. Set the primary key for merging
    df_live.set_index('Company Name', inplace=True)
    
    # 5. Perform the Lifetime Upsert
    csv_file = 'ipo_tracker.csv'
    if os.path.exists(csv_file):
        df_existing = pd.read_csv(csv_file)
        df_existing.set_index('Company Name', inplace=True)
        
        # combine_first() prioritizes live data but preserves historical rows permanently
        df_final = df_live.combine_first(df_existing)
    else:
        df_final = df_live
        
    # 6. Save the master archive
    df_final.reset_index().to_csv(csv_file, index=False)
    print("IPO Tracker updated successfully.")
    
except Exception as e:
    print(f"Pipeline failed: {e}")
