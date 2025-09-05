import pandas as pd
import numpy as np
import requests
import io
from tqdm import tqdm 
from pandas.errors import EmptyDataError
from tqdm import tqdm



def get_csv(url):
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            try:
                return pd.read_csv(io.StringIO(resp.text))
            except EmptyDataError:
                print(f"    ⚠ Empty CSV data at: {url}")
                return None
        else:
            print(f"    ⚠ HTTP error {resp.status_code} for: {url}")
            return None
    except Exception as e:
        print(f"    ⚠ Exception fetching {url}: {e}")
        return None

def check_data(list_tickers, year=2024, min_years=10):

    list_check = []
    for t in tqdm(list_tickers):
        try:
            income_url = f'https://perplexity.ai/rest/finance/financials/{t}/csv?period=annual&statement_category=INCOME_STATEMENT'
            cf_url     = f'https://perplexity.ai/rest/finance/financials/{t}/csv?period=annual&statement_category=CASH_FLOW'
            bs_url     = f'https://perplexity.ai/rest/finance/financials/{t}/csv?period=annual&statement_category=BALANCE_SHEET'

            inc = get_csv(income_url)
            cf  = get_csv(cf_url)
            bs  = get_csv(bs_url)

            inc_bool = len(inc.calendarYear.unique()) >= min_years
            cf_bool  = len(cf.calendarYear.unique()) >= min_years
            bs_bool  = len(bs.calendarYear.unique()) >= min_years

        except Exception:
            inc_bool, cf_bool, bs_bool = False, False, False
            print(f"Missing Data {t}")
        
        list_check.append({
            'ticker': t,
            'income_years_ok': inc_bool,
            'cashflow_years_ok': cf_bool,
            'balance_years_ok': bs_bool
            })

    # Convert the check list to a DataFrame
    df = pd.DataFrame(list_check)
    return df


