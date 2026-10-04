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
                    sys.exit("Max retries reached. Pipeline failed.")
                
            for i, t in enumerate(tables):
                t.columns = t.columns.str.replace('▲▼', '', regex=False).str.strip()
                if any(target_keyword.lower() in str(c).lower() for c in t.columns):
                    print(f"Success: Found the target table on attempt {attempt + 1}.")
                    return t
                    
            print(f"Error: Could not find the main IPO table containing '{target_keyword}'.")
            sys.exit(1)
            
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
            else:
                sys.exit("Max retries reached. Failing pipeline.")

try:
    print("Fetching Performance Data...")
    df_perf = fetch_and_clean("https://www.chittorgarh.com/report/ipo_report_listing_day_gain/98/all/", 'Listing Date')
    
    print("Fetching Mainboard & SME Dates...")
    df_main = fetch_and_clean("https://www.chittorgarh.com/report/mainboard-ipo-list-in-india-bse-nse/83/all/", 'Listing Date')
    # Tag these rows as Mainboard before merging
    df_main['IPO Type'] = 'Mainboard'
    
    df_sme = fetch_and_clean("https://www.chittorgarh.com/report/sme-ipo-list-in-india-bse-nse/84/all/", 'Listing Date')
    # Tag these rows as SME before merging
    df_sme['IPO Type'] = 'SME'
    
    df_dates = pd.concat([df_main, df_sme], ignore_index=True)
    
    # 1. Dynamically identify Performance columns
    perf_company = next(c for c in df_perf.columns if 'Company' in c)
    listing_date = next(c for c in df_perf.columns if 'Listing Date' in c)
    issue_price = next(c for c in df_perf.columns if 'Issue Price' in c)
    open_price = next(c for c in df_perf.columns if 'Open Price' in c)
    close_price = next(c for c in df_perf.columns if 'Close Price' in c)
    
    # 2. Dynamically identify Dates columns
    dates_company_candidates = ['Company', 'Issuer', 'IPO Name', 'Name']
    close_date_candidates = ['Close', 'Closing', 'Ends', 'End Date']
    
    dates_company = next((c for c in df_dates.columns if any(cand.lower() in str(c).lower() for cand in dates_company_candidates)), None)
    close_date = next((c for c in df_dates.columns if any(cand.lower() in str(c).lower() for cand in close_date_candidates) and 'price' not in str(c).lower()), None)
    
    if not dates_company or not close_date:
        sys.exit("Pipeline failed: The IPO dates table is missing the Company or Close column.")
        
    # 3. Merge the authentic Close Date AND the IPO Type into the Performance table
    df_close_dates = df_dates[[dates_company, close_date, 'IPO Type']].rename(columns={
        dates_company: perf_company, 
        close_date: 'IPO Close Date'
    })
    df_live = pd.merge(df_perf, df_close_dates, on=perf_company, how='left')
    
    # 4. Standardize column names to match your exact request
    df_live = df_live.rename(columns={
        perf_company: 'Company Name',
        listing_date: 'Listing Date',
        issue_price: 'Issue Price',
        open_price: 'Listing Day Opening Price',
        close_price: 'Listing Day Closing Price'
    })
    
    # 5. Enforce exact column order & drop the old 'IPO Opening Date'
    final_columns = [
        'Company Name', 
        'IPO Type', 
        'IPO Close Date', 
        'Listing Date', 
        'Issue Price', 
        'Listing Day Opening Price', 
        'Listing Day Closing Price'
    ]
    df_live = df_live[final_columns]
    
    # 6. Filter from September 1, 2026 and clean ghost rows
    df_live = df_live.dropna(subset=['Listing Date'])
    df_live['Sort_Date'] = pd.to_datetime(df_live['Listing Date'], format='%d-%b-%Y', errors='coerce')
    cutoff_date = pd.to_datetime('2026-09-01')
    df_live = df_live[(df_live['Sort_Date'] >= cutoff_date) | (df_live['Sort_Date'].isna())]
    
    df_live.set_index('Company Name', inplace=True)
    
    # 7. Upsert to CSV
    csv_file = 'ipo_tracker.csv'
    if os.path.exists(csv_file):
        df_existing = pd.read_csv(csv_file)
        df_existing.set_index('Company Name', inplace=True)
        df_final = df_live.combine_first(df_existing) 
    else:
        df_final = df_live
        
    df_final = df_final.reset_index()
    
    # 8. Sort chronologically (newest at the top)
    df_final = df_final.dropna(subset=['Listing Date'])
    df_final['Sort_Date'] = pd.to_datetime(df_final['Listing Date'], format='%d-%b-%Y', errors='coerce')
    df_final = df_final.sort_values(by='Sort_Date', ascending=False)
    
    # Enforce the exact column order one last time before exporting
    df_final = df_final[final_columns]
    
    df_final.to_csv(csv_file, index=False)
    print("IPO Tracker updated with IPO Type and sorted chronologically successfully.")

except Exception as e:
    print(f"Pipeline failed with an unexpected error: {e}")
    sys.exit(1)
