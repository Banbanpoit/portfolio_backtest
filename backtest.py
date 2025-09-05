import pandas as pd
import numpy as np
import yfinance as yf
from screening_filters import tickers, scoring, top_15  # scoring(ticker, year), top_15(df)
# If filter_universe is preferred, it can be used to build df_scores as well.

def get_first_trading_day_price(ticker: str, date_target: Timestamp):
    """
    Returns (price, date) for the first rebalancing day.
    Second week of March as more then 50% of US companies have reported annual
    """
    start_date = f"{year}-03-15"
    end_date = f"{year}-03-29"
    df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None, None
    first = df.iloc[0,:]
    return float(first["Close"]), pd.to_datetime(first.name).date()

def get_last_trading_day_price(ticker: str, year: int):
    """
    Returns (price, date) for the last trading day of `year` i.e before rebalancing
    First 2 weeks of march - small buffer to handle holidays
    """
    start_date = f"{year+1}-03-01"
    end_date = f"{year+1}-03-14"
    df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None, None
    last = df.iloc[-1,:]
    return float(last["Close"]), pd.to_datetime(last.name).date()

def backtest_strategy_first_day_only_with_details(
    ticker_list,
    start_year=2018,
    end_year=2024,
    min_holdings=1
):
    """
    Annual rebalance:
      - Selection each year uses scoring(ticker, year-1).
      - Prices use only first and last trading day of the investment year.
      - Returns both a yearly summary and a per-ticker detail DataFrame.
    """
    yearly_records = []
    detail_records = []
    cumulative = 1.0

    for year in range(start_year, end_year + 1):
        print(f"\n=== Year {year}: Screening with financial data ===")

        # 1) Score entire universe with prior-year financials (point-in-time)
        scores = []
        for t in ticker_list:
            try:
                s = scoring(t, year=year-1)
                if s is not None:
                    scores.append(s)
            except Exception as e:
                print(f"Scoring error {t} ({year-1}): {e}")

        if not scores:
            yearly_records.append({
                "year": year,
                "n_selected": 0,
                "portfolio_return": 0.0,
                "cumulative_return": cumulative
            })
            continue

        df_scores = pd.DataFrame(scores)

        # 2) Select portfolio using top_15
        selected_df = top_15(df_scores, year-1).reset_index(drop=True)
        selected = selected_df["Ticker"].tolist()
        if len(selected) < min_holdings:
            print(f"Only {len(selected)} selected; proceeding.")

        # 3) Prices and returns per ticker + detail rows
        per_stock_returns = []
        for idx, row in selected_df.iterrows():
            tkr = row["Ticker"]
            # Optional: include available scoring metrics for traceability
            total_score = row.get("Total Score", None)

            entry_price, entry_date = get_first_trading_day_price(tkr, year)
            exit_price, exit_date = get_last_trading_day_price(tkr, year)

            if entry_price is None or exit_price is None:
                ann_return = 0.0
            else:
                ann_return = (exit_price / entry_price) - 1.0

            per_stock_returns.append(ann_return)

            # Detail record per ticker per year
            detail_records.append({
                "year": year,
                "rank_in_selection": idx + 1,
                "ticker": tkr,
                "entry_date": entry_date,
                "entry_price_adj": entry_price,
                "exit_date": exit_date,
                "exit_price_adj": exit_price,
                "annual_return": ann_return,
                "total_score": total_score
            })

        # 4) Equal-weight portfolio return
        if per_stock_returns:
            port_ret = float(np.mean(per_stock_returns))
        else:
            port_ret = 0.0

        cumulative *= (1.0 + port_ret)

        yearly_records.append({
            "year": year,
            "n_selected": len(selected),
            "portfolio_return": port_ret,
            "cumulative_return": cumulative
        })

        print(f"Year {year} return: {port_ret:.2%} | Cumulative: {cumulative-1:.2%}")

    summary_by_year = pd.DataFrame(yearly_records)
    details_by_year = pd.DataFrame(detail_records)
    return summary_by_year, details_by_year

# Example usage:
if __name__ == "__main__":
    summary_df, details_df = backtest_strategy_first_day_only_with_details(
        tickers,
        start_year=2020,
        end_year=2024
    )
    print("\n=== Summary by Year ===")
    print(summary_df)
    print("\n=== Details by Year (first 20 rows) ===")
    print(details_df.head(20))
    # Optional: save to CSV
    # summary_df.to_csv("backtest_summary.csv", index=False)
    # details_df.to_csv("backtest_details.csv", index=False)
