import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Organisation, StockPrice, TradingSignal

"""
stocks.utils

Utilities for processing uploaded stock price files, analyzing price time-series,
generating trading signals and returning recent data.

This module exposes:
- StockAnalyzer: simple rule-based analyzer that generates buy/hold/sell signals.
- process_uploaded_file: parse uploaded CSV/Excel and persist prices + generate signals.
- generate_trading_signals: create TradingSignal records for an Organisation.
- get_recent_data: fetch recent prices and signals for UI consumption.

Notes:
- StockAnalyzer accepts a pandas.DataFrame of price history with at least 'date' and 'close_price'.
- The module uses Django ORM models: Organisation, StockPrice, TradingSignal.
"""

class StockAnalyzer:
    """
    Rule-based stock analyzer.

    Attributes:
        ticker (str): ticker symbol for the organisation.
        df (pd.DataFrame): DataFrame of historical prices (sorted by date).
        prices (list[dict]): list of rows as {'date': date, 'close_price': Decimal/float} for index-based access.

    Initialization will compute helper columns:
      - prev_close
      - daily_change_pct
      - future_price_5d
      - profit_pct_5d

    The generate_signals method inspects past daily changes and 5-day future prices
    to produce a list of signals. The logic is intentionally simple and intended
    for demonstration / prototyping.
    """

    def __init__(self, ticker, prices_df):
        """
        Initialize the analyzer.

        Args:
            ticker (str): ticker symbol.
            prices_df (pd.DataFrame): dataframe with at least ['date', 'close_price'].
        """
        self.ticker = ticker
        # Ensure dates are sorted ascending for lookback/lookahead logic
        self.df = prices_df.sort_values('date').reset_index(drop=True)

        # Build convenience columns used in analysis
        self.df['prev_close'] = self.df['close_price'].shift(1)
        self.df['daily_change_pct'] = (
            (self.df['close_price'] - self.df['prev_close']) / self.df['prev_close'] * 100
        )
        self.df['future_price_5d'] = self.df['close_price'].shift(-5)
        self.df['profit_pct_5d'] = (
            (self.df['future_price_5d'] - self.df['close_price']) / self.df['close_price'] * 100
        )

        # Provide a list-of-dicts view used by existing index-based code paths.
        # Each entry is {'date': Timestamp/date, 'close_price': float}
        # Keeping both df and prices ensures backward compatibility.
        self.prices = [
            {'date': row['date'], 'close_price': row['close_price']}
            for _, row in self.df[['date', 'close_price']].iterrows()
        ]

    def generate_signals(self):
        """
        Generate trading signals across the available price history.

        Returns:
            list[dict]: list of per-day signal dictionaries:
                {
                  'date': date,
                  'signal': 'buy' | 'sell' | 'hold' | 'weak_buy',
                  'price_drop': float | None,
                  'expected_profit': float | None,
                  'confidence': int,
                  'close_price': float
                }

        Signal rules (summary):
          - If today's drop vs previous day <= -3% consider BUY conditions.
            - Calculate confidence using simple heuristics (above 5-day MA, volume, near support).
            - If 5-day future price yields positive profit -> 'buy'.
            - Otherwise may return 'weak_buy' if confidence high.
          - If 5 days have passed since a BUY-like drop, mark a SELL with realized profit.
        """
        signals = []
        n = len(self.prices)

        for i in range(n):
            signal = 'hold'
            price_drop = None
            expected_profit = None
            confidence = 0

            if i >= 1 and i < n - 5:
                # Calculate metrics using index-based list representation
                prev_close = self.prices[i-1]['close_price']
                current_close = self.prices[i]['close_price']
                daily_change = ((current_close - prev_close) / prev_close) * 100

                # Check 5-day moving average (if available)
                if i >= 5:
                    ma_5 = np.mean([self.prices[j]['close_price'] for j in range(i-5, i)])
                    above_ma = current_close > ma_5
                else:
                    above_ma = False

                # BUY conditions
                if daily_change <= -3:
                    # Placeholder: volume_increase assumed True if no volume data available
                    volume_increase = True

                    # Support level heuristic
                    support_level = self.find_support_level(i)
                    near_support = abs(current_close - support_level) / support_level < 0.02

                    confidence = 50  # Base for ~3% drop
                    if above_ma:
                        confidence += 20
                    if volume_increase:
                        confidence += 15
                    if near_support:
                        confidence += 15

                    # Check future profit over 5 days
                    future_price = self.prices[i+5]['close_price']
                    profit_pct = ((future_price - current_close) / current_close) * 100

                    if profit_pct > 0:
                        signal = 'buy'
                        price_drop = abs(daily_change)
                        expected_profit = profit_pct
                    else:
                        signal = 'hold' if confidence < 60 else 'weak_buy'

            # SELL logic: if 5 days after a past BUY-like drop, create SELL with realized profit
            if i >= 5:
                past_i = i - 5
                if past_i >= 1:
                    past_prev = self.prices[past_i-1]['close_price']
                    past_current = self.prices[past_i]['close_price']
                    past_drop = ((past_current - past_prev) / past_prev) * 100

                    if past_drop <= -3:
                        buy_price = past_current
                        sell_price = self.prices[i]['close_price']
                        actual_profit = ((sell_price - buy_price) / buy_price) * 100

                        signal = 'sell'
                        expected_profit = actual_profit

            signals.append({
                'date': self.prices[i]['date'],
                'signal': signal,
                'price_drop': price_drop,
                'expected_profit': expected_profit,
                'confidence': confidence,
                'close_price': self.prices[i]['close_price']
            })

        return signals

    def find_support_level(self, current_index, lookback=20):
        """
        Find a simple support level as the minimum close price in a lookback window.

        Args:
            current_index (int): current index in self.prices for which to find support.
            lookback (int): number of prior days to inspect.

        Returns:
            float: nearest support price (minimum in the window) or current price if no history.
        """
        start = max(0, current_index - lookback)
        prices = [self.prices[j]['close_price'] for j in range(start, current_index)]
        return min(prices) if prices else self.prices[current_index]['close_price']

    def get_summary_stats(self, signals):
        """
        Produce summary statistics from a list of generated signals.

        Args:
            signals (list[dict]): output of generate_signals.

        Returns:
            dict: summary metrics including counts, success rate and average drops/profits.
        """
        buy_signals = [s for s in signals if s['signal'] == 'buy']
        sell_signals = [s for s in signals if s['signal'] == 'sell']
        hold_signals = [s for s in signals if s['signal'] == 'hold']

        total_buys = len(buy_signals)
        successful_buys = len([s for s in buy_signals if s.get('expected_profit', 0) > 0])
        success_rate = (successful_buys / total_buys * 100) if total_buys > 0 else 0

        avg_price_drop = np.mean([s['price_drop'] for s in buy_signals if s['price_drop']]) if buy_signals else 0
        avg_profit = np.mean([s['expected_profit'] for s in buy_signals if s['expected_profit']]) if buy_signals else 0

        return {
            'total_days': len(signals),
            'buy_signals': total_buys,
            'sell_signals': len(sell_signals),
            'hold_signals': len(hold_signals),
            'success_rate': round(success_rate, 2),
            'avg_price_drop': round(avg_price_drop, 2),
            'avg_profit': round(avg_profit, 2),
            'max_price_drop': round(max([s['price_drop'] for s in buy_signals if s['price_drop']], default=0), 2),
            'min_price_drop': round(min([s['price_drop'] for s in buy_signals if s['price_drop']], default=0), 2),
        }


def process_uploaded_file(file, form_data):
    """
    Process an uploaded CSV or Excel file and persist prices to the database.

    This function will:
      - read the uploaded file into a pandas.DataFrame
      - normalize column names
      - create Organisation records (get_or_create)
      - bulk create StockPrice records (ignore conflicts)
      - invoke generate_trading_signals for each organisation

    Args:
        file: uploaded file object (must have .name and be readable by pandas).
        form_data (dict): mapping containing 'ticker_column', 'date_column', 'price_column'.

    Returns:
        tuple(int, int): (organisations_created, prices_created)
    """
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    # Clean column names for consistent lookup
    df.columns = [col.strip().lower() for col in df.columns]

    ticker_col = form_data['ticker_column'].strip().lower()
    date_col = form_data['date_column'].strip().lower()
    price_col = form_data['price_column'].strip().lower()

    # Convert date column and drop invalid rows
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])

    # Unique tickers to create organisations / prices for
    tickers = df[ticker_col].unique()

    organisations_created = 0
    prices_created = 0

    for ticker in tickers:
        # Get or create organisation
        org, created = Organisation.objects.get_or_create(
            ticker=ticker.strip(),
            defaults={'name': ticker.strip()}
        )
        if created:
            organisations_created += 1

        # Filter data for this ticker
        ticker_data = df[df[ticker_col] == ticker]

        # Prepare StockPrice objects for bulk create
        price_objects = []
        for _, row in ticker_data.iterrows():
            price_objects.append(StockPrice(
                organisation=org,
                date=row[date_col].date(),
                close_price=Decimal(str(row[price_col]))
            ))

        # Bulk create prices (ignore duplicates/conflicts)
        StockPrice.objects.bulk_create(
            price_objects,
            ignore_conflicts=True
        )
        prices_created += len(price_objects)

        # Generate trading signals for this organisation
        generate_trading_signals(org)

    return organisations_created, prices_created


def generate_trading_signals(organisation):
    """
    Generate and persist TradingSignal records for an organisation.

    Requires at least 6 historical price points to compute 5-day lookahead.
    """
    # Query prices from DB ordered by date
    prices = StockPrice.objects.filter(
        organisation=organisation
    ).order_by('date').values('date', 'close_price')

    if len(prices) < 6:
        return

    df = pd.DataFrame(list(prices))
    analyzer = StockAnalyzer(organisation.ticker, df)
    signals = analyzer.generate_signals()

    # Prepare TradingSignal objects for bulk creation
    signal_objects = []
    for signal_data in signals:
        signal_objects.append(TradingSignal(
            organisation=organisation,
            date=signal_data['date'],
            signal=signal_data['signal'],
            price_drop=signal_data['price_drop'],
            expected_profit=signal_data['expected_profit']
        ))

    TradingSignal.objects.bulk_create(
        signal_objects,
        ignore_conflicts=True
    )


def get_recent_data(organisation, days=30):
    """
    Return recent price and signal data for UI consumption.

    Args:
        organisation (Organisation): organisation instance.
        days (int): lookback window in days.

    Returns:
        dict: {'prices': [...], 'signals': [...] } where lists contain dicts suitable for JSON.
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    prices = StockPrice.objects.filter(
        organisation=organisation,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')

    signals = TradingSignal.objects.filter(
        organisation=organisation,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')

    return {
        'prices': list(prices.values('date', 'close_price')),
        'signals': list(signals.values('date', 'signal', 'price_drop', 'expected_profit'))
    }