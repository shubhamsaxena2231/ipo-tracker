import pandas as pd
import requests
import os
import sys
import io

api_key = os.environ.get('SCRAPER_API_KEY')
if not api_key:
    print("Pipeline failed: SCRAPER_API_KEY environment variable is missing.")
    sys.exit(1)

def fetch_and_clean(url, target_keyword):
    payload = {'api_key': api_key, 'url': url, 'render': 'true'}
    res = requests.get("http://api.scraperapi.com", params=payload)
    res.raise_for_status()
    
    try:
        tables = pd.read_html(io.StringIO(res.text))
    except ValueError:
        print(f"Pipeline failed: No HTML tables found at {url}. ScraperAPI may have hit a CAPTCHA.")
        sys.exit(1)
        
    for i, t in enumerate(tables):
        t.columns = t.columns.str.replace('▲▼', '', regex=False).str.strip()
        # Look for a widely used column to confirm this is the authentic IPO table
        if any(target_keyword.lower() in str(c).lower() for c in t.columns):
            return t
            
    # If the target keyword is missing, print what was actually found to the logs
    print(f"Error: Could not find the main IPO table containing '{target_keyword}' at {url}.")
    print("Instead, we found these tables (this indicates a column rename or a block):")
    for i, t in enumerate(tables):
        print(f"Table [{i}] Columns: {t.columns.tolist()}")
    sys.exit(1)

try:
    print("Fetching Performance Data...")
    # 'Listing Date' is on all three pages, making it a stronger universal anchor than 'Close'
    df_perf = fetch_and_clean("https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/", 'Listing Date')
    
    print("Fetching Mainboard & SME Dates...")
    df_main = fetch_and_clean("https://www.chittorgarh.com/report/mainboard-ipo-list-in-india-bse-nse/83/all/", 'Listing Date')
    df_sme = fetch_and_clean("https://www.chittorgarh.com/report/sme-ipo-list-in-india-bse-nse/84/all/", 'Listing Date')
    
    df_dates = pd.concat([df_main, df_sme], ignore_index=True)
    
    # 1. Dynamically identify Performance columns
    perf_company = next(c for c in df_perf.columns if 'Company' in c)
    listing_date = next(c for c in df_perf.columns if 'Listing Date' in c)
    issue_price = next(c for c in df_perf.columns if 'Issue Price' in c)
    open_price = next(c for c in df_perf.columns if 'Open Price' in c)
    close_price = next(c for c in df_perf.columns if 'Close Price' in c)
    
    # 2. Dynamically identify Dates columns using safe lookups
    dates_company = next((c for c in df_dates.columns if 'Company' in c or 'Issuer' in c), None)
    close_date = next((c for c in df_dates.columns if 'Close' in c and 'Price' not in c), None)
    
    # If the exact column names changed, this stops the pipeline and prints the new names
    if not dates_company or not close_date:
        print("Pipeline failed: The IPO dates table is missing the Company or Close column.")
        print(f"Available columns are: {df_dates.columns.tolist()}")
        sys.exit(1)
        
    # 3. Merge the authentic Close Date into the Performance table
    df_close_dates = df_dates[[dates_company, close_date]].rename(columns={dates_company: perf_company, close_date: 'IPO Close Date'})
    df_live = pd.merge(df_perf, df_close_dates, on=perf_company, how='left')
    
    # 4. Final Formatting to your requested 6 columns
    df_live = df_live[[perf_company, 'IPO Close Date', listing_date, issue_price, open_price, close_price]]
    df_live.columns = ['Company Name', 'IPO Close Date', 'Listing Date', 'Issue Price', 'Listing Day Opening Price', 'Listing Day Closing Price']
    
    # 5. Filter from September 1, 2026
    df_live['Date_Temp'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
    cutoff_date = pd.to_datetime('2026-09-01')
    df_live = df_live[(df_live['Date_Temp'] >= cutoff_date) | (df_live['Date_Temp'].isna())]
    df_live.drop(columns=['Date_Temp'], inplace=True)
    df_live.set_index('Company Name', inplace=True)
    
    # 6. Upsert to CSV
    csv_file = 'ipo_tracker.csv'
    if os.path.exists(csv_file):
        df_existing = pd.read_csv(csv_file)
        df_existing.set_index('Company Name', inplace=True)
        df_final = df_live.combine_first(df_existing) 
    else:
        df_final = df_live
        
    df_final.reset_index().to_csv(csv_file, index=False)
    print("IPO Tracker updated with Close Dates successfully.")

except Exception as e:
    print(f"Pipeline failed with an unexpected error: {e}")
    sys.exit(1)
