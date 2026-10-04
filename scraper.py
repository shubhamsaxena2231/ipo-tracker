import pandas as pd
import cloudscraper
import os
import sys
import io

url = "https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/"

try:
    # 1. Initialize the Cloudflare bypass scraper
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
    response.raise_for_status()
    
    # 2. Fetch live data (Wrapped in io.StringIO to fix the pandas FutureWarning)
    df_live = pd.read_html(io.StringIO(response.text))[0]

    # 3. Map to your 6 required columns
    df_live = df_live[['Company', 'Close Date', 'Listing Date', 'Issue Price', 'Open Price on Listing (Rs.)', 'Close Price on Listing Date (Rs.)']]
    df_live.columns = ['Company Name', 'IPO Close Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']
    
    # 4. Filter for >= Sep 1, 2026
    df_live['Date_Temp'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
    cutoff_date = pd.to_datetime('2026-09-01')
    
    # Keeps rows after Sep 1 OR rows with blank dates (upcoming IPOs)
    df_live = df_live[(df_live['Date_Temp'] >= cutoff_date) | (df_live['Date_Temp'].isna())]
    df_live.drop(columns=['Date_Temp'], inplace=True)
    
    # 5. Set the primary key for merging
    df_live.set_index('Company Name', inplace=True)
    
    # 6. Perform the Lifetime Upsert
    csv_file = 'ipo_tracker.csv'
    if os.path.exists(csv_file):
        df_existing = pd.read_csv(csv_file)
        df_existing.set_index('Company Name', inplace=True)
        
        # combine_first() prioritizes live data but preserves historical rows permanently
        df_final = df_live.combine_first(df_existing)
    else:
        df_final = df_live
        
    # 7. Save the master archive
    df_final.reset_index().to_csv(csv_file, index=False)
    print("IPO Tracker updated successfully.")
    
except Exception as e:
    # Forces GitHub Actions to accurately report a failure and stop the pipeline
    print(f"Pipeline failed: {e}")
    sys.exit(1)
