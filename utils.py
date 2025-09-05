import pandas as pd
from datetime import datetime

def get_sp500_tickers_for_year(csv_path, year):
    """
    Returns the list of S&P 500 tickers for a given year using the historical CSV.
    Returns:
        List[str]: List of ticker symbols in the S&P 500 for the specified year
    """
    # Load CSV and ensure date column is parsed
    df = pd.read_csv(csv_path)
    # Assume the CSV has a 'date' column in YYYY-MM-DD format and a 'ticker' column
    df['date'] = pd.to_datetime(df['date'])
    
    # Find the last date snapshot for the given year
    year_dates = df[df['date'].dt.year == year]['date'].unique()
    if len(year_dates) == 0:
        raise ValueError(f"No records found for year {year}")
    
    # Use the latest date for that year
    snapshot_date = max(year_dates)
    tickers = df[df['date'] == snapshot_date]['tickers'].unique()
    return list(tickers)

if __name__ == "__main__":
# Example usage:
    tickers_2021 = get_sp500_tickers_for_year('./data/S&P 500 Historical Components & Changes(07-12-2025).csv', 2021)
    print(tickers_2021)  # Prints all tickers for the S&P 500 as of last change in 2021
