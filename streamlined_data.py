"""
Streamlined Market Data Collection
=================================

This module uses our existing TastyTrade infrastructure (tt.py and tt_data.py)
to gather exactly the data we need for comprehensive market analysis without
external dependencies like yfinance or alpaca.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import config
from tt_data import get_market_overview, get_ticker_recent_data, get_current_price
from tt import get_options_chain, get_current_price as tt_get_current_price, get_market_data


def get_global_market_overview() -> Dict[str, Dict]:
    """
    Get current prices of global market indicators with bid/ask/day-over-day data
    
    Returns:
    Dict with symbols as keys and market data as values
    """
    symbols = ['QQQ', 'TLT', 'GLD', 'USO', 'IBIT', 'NDAQ']
    
    print(f"🌍 Fetching global market overview for: {', '.join(symbols)}")
    
    try:
        market_data = get_market_overview(symbols=symbols, force_refresh=True)
        
        # Format for consistency
        formatted_data = {}
        for symbol, data in market_data.items():
            if data:
                formatted_data[symbol] = {
                    'symbol': symbol,
                    'current_price': data.get('current_price', 0.0),
                    'bid': data.get('bid', 0.0),
                    'ask': data.get('ask', 0.0),
                    'day_change': data.get('day_change', 0.0),
                    'day_change_percent': data.get('day_change_percent', 0.0),
                    'volume': data.get('volume', 0),
                    'timestamp': data.get('timestamp', datetime.now().isoformat()),
                    'source': 'tastytrade'
                }
        
        print(f"✅ Got global market data for {len(formatted_data)} symbols")
        return formatted_data
        
    except Exception as e:
        print(f"❌ Error fetching global market overview: {e}")
        return {}


def get_spy_giants_overview() -> Dict[str, Dict]:
    """
    Get current prices of SPY's largest holdings with bid/ask/day-over-day data
    
    Returns:
    Dict with symbols as keys and market data as values  
    """
    spy_giants = ['NVDA', 'MSFT', 'AAPL', 'AMZN', 'META', 'GOOGL']
    
    print(f"🏢 Fetching SPY giants overview for: {', '.join(spy_giants)}")
    
    try:
        market_data = get_market_overview(symbols=spy_giants, force_refresh=True)
        
        # Format for consistency
        formatted_data = {}
        for symbol, data in market_data.items():
            if data:
                formatted_data[symbol] = {
                    'symbol': symbol,
                    'current_price': data.get('current_price', 0.0),
                    'bid': data.get('bid', 0.0),
                    'ask': data.get('ask', 0.0),
                    'day_change': data.get('day_change', 0.0),
                    'day_change_percent': data.get('day_change_percent', 0.0),
                    'volume': data.get('volume', 0),
                    'timestamp': data.get('timestamp', datetime.now().isoformat()),
                    'source': 'tastytrade'
                }
        
        print(f"✅ Got SPY giants data for {len(formatted_data)} symbols")
        return formatted_data
        
    except Exception as e:
        print(f"❌ Error fetching SPY giants overview: {e}")
        return {}


def get_ticker_30min_data(ticker: str) -> Dict[str, Any]:
    """
    Get last 30 minutes of ticker data in one-minute intervals
    
    Parameters:
    ticker: Stock symbol to get data for
    
    Returns:
    Dict containing recent price data and summary statistics
    """
    print(f"📊 Fetching last 30 minutes of {ticker} data...")
    
    try:
        # Get recent data with 1-minute intervals for last 30 minutes
        ticker_data = get_ticker_recent_data(
            ticker=ticker, 
            period="1d", 
            interval="1m", 
            last_minutes=30
        )
        
        if not ticker_data:
            print(f"❌ No recent data available for {ticker}")
            return {}
        
        # Extract key information
        result = {
            'ticker': ticker,
            'current_price': ticker_data.get('current_price', 0.0),
            'price_change': ticker_data.get('price_change', 0.0),
            'price_change_pct': ticker_data.get('price_change_pct', 0.0),
            'volume': ticker_data.get('volume', 0),
            'timestamp': ticker_data.get('timestamp', datetime.now().isoformat()),
            'data_points': len(ticker_data.get('historical_data', [])),
            'period_summary': {
                'high': ticker_data.get('high', 0.0),
                'low': ticker_data.get('low', 0.0),
                'open': ticker_data.get('open', 0.0),
                'close': ticker_data.get('current_price', 0.0),
                'vwap': ticker_data.get('vwap', 0.0)
            },
            'technical_indicators': ticker_data.get('technical_indicators', {}),
            'source': 'tastytrade'
        }
        
        print(f"✅ Got {result['data_points']} data points for {ticker} over last 30 minutes")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching {ticker} 30-minute data: {e}")
        return {}


def get_options_chain_data(ticker: str, dte: int, current_price: Optional[float] = None) -> Dict[str, Any]:
    """
    Get options chain data for specified DTE with strikes within 5% of current price
    
    Parameters:
    ticker: Stock symbol
    dte: Days to expiration
    current_price: Current stock price (will fetch if not provided)
    
    Returns:
    Dict containing calls and puts with price and volume data
    """
    print(f"⚙️ Fetching {ticker} options chain for {dte}DTE...")
    
    try:
        # Get current price if not provided
        if current_price is None:
            current_price = get_current_price(ticker)
            
        if not current_price:
            print(f"❌ Could not get current price for {ticker}")
            return {}
        
        # Calculate 5% strike range
        strike_range = {
            'min': current_price * 0.95,  # 5% below
            'max': current_price * 1.05   # 5% above
        }
        
        print(f"📈 Current {ticker} price: ${current_price:.2f}")
        print(f"🎯 Strike range: ${strike_range['min']:.2f} - ${strike_range['max']:.2f}")
        
        # Get options chain
        options_data = get_options_chain(
            ticker=ticker,
            dte=dte,
            strike_range=strike_range,
            limit=100  # Get more options to ensure we capture the range
        )
        
        if not options_data:
            print(f"❌ No options data available for {ticker} {dte}DTE")
            return {}
        
        # Extract and format options data
        calls = []
        puts = []
        
        # Process the options data (format depends on what get_options_chain returns)
        if 'options' in options_data:
            for option in options_data['options']:
                option_info = {
                    'strike': option.get('strike_price', 0.0),
                    'bid': option.get('bid', 0.0),
                    'ask': option.get('ask', 0.0),
                    'last_price': option.get('last_price', 0.0),
                    'volume': option.get('volume', 0),
                    'open_interest': option.get('open_interest', 0),
                    'implied_volatility': option.get('implied_volatility', 0.0),
                    'delta': option.get('delta', 0.0),
                    'gamma': option.get('gamma', 0.0),
                    'theta': option.get('theta', 0.0),
                    'vega': option.get('vega', 0.0)
                }
                
                if option.get('option_type', '').lower() == 'call':
                    calls.append(option_info)
                elif option.get('option_type', '').lower() == 'put':
                    puts.append(option_info)
        
        result = {
            'ticker': ticker,
            'dte': dte,
            'current_price': current_price,
            'strike_range': strike_range,
            'calls': sorted(calls, key=lambda x: x['strike']),
            'puts': sorted(puts, key=lambda x: x['strike']),
            'total_options': len(calls) + len(puts),
            'timestamp': datetime.now().isoformat(),
            'source': 'tastytrade'
        }
        
        print(f"✅ Got {len(calls)} calls and {len(puts)} puts for {ticker} {dte}DTE")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching {ticker} options chain: {e}")
        return {}


def get_streamlined_market_data(ticker: str, dte: int) -> Dict[str, Any]:
    """
    Main function to gather all required market data using TastyTrade infrastructure
    
    Parameters:
    ticker: Primary ticker to analyze
    dte: Days to expiration for options analysis
    
    Returns:
    Comprehensive market data dictionary matching target format
    """
    print(f"🎯 Gathering streamlined market data for {ticker} {dte}DTE...")
    
    # Initialize result structure
    result = {
        'success': True,
        'ticker': ticker,
        'dte': dte,
        'timestamp': {
            'current_time': datetime.now().isoformat(),
            'market_date': datetime.now().strftime('%Y-%m-%d'),
            'market_time': datetime.now().strftime('%H:%M:%S EST'),
            'trading_day': datetime.now().strftime('%A, %B %d, %Y')
        },
        'global_markets': {},
        'spy_giants': {},
        'ticker_data': {},
        'options_chain': {},
        'source': 'tastytrade_streamlined'
    }
    
    try:
        # 1. Global Market Overview
        print("\n1️⃣ Fetching global market overview...")
        result['global_markets'] = get_global_market_overview()
        
        # 2. SPY Giants Overview (only if ticker is SPY)
        if ticker.upper() == 'SPY':
            print("\n2️⃣ Fetching SPY giants overview...")
            result['spy_giants'] = get_spy_giants_overview()
        
        # 3. Ticker 30-minute data
        print(f"\n3️⃣ Fetching {ticker} recent data...")
        result['ticker_data'] = get_ticker_30min_data(ticker)
        
        # 4. Options chain data
        print(f"\n4️⃣ Fetching {ticker} options chain...")
        current_price = result['ticker_data'].get('current_price')
        result['options_chain'] = get_options_chain_data(ticker, dte, current_price)
        
        print(f"\n✅ Successfully gathered streamlined market data for {ticker} {dte}DTE")
        print(f"📊 Data summary:")
        print(f"   - Global markets: {len(result['global_markets'])} symbols")
        print(f"   - SPY giants: {len(result['spy_giants'])} symbols")
        print(f"   - Ticker data points: {result['ticker_data'].get('data_points', 0)}")
        print(f"   - Options: {result['options_chain'].get('total_options', 0)} contracts")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in streamlined market data collection: {e}")
        result['success'] = False
        result['error'] = str(e)
        return result


if __name__ == "__main__":
    # Test the streamlined data collection
    print("🧪 Testing streamlined market data collection...")
    
    # Test with SPY 1DTE
    data = get_streamlined_market_data('SPY', 1)
    
    if data['success']:
        print("\n✅ Test successful!")
        print(json.dumps(data, indent=2, default=str)[:1000] + "...")
    else:
        print(f"\n❌ Test failed: {data.get('error', 'Unknown error')}")