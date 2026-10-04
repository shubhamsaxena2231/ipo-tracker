import pandas as pd
import requests
import os
import sys
import io
import time

api_key = os.environ.get('SCRAPER_API_KEY')
if not api_key:
    print("Pipeline failed: SCRAPER_API_KEY environment variable is missing.")
    sys.exit(1)

def fetch_and_clean(url, target_keyword):
    payload = {'api_key': api_key, 'url': url, 'render': 'true'}
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} of {max_retries} for {url}...")
            res = requests.get("http://api.scraperapi.com", params=payload, timeout=90)
            res.raise_for_status()
            
            try:
                tables = pd.read_html(io.StringIO(res.text))
            except ValueError:
                print(f"No HTML tables found. ScraperAPI may have hit a CAPTCHA.")
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue 
                else:
                    print("Max retries reached. Pipeline failed.")
                    sys.exit(1)
                
            for i, t in enumerate(tables):
                t.columns = t.columns.str.replace('▲▼', '', regex=False).str.strip()
                if any(target_keyword.lower() in str(c).lower() for c in t.columns):
                    print(f"Success: Found the target table on attempt {attempt + 1}.")
                    return t
                    
            print(f"Error: Could not find the main IPO table containing '{target_keyword}'.")
            for i, t in enumerate(tables):
                print(f"Table [{i}] Columns: {t.columns.tolist()}")
            sys.exit(1)
            
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print("Sleeping for 10 seconds before retrying...")
                time.sleep(10)
            else:
                print("Max retries reached. Failing pipeline.")
                sys.exit(1)

try:
    print("Fetching Performance Data...")
    df_perf = fetch_and_clean("https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/", 'Listing Date')
    
    print("Fetching Mainboard & SME Dates...")
    df_main = fetch_and_clean("https://www.chittorgarh.com/report/mainboard-ipo-list-in-india-bse-nse/83/all/", 'Listing Date')
    df_sme = fetch_and_clean("https://www.chittorgarh.com/report/sme-ipo-list-in-india-bse-nse/84/all/", 'Listing Date')
    
    df_dates = pd.concat([df_main, df_sme], ignore_index=True)
    
    # Debugging output to expose the exact column structures in the GitHub logs
    print(f"Performance Columns: {df_perf.columns.tolist()}")
    print(f"Dates Columns: {df_dates.columns.tolist()}")
    
    # 1. Dynamically identify Performance columns
    perf_company = next(c for c in df_perf.columns if 'Company' in c)
    listing_date = next(c for c in df_perf.columns if 'Listing Date' in c)
    issue_price = next(c for c in df_perf.columns if 'Issue Price' in c)
    open_price = next(c for c in df_perf.columns if 'Open Price' in c)
    close_price = next(c for c in df_perf.columns if 'Close Price' in c)
    
    # 2. Dynamically identify Dates columns using broadened vocabularies
    dates_company_candidates = ['Company', 'Issuer', 'IPO Name', 'Name']
    close_date_candidates = ['Close', 'Closing', 'Ends', 'End Date']
    
    dates_company = next((c for c in df_dates.columns if any(cand.lower() in str(c).lower() for cand in dates_company_candidates)), None)
    close_date = next((c for c in df_dates.columns if any(cand.lower() in str(c).lower() for cand in close_date_candidates) and 'price' not in str(c).lower()), None)
    
    if not dates_company or not close_date:
        print("Pipeline failed: The IPO dates table is missing the Company or Close column.")
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
