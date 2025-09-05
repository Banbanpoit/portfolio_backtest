#### Introduction
This project implements a portfolio construction strategy designed to systematically select and allocate stocks within the S&P 500 universe. The approach combines rigorous financial screening criteria with historical backtesting to assess real-world performance.

#### Rebalancing
Portfolio rebalancing occurs after the second week of March, once more than 50% of US companies have reported annual results.
This timing introduces a look-ahead bias, as filters rely on finalized statements after the reporting period.

#### Topline filters

| Filter              | Description                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------- |
| Minimum Revenue     | Latest reported annual sales > $100 million                                               |
| Data History        | At least 6 consecutive years of annual financial statements                               |
| Minimum Liquidity   | Average daily trading value > $5 million                                                  |
| Sales Consistency 1 | No year in company history with >20% YoY sales decline (single-year exceptions up to 17%) |
| Sales Consistency 2 | No two consecutive years of declining revenue                                             |
#### Refined Financial Filters

| #   | Criterion                               | Definition / Formula                                                                                                       | Threshold |
| --- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------- |
| 1   | Consistent 5Y SPS Growth                | Minimum of 5Y rolling sales per share (SPS) growth: <br> min(SPS growth 5Y, T to T-4)                                      | > 3%      |
| 2   | Consistent 5Y FCFPS Growth              | Minimum of 5Y rolling free cash flow/share (FCFPS) growth (or EPS for banks/insurers): <br> min(FCFPS growth 5Y, T to T-4) | > 7%      |
| 3   | Free Cash Flow Margin (FCFM)            | Minimum of 5Y rolling FCF margin: <br> min(FCFM, T to T-4); <br> FCFM = (FCF – SBC) / Sales                                | > 8%      |
| 4   | Cash Return on Invested Capital (CROIC) | Minimum of 5Y rolling CROIC: <br> min(CROIC, T to T-4); <br> CROIC = (FCF – SBC) / Invested Capital                        | > 10%     |
| 5   | Free Cash Flow Conversion               | 5Y FCF conversion rate: <br> (sum FCF_5y – sum SBC_5y) / sum NI_5y                                                         | > 70%     |
#### Final screening
- **Rank the remaining stocks** by highest expected FCFYa(5Y).
- **Select the top 15 names** to form an equally weighted portfolio (≈6.66% per name).
