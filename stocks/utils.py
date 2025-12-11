import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Organisation, StockPrice, TradingSignal

class StockAnalyzer:
    def __init__(self, ticker, prices_df):
        self.ticker = ticker
        self.df = prices_df.sort_values('date').reset_index(drop=True)
        self.df['prev_close'] = self.df['close_price'].shift(1)
        self.df['daily_change_pct'] = (
            (self.df['close_price'] - self.df['prev_close']) / self.df['prev_close'] * 100
        )
        self.df['future_price_5d'] = self.df['close_price'].shift(-5)
        self.df['profit_pct_5d'] = (
            (self.df['future_price_5d'] - self.df['close_price']) / self.df['close_price'] * 100
        )
    
    def generate_signals(self):
        signals = []
        
        for i in range(len(self.df) - 5):
            row = self.df.iloc[i]
            
            # check for buy signal (drop >= 3%)
            if row['daily_change_pct'] <= -3:

                # check if profitable 5 days later
                if row['profit_pct_5d'] > 0:
                    signal = 'buy'
                else:
                    signal = 'hold'
            else:
                # check if we have an active position
                signal = 'hold'
                
                # look back 5 days to see if we should sell
                for j in range(max(0, i-5), i):
                    if j < len(self.df):
                        prev_row = self.df.iloc[j]
                        if prev_row['daily_change_pct'] <= -3 and i - j == 5:
                            signal = 'sell'
                            break
            
            signals.append({
                'date': row['date'],
                'signal': signal,
                'price_drop': abs(row['daily_change_pct']) if row['daily_change_pct'] < 0 else None,
                'expected_profit': row['profit_pct_5d'] if signal == 'buy' else None,
                'close_price': row['close_price']
            })
        
        # add placeholders for last 5 days
        for i in range(len(self.df) - 5, len(self.df)):
            signals.append({
                'date': self.df.iloc[i]['date'],
                'signal': 'hold',
                'price_drop': None,
                'expected_profit': None,
                'close_price': self.df.iloc[i]['close_price']
            })
        
        return signals
    
    def get_summary_stats(self, signals):
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
    """Process uploaded CSV/Excel file and save to database"""
    
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    
    # Clean column names
    df.columns = [col.strip().lower() for col in df.columns]
    
    ticker_col = form_data['ticker_column'].strip().lower()
    date_col = form_data['date_column'].strip().lower()
    price_col = form_data['price_column'].strip().lower()
    
    # Convert date column
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])
    
    # Get unique tickers
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
        
        # Create stock prices
        price_objects = []
        for _, row in ticker_data.iterrows():
            price_objects.append(StockPrice(
                organisation=org,
                date=row[date_col].date(),
                close_price=Decimal(str(row[price_col]))
            ))
        
        # Bulk create prices
        StockPrice.objects.bulk_create(
            price_objects,
            ignore_conflicts=True
        )
        prices_created += len(price_objects)
        
        # Generate trading signals
        generate_trading_signals(org)
    
    return organisations_created, prices_created


def generate_trading_signals(organisation):
    """Generate trading signals for an organisation"""
    
    # Get prices
    prices = StockPrice.objects.filter(
        organisation=organisation
    ).order_by('date').values('date', 'close_price')
    
    if len(prices) < 6:
        return
    
    df = pd.DataFrame(list(prices))
    analyzer = StockAnalyzer(organisation.ticker, df)
    signals = analyzer.generate_signals()
    
    # Save signals to database
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
    """Get recent stock data and signals"""
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