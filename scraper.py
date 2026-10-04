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
        if any('Listing Date' in str(col) for col in tbl.columns):
            df_live = tbl
            print(f"Success: Found the IPO data in table index [{i}].")
            break
            
    # This is the IF statement that caused the indentation error previously
    if df_live is None:
        print("Pipeline failed: Could not locate the main IPO table.")
        sys.exit(1)

    # Clean the column headers to strip out the hidden sorting arrows
    df_live.columns = df_live.columns.str.replace('▲▼', '', regex=False).str.strip()
    
    # Select the available columns based on the cleaned headers
    df_live = df_live[['Company', 'Opening Date', 'Listing Date', 'Issue Price (Rs.)', 'Open Price on Listing (Rs.)', 'Close Price on Listing (Rs.)']]
    
    # Rename them to your preferred, clean formats
    df_live.columns = ['Company Name', 'IPO Opening Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']
    
    # Filter for dates from Sep 1, 2026 onwards
    df_live['Date_Temp'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
    cutoff_date = pd.to_datetime('2026-09-01')
    
    df_live = df_live[(df_live['Date_Temp'] >= cutoff_date) | (df_live['Date_Temp'].isna())]
    df_live.drop(columns=['Date_Temp'], inplace=True)
    
    df_live.set_index('Company Name', inplace=True)
    
    # Perform the Lifetime Upsert
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
