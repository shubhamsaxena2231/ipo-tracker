import pandas as pd
import requests
import os
import sys
import io

# Retrieve the ScraperAPI key passed from GitHub Actions
api_key = os.environ.get('SCRAPER_API_KEY')
if not api_key:
    print("Pipeline failed: SCRAPER_API_KEY environment variable is missing.")
    sys.exit(1)

target_url = "https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/"
scraper_url = "http://api.scraperapi.com"

# The payload tells ScraperAPI where to go and to render JavaScript to bypass Cloudflare
payload = {
    'api_key': api_key,
    'url': target_url,
    'render': 'true' 
}

try:
    print("Fetching data via ScraperAPI...")
    response = requests.get(scraper_url, params=payload)
    response.raise_for_status()
    
    # 1. Fetch live data
    df_live = pd.read_html(io.StringIO(response.text))[0]

    # 2. Map columns
    df_live = df_live[['Company', 'Close Date', 'Listing Date', 'Issue Price', 'Open Price on Listing (Rs.)', 'Close Price on Listing Date (Rs.)']]
    df_live.columns = ['Company Name', 'IPO Close Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']
    
    # 3. Filter for >= Sep 1, 2026
    df_live['Date_Temp'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
    cutoff_date = pd.to_datetime('2026-09-01')
    
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
    sys.exit(1)
