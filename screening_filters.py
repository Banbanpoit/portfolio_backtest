import pandas as pd
import numpy as np
import requests
import io
from tqdm import tqdm 
from pandas.errors import EmptyDataError
import yfinance as yf

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

def eligibility_filter(ticker, year=2024, min_years=5):
    """
    Toplines filter 
    
    | Minimum Revenue     | Latest reported annual sales > $100 million                                               |
    | Data History        | At least 6 consecutive years of annual financial statements                               |
    | Minimum Liquidity   | Average daily trading value > $5 million                                                  |
    | Sales Consistency 1 | No year in company history with >20% YoY sales decline (single-year exceptions up to 17%) |
    | Sales Consistency 2 | No two consecutive years of declining revenue                                             |

    """

    # Download
    income_url = f'https://perplexity.ai/rest/finance/financials/{ticker}/csv?period=annual&statement_category=INCOME_STATEMENT'
    cf_url     = f'https://perplexity.ai/rest/finance/financials/{ticker}/csv?period=annual&statement_category=CASH_FLOW'
    bs_url     = f'https://perplexity.ai/rest/finance/financials/{ticker}/csv?period=annual&statement_category=BALANCE_SHEET'

    inc = get_csv(income_url)
    cf  = get_csv(cf_url)
    bs  = get_csv(bs_url)

    if any(x is None for x in [inc, cf, bs]):
        print(f" ⚠ {ticker}: Could not fetch all statements")
        return None

    # Apply the SAME year filter to all statements
    start_year = year - min_years
    inc = inc[inc['calendarYear'].between(start_year, year)].sort_values('calendarYear', ascending=True)
    cf  = cf[cf['calendarYear'].between(start_year, year)].sort_values('calendarYear', ascending=True)
    bs  = bs[bs['calendarYear'].between(start_year, year)].sort_values('calendarYear', ascending=True)

    if inc.empty or cf.empty or bs.empty:
        print(f"✗ {ticker}: Missing statements in {start_year}-{year}")
        return None

    # 1. Revenue check
    if inc.iloc[-1]['revenue'] < 100_000_000:
        print(f"✗ {ticker}: Latest year sales < $100M")
        return None

    #2. X years of data
    if len(inc) < min_years:
        print(f"✗ {ticker}: Less than {min_years} consecutive years of statements")
        return None

    #3. No year with >20% yoy sales decline
    revenues = inc['revenue'].values
    yoy = [(revenues[i+1] - revenues[i]) / revenues[i] for i in range(len(revenues)-1)]
    if any(v < -0.20 for v in yoy):
        print(f"✗ {ticker}: More than 20% YoY sales decline")
        return None
    
    #4. No two consecutive years of declining revenue
    declines = [v < 0 for v in yoy]
    if any(declines[i] and declines[i+1] for i in range(len(declines)-1)):
        print(f"✗ {ticker}: Two consecutive YoY sales declines")
        return None

    print(f"✓ {ticker}: Passes eligibility filters")
    return inc, cf, bs


def scoring(ticker, year=2024, min_years=5):
    #Financial filtering
    out = {'Ticker': ticker}
    data = eligibility_filter(ticker, year)
    if not data:
        print(f"✗ {ticker}: Not eligible for scoring\n")
        return None
    inc, cf, bs = data

    merged_df = inc.merge(cf, on=['calendarYear', 'symbol'], suffixes=('', '_cf'))
    merged_df = merged_df.merge(bs, on=['calendarYear', 'symbol'], suffixes=('', '_bs'))
    merged_df = merged_df.sort_values('calendarYear', ascending=True)

    out['Name'] = ticker
    
    # SPS Growth - 3%
    # Minimum of 5Y rolling sales per share (SPS) growth:  min(SPS growth 5Y, T to T-4)
    sps_growth_ts = 0.03
    try:
        yoy_sps = [((merged_df.iloc[i+1]['revenue'] / merged_df.iloc[i+1]['weightedAverageShsOutDil']) / (merged_df.iloc[i]['revenue'] / merged_df.iloc[i]['weightedAverageShsOutDil'])-1) for i in range(merged_df.shape[0]-1)]
        out['SPS Growth'] = int(all(x > sps_growth_ts for x in yoy_sps))
        print(f"SPS Growth => {out['SPS Growth']}")

    except Exception as e:
        out['SPS Growth'] = 0
        print(f"SPS Growth: Error: {e}")
    
    # FCFPS Growth
    # Minimum of 5Y rolling free cash flow/share (FCFPS) growth (or EPS for banks/insurers):  min(FCFPS growth 5Y, T to T-4)
    fcfps_growth_ts = 0.07
    try:
        yoy_fcfps = [(merged_df.iloc[i+1]['freeCashFlow'] / merged_df.iloc[i+1]['weightedAverageShsOutDil']) / merged_df.iloc[i]['freeCashFlow'] / merged_df.iloc[i]['weightedAverageShsOutDil'] for i in range(merged_df.shape[0]-1)]
        out['FCFPS Growth'] = int(all(x > fcfps_growth_ts for x in yoy_fcfps))
        print(f"FCFPS Growth => {out['FCFPS Growth']}")

    except Exception as e:
        out['FCFPS Growth'] = 0
        print(f"FCFPS Growth: Error: {e}")
    
    # FCF Margin
    # Minimum of 5Y rolling FCF margin:  min(FCFM, T to T-4);  FCFM = (FCF – SBC) / Sales
    fcf_margin_ts = 0.08

    try:
        #If no stock based compensation put 0
        fcf_margins = [((row['freeCashFlow'] - row.get('stockBasedCompensation', 0)) / row['revenue']) for _, row in merged_df.iterrows()]
        out['FCF Margin'] = int(all(x > fcf_margin_ts for x in fcf_margins))
        print(f"FCF Margin => {out['FCF Margin']}")

    except Exception as e:
        out['FCF Margin'] = 0
        print(f"        FCF Margin: Error: {e}")

    # CROIC
    # Minimum of 5Y rolling CROIC: min(CROIC, T to T-4);  CROIC = (FCF – SBC) / Invested Capital
    croic_ts = 0.1
    try:
        croics = []
        for _, row in merged_df.iterrows():
            fcf = row['freeCashFlow']
            sbc = row.get('stockBasedCompensation', 0)
            invested = row.get('totalEquity', 0) + row.get('totalDebt', 0)
            croics.append((fcf - sbc) / invested if invested > 0 else 0)

        out['CROIC'] = int(all(x > croic_ts for x in croics))
        print(f"CROIC => {out['CROIC']}")

    except Exception as e:
        out['CROIC'] = 0
        print(f"        CROIC: Error: {e}")

    # FCF Conversion
    # 5Y FCF conversion rate:  (sum FCF_5y – sum SBC_5y) / sum NI_5y
    try:
        fcf_sum = sum(row['freeCashFlow'] - row.get('stockBasedCompensation', 0) for _, row in merged_df.iterrows())
        ni_sum = sum(row['netIncome'] for _, row in merged_df.iterrows())

        ratio = fcf_sum / ni_sum if ni_sum != 0 else 0

        out['FCF Conversion'] = int(ratio > 0.7)
        print(f"FCF Conversion: {ratio:.2%} => {out['FCF Conversion']}")

    except Exception as e:
        out['FCF Conversion'] = 0
        print(f"        FCF Conversion: Error: {e}")

    out['Total Score'] = sum([out[k] for k in ['SPS Growth', 'FCFPS Growth', 'FCF Margin', 'CROIC', 'FCF Conversion']])
    print(f"{ticker}: Total Score = {out['Total Score']}\n")
    return out

def filter_universe(list_tickers):
    results = []
    for t in tqdm(list_tickers, desc='Analysing Companies', unit='Company'):
        print(f"--- Analysing {t} ---")
        score = scoring(t)
        if score:
            results.append(score)

    # Output as DataFrame or CSV
    df = pd.DataFrame(results)
    return df


def get_first_trading_day_price(ticker: str, year: int):
    """
    Returns (price, date) for the first rebalancing day of the `year`.
    Second week of March as more then 50% of US companies have reported annual
    """
    start_date = f"{year}-03-15"
    end_date = f"{year}-03-29"
    df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None, None
    first = df.iloc[0,:]
    return float(first["Close"])


def calculate_expected_fcfya_5y(ticker, year):
    start_year = year - 5 #Last 5years

    try:

        #Fetch Stock Price
        stock_price = get_first_trading_day_price(ticker, year)

        #Fetch financial data

        income_url = f'https://perplexity.ai/rest/finance/financials/{ticker}/csv?period=annual&statement_category=INCOME_STATEMENT'
        cf_url = f'https://perplexity.ai/rest/finance/financials/{ticker}/csv?period=annual&statement_category=CASH_FLOW'
        
        inc = get_csv(income_url)
        cf = get_csv(cf_url)

        #Filter on year of interest
        inc = inc[inc['calendarYear'].between(start_year, year)].sort_values('calendarYear')
        cf  = cf[cf['calendarYear'].between(start_year, year)].sort_values('calendarYear')

        merged = inc.merge(cf, on=['calendarYear', 'symbol'], suffixes=('', '_cf')).sort_values('calendarYear', ascending=True)

        # FCF per share, SBC per share
        fcfps_now = merged.iloc[-1]['freeCashFlow'] / merged.iloc[-1]['weightedAverageShsOutDil']
        sbcps_now = merged.iloc[-1].get('stockBasedCompensation', 0) / merged.iloc[-1]['weightedAverageShsOutDil']
        fcfya_now = (fcfps_now - sbcps_now) / stock_price

        # Find 5Y FCFPS growth
        fcfps_5y = merged.iloc[0]['freeCashFlow'] / merged.iloc[0]['weightedAverageShsOutDil']
        fcfps_g5 = ((fcfps_now-fcfps_5y) / fcfps_5y)**(1/5) - 1
        expected_fcfya_5y = fcfya_now * (1 + fcfps_g5) ** 5

        return fcfya_now, expected_fcfya_5y
    
    except Exception as e:
        print(f"Error calculating FCFYa(5Y) for {ticker}: {e}")
        return None, None

def top_15(df, year):
    df5 = df[df['Total Score'] >= 4].copy()
    fcfya_now_list = []
    fcfya_5y_list = []

    print("\nRanking stocks with 5 points by Expected FCFYa(5Y)...\n")
    for idx, row in df5.iterrows():
        ticker = row["Ticker"]
        fcfya_now, fcfya_5y = calculate_expected_fcfya_5y(ticker, year)
        fcfya_now_list.append(fcfya_now)
        fcfya_5y_list.append(fcfya_5y)

    df5['FCFYa_now'] = fcfya_now_list
    df5['FCFYa(5Y)'] = fcfya_5y_list
    df5_ranked = df5.sort_values('FCFYa(5Y)', ascending=False)

    print("\nStocks with Total Score == 5, ranked by Expected FCFYa(5Y):")
    print(df5_ranked[['Ticker', 'Name', 'FCFYa_now', 'FCFYa(5Y)', 'Total Score']])

    #return first 15
    return df5_ranked[:15]
