import pandas as pd
import requests
import os
import sys
import io

api_key = os.environ.get('SCRAPER_API_KEY')
if not api_key:
    print("Pipeline failed: SCRAPER_API_KEY environment variable is missing.")
    sys.exit(1)

target_url = "https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/"
scraper_url = "http://api.scraperapi.com"

payload = {
    'api_key': api_key,
    'url': target_url,
    'render': 'true' 
}

try:
    print("Fetching data via ScraperAPI...")
    response = requests.get(scraper_url, params=payload)
    response.raise_for_status()
    
    # Extract ALL tables from the page
    tables = pd.read_html(io.StringIO(response.text))
    print(f"Found {len(tables)} tables on the webpage.")
    
    # Hunt for the correct table by checking if it has a 'Listing Date' column
    df_live = None
    for i, tbl in enumerate(tables):
        # We check for a highly probable partial match in the columns
        if any('Listing Date' in str(col) for col in tbl.columns):
            df_live = tbl
            print(f"Success: Found the IPO data in table index [{i}].")
            print(f"Actual columns found: {df_live.columns.tolist()}")
            break
            
    if df_live is None:
     # Clean the column headers to strip out the hidden sorting arrows
    df_live.columns = df_live.columns.str.replace('▲▼', '', regex=False).str.strip()
    
    # Select the available columns based on the cleaned headers. 
    # Note: Since Chittorgarh removed 'Close Date', we must substitute it with 'Opening Date'.
    df_live = df_live[['Company', 'Opening Date', 'Listing Date', 'Issue Price (Rs.)', 'Open Price on Listing (Rs.)', 'Close Price on Listing (Rs.)']]
    
    # Rename them to your preferred, clean formats
    df_live.columns = ['Company Name', 'IPO Opening Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']
        for i, tbl in enumerate(tables):
            print(f"Table [{i}]: {tbl.columns.tolist()}")
        sys.exit(1)

    # Note: If this step fails again, you will need to look at the "Actual columns found" 
    # printed in the log and update the exact strings in the list below.
    df_live = df_live[['Company', 'Close Date', 'Listing Date', 'Issue Price', 'Open Price on Listing (Rs.)', 'Close Price on Listing Date (Rs.)']]
    df_live.columns = ['Company Name', 'IPO Close Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']
    
    df_live['Date_Temp'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
    cutoff_date = pd.to_datetime('2026-09-01')
    
    df_live = df_live[(df_live['Date_Temp'] >= cutoff_date) | (df_live['Date_Temp'].isna())]
    df_live.drop(columns=['Date_Temp'], inplace=True)
    
    df_live.set_index('Company Name', inplace=True)
    
    csv_file = 'ipo_tracker.csv'
    if os.path.exists(csv_file):
        df_existing = pd.read_csv(csv_file)
        df_existing.set_index('Company Name', inplace=True)
        df_final = df_live.combine_first(df_existing)
    else:
        df_final = df_live
        
    df_final.reset_index().to_csv(csv_file, index=False)
    print("IPO Tracker updated successfully.")
    
except Exception as e:
    print(f"Pipeline failed: {e}")
    sys.exit(1)
