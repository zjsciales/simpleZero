"""
Streamlined Market Data Collection
=================================

This module combines TastyTrade infrastructure (tt.py and tt_data.py) for real-time
data and options with yfinance for historical data needed for technical analysis.
Uses yfinance sparingly to avoid rate limiting.
"""

import json
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import config

# Import yfinance for historical data (used sparingly)
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
    print("✅ yfinance imported successfully")
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not available - technical analysis will use fallback values")

# Make sure yfinance is actually usable by trying a simple operation
if YFINANCE_AVAILABLE:
    try:
        # Simple test to verify yfinance is working
        test = yf.Ticker("SPY")
        test.info
        print("✅ yfinance tested and working")
    except Exception as e:
        print(f"⚠️ yfinance imported but not working: {e}")
        YFINANCE_AVAILABLE = False
from tt_data import get_market_overview, get_ticker_recent_data
from tt import get_options_chain_data, get_authenticated_headers

# Cache for yfinance data to minimize API calls
_yfinance_cache = {}
_cache_timeout = 300  # 5 minutes

# Cache for day changes (longer timeout since they change less frequently)
_day_change_cache = {}
_day_change_cache_timeout = 900  # 15 minutes

def get_day_changes_yfinance(symbols: List[str]) -> Dict[str, Dict]:
    """
    Get day-over-day changes for multiple symbols efficiently using yfinance
    Uses aggressive caching to minimize API calls (15-minute cache)
    
    Parameters:
    symbols: List of stock symbols
    
    Returns:
    Dict with symbols as keys and change data as values
    """
    if not YFINANCE_AVAILABLE:
        print(f"❌ yfinance not available for day changes")
        # Return placeholder data for sandbox mode
        return {
            symbol: {
                'day_change': 0.0,
                'day_change_percent': 0.0, 
                'current_price': 0.0,
                'previous_close': 0.0
            } 
            for symbol in symbols
        }
    
    current_time = datetime.now()
    results = {}
    
    # Check which symbols need fresh data
    symbols_to_fetch = []
    for symbol in symbols:
        cache_key = f"day_change_{symbol}"
        if cache_key in _day_change_cache:
            cached_data, cache_time = _day_change_cache[cache_key]
            if (current_time - cache_time).seconds < _day_change_cache_timeout:
                results[symbol] = cached_data
                continue
        symbols_to_fetch.append(symbol)
    
    if not symbols_to_fetch:
        print(f"✅ Using cached day changes for all {len(symbols)} symbols")
        return results
    
    try:
        print(f"📊 Fetching day changes from yfinance for: {', '.join(symbols_to_fetch)}")
        
        # Fetch 2 days of daily data to calculate day change
        for symbol in symbols_to_fetch:
            try:
                ticker_obj = yf.Ticker(symbol)
                hist_data = ticker_obj.history(period="2d", interval="1d")
                
                if len(hist_data) >= 2:
                    current_close = hist_data['Close'].iloc[-1]
                    previous_close = hist_data['Close'].iloc[-2]
                    day_change = current_close - previous_close
                    day_change_percent = (day_change / previous_close) * 100
                    
                    change_data = {
                        'day_change': float(day_change),
                        'day_change_percent': float(day_change_percent),
                        'current_price': float(current_close),
                        'previous_close': float(previous_close)
                    }
                    
                    results[symbol] = change_data
                    _day_change_cache[f"day_change_{symbol}"] = (change_data, current_time)
                    
                elif len(hist_data) == 1:
                    # Only one day of data, assume 0% change
                    current_close = hist_data['Close'].iloc[-1]
                    change_data = {
                        'day_change': 0.0,
                        'day_change_percent': 0.0,
                        'current_price': float(current_close),
                        'previous_close': float(current_close)
                    }
                    results[symbol] = change_data
                    _day_change_cache[f"day_change_{symbol}"] = (change_data, current_time)
                
            except Exception as e:
                print(f"⚠️ Error getting day change for {symbol}: {e}")
                # Provide fallback data
                results[symbol] = {
                    'day_change': 0.0,
                    'day_change_percent': 0.0,
                    'current_price': 0.0,
                    'previous_close': 0.0
                }
        
        print(f"✅ Retrieved day changes for {len(symbols_to_fetch)} symbols")
        return results
        
    except Exception as e:
        print(f"❌ Error fetching day changes from yfinance: {e}")
        return {symbol: {'day_change': 0.0, 'day_change_percent': 0.0, 'current_price': 0.0, 'previous_close': 0.0} for symbol in symbols_to_fetch}

def get_historical_data_yfinance(ticker: str, period: str = "5d", interval: str = "1h") -> Optional[pd.DataFrame]:
    """
    Get historical data using yfinance with caching to minimize API calls
    
    Parameters:
    ticker: Stock symbol
    period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
    interval: Data interval ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')
    
    Returns:
    DataFrame with OHLCV data or None if failed
    """
    if not YFINANCE_AVAILABLE:
        print(f"❌ yfinance not available for {ticker} historical data")
        return None
    
    # Create cache key
    cache_key = f"{ticker}_{period}_{interval}"
    current_time = datetime.now()
    
    # Check cache first
    if cache_key in _yfinance_cache:
        cached_data, cache_time = _yfinance_cache[cache_key]
        if (current_time - cache_time).seconds < _cache_timeout:
            print(f"✅ Using cached yfinance data for {ticker} ({period}, {interval})")
            return cached_data
    
    try:
        print(f"📊 Fetching {ticker} historical data from yfinance ({period}, {interval})...")
        
        # Create ticker object
        ticker_obj = yf.Ticker(ticker)
        
        # Get historical data
        hist_data = ticker_obj.history(period=period, interval=interval)
        
        if hist_data.empty:
            print(f"❌ No historical data returned for {ticker}")
            return None
        
        # Clean and standardize column names
        hist_data.columns = [col.title() for col in hist_data.columns]
        
        # Cache the result
        _yfinance_cache[cache_key] = (hist_data, current_time)
        
        print(f"✅ Retrieved {len(hist_data)} data points for {ticker} from yfinance")
        return hist_data
        
    except Exception as e:
        print(f"❌ Error fetching {ticker} data from yfinance: {e}")
        return None


def get_enhanced_historical_data(ticker: str, dte: int = 0) -> Optional[pd.DataFrame]:
    """
    Get historical data optimized for DTE-specific analysis using yfinance
    
    Parameters:
    ticker: Stock symbol
    dte: Days to expiration (determines timeframe)
    
    Returns:
    DataFrame with enhanced historical data including technical indicators
    """
    try:
        # DTE-aware timeframe selection for better technical analysis
        if dte == 0:
            # 0DTE: Need recent intraday data
            period = "1d"
            interval = "1m"
            min_periods = 30  # At least 30 minutes of data
        elif dte <= 3:
            # Short DTE: Recent hourly data
            period = "5d" 
            interval = "5m"
            min_periods = 50  # ~4 hours of 5min data
        elif dte <= 7:
            # Medium DTE: Recent daily data
            period = "1mo"
            interval = "15m"
            min_periods = 96  # ~1 day of 15min data
        else:
            # Longer DTE: More historical daily data
            period = "3mo"
            interval = "1h"
            min_periods = 100  # ~4 days of hourly data
        
        print(f"📈 Getting enhanced historical data for {ticker} ({dte}DTE): {period} @ {interval}")
        
        # Get data from yfinance
        hist_data = get_historical_data_yfinance(ticker, period, interval)
        
        if hist_data is None or len(hist_data) < min_periods:
            print(f"⚠️ Insufficient historical data for {ticker} (got {len(hist_data) if hist_data is not None else 0}, need {min_periods})")
            # Try a longer period as fallback
            if dte == 0:
                print(f"🔄 Trying 5d period for 0DTE fallback...")
                hist_data = get_historical_data_yfinance(ticker, "5d", "5m")
            
            if hist_data is None or len(hist_data) < 20:  # Absolute minimum
                print(f"❌ Cannot get sufficient historical data for {ticker}")
                return None
        
        # Add technical indicators
        hist_data = add_technical_indicators(hist_data)
        
        print(f"✅ Enhanced historical data ready: {len(hist_data)} periods with technical indicators")
        return hist_data
        
    except Exception as e:
        print(f"❌ Error getting enhanced historical data for {ticker}: {e}")
        return None


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add comprehensive technical indicators to historical data DataFrame
    
    Parameters:
    df: DataFrame with OHLCV data
    
    Returns:
    DataFrame with added technical indicators
    """
    if df is None or df.empty:
        return df
    
    try:
        # Ensure we have the required columns
        if 'Close' not in df.columns:
            print(f"❌ No 'Close' column in DataFrame")
            return df
        
        print(f"🔧 Adding technical indicators to {len(df)} data points...")
        
        # Moving Averages
        df['SMA_10'] = df['Close'].rolling(window=10, min_periods=1).mean()
        df['SMA_20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['SMA_50'] = df['Close'].rolling(window=min(50, len(df)), min_periods=1).mean()
        df['EMA_10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        
        # RSI
        df = add_rsi_indicator(df)
        
        # Bollinger Bands
        df = add_bollinger_bands(df)
        
        # Volume indicators
        if 'Volume' in df.columns:
            df['Volume_SMA'] = df['Volume'].rolling(window=20, min_periods=1).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        
        # ATR (Average True Range)
        df = add_atr_indicator(df)
        
        print(f"✅ Technical indicators added successfully")
        return df
        
    except Exception as e:
        print(f"❌ Error adding technical indicators: {e}")
        return df


def add_rsi_indicator(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add RSI indicator to DataFrame"""
    try:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
        
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    except Exception as e:
        print(f"⚠️ Error adding RSI: {e}")
        return df


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Add Bollinger Bands to DataFrame"""
    try:
        # Use appropriate period based on data length
        actual_period = min(period, len(df))
        
        sma = df['Close'].rolling(window=actual_period, min_periods=1).mean()
        std = df['Close'].rolling(window=actual_period, min_periods=1).std()
        
        df['BB_Upper'] = sma + (std * std_dev)
        df['BB_Lower'] = sma - (std * std_dev)
        df['BB_Middle'] = sma
        
        # Band width and position
        df['BB_Width'] = ((df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']) * 100
        df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        
        return df
    except Exception as e:
        print(f"⚠️ Error adding Bollinger Bands: {e}")
        return df


def add_atr_indicator(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add Average True Range (ATR) indicator"""
    try:
        if len(df) < 2:
            return df
            
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(window=min(period, len(df)), min_periods=1).mean()
        
        return df
    except Exception as e:
        print(f"⚠️ Error adding ATR: {e}")
        return df


def get_available_dtes(ticker: str) -> List[Dict[str, Any]]:
    """
    Get all available DTEs (Days to Expiration) for a ticker by fetching the raw options chain
    and analyzing what expiration dates are actually available in the market.
    
    Parameters:
    ticker: Stock symbol to check
    
    Returns:
    List of dictionaries with 'dte', 'expiration_date', and 'count' for available options
    """
    print(f"🔍 Checking available DTEs for {ticker}...")
    
    try:
        # Get the raw options chain from TastyTrade API using unified environment-based endpoint
        import config
        base_url = config.TT_BASE_URL  # Use unified environment-aware URL
        options_url = f"{base_url}/option-chains/{ticker}"
        
        headers = get_authenticated_headers()
        if not headers:
            print("❌ No authentication available for options chain")
            return []
            
        print(f"🔗 Calling: {options_url}")
        print(f"🌍 Environment: {config.ENVIRONMENT_NAME}")
        response = requests.get(options_url, headers=headers)
        print(f"📡 Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch options chain: {response.text}")
            return []
        
        data = response.json()
        
        # Parse expiration dates from the response
        available_dtes = []
        today = datetime.now().date()
        
        # The structure depends on TastyTrade API response format
        # Let's check what we get back
        print(f"📊 Raw API response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        if 'data' in data and 'items' in data['data']:
            # Group by expiration date
            expiration_counts = {}
            
            for item in data['data']['items']:
                if 'expiration-date' in item:
                    exp_date_str = item['expiration-date']
                    try:
                        exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date()
                        dte = (exp_date - today).days
                        
                        if dte >= 0:  # Only future or today's expirations
                            if exp_date_str not in expiration_counts:
                                expiration_counts[exp_date_str] = {
                                    'dte': dte,
                                    'expiration_date': exp_date_str,
                                    'count': 0
                                }
                            expiration_counts[exp_date_str]['count'] += 1
                    except ValueError:
                        continue
            
            # Convert to sorted list
            available_dtes = list(expiration_counts.values())
            available_dtes.sort(key=lambda x: x['dte'])
            
            print(f"✅ Found {len(available_dtes)} available DTEs for {ticker}")
            for dte_info in available_dtes[:10]:  # Show first 10
                print(f"   📅 {dte_info['dte']}DTE ({dte_info['expiration_date']}) - {dte_info['count']} options")
        
        return available_dtes
        
    except Exception as e:
        print(f"❌ Error getting available DTEs for {ticker}: {e}")
        return []


def get_global_market_overview() -> Dict[str, Dict]:
    """
    Get current prices of global market indicators with day-over-day data
    Uses TastyTrade as primary source, yfinance as fallback
    Returns blank fields instead of fallback values if both sources fail
    
    Returns:
    Dict with symbols as keys and market data as values
    """
    symbols = ['QQQ', 'TLT', 'GLD', 'USO', 'IBIT', 'NDAQ']
    
    print(f"🌍 Fetching global market overview for: {', '.join(symbols)}")
    
    try:
        # Get basic market data from TastyTrade
        market_data = get_market_overview(symbols=symbols, force_refresh=True)
        
        # Get yfinance data as backup only if TastyTrade data is incomplete
        day_changes = {}
        if YFINANCE_AVAILABLE:
            day_changes = get_day_changes_yfinance(symbols)
        
        # Format for consistency with enhanced day change data
        formatted_data = {}
        
        # Process each symbol, preferring TastyTrade data when available
        for symbol in symbols:
            tt_data = market_data.get(symbol, {})
            yf_data = day_changes.get(symbol, {})
            
            # Create entry using primary TastyTrade data, with yfinance as backup
            # Use None (not 0.0) for missing data to display as blank
            formatted_data[symbol] = {
                'symbol': symbol,
                # Current price: TastyTrade → yfinance → None
                'current_price': tt_data.get('current_price') or yf_data.get('current_price'),
                # Bid/Ask: TastyTrade only → None
                'bid': tt_data.get('bid'),
                'ask': tt_data.get('ask'),
                # Day change: TastyTrade → yfinance → None
                'day_change': tt_data.get('day_change') or yf_data.get('day_change'),
                'day_change_percent': tt_data.get('day_change_percent') or yf_data.get('day_change_percent'),
                # Volume: TastyTrade → yfinance → None
                'volume': tt_data.get('volume'),
                # Timestamp: TastyTrade → current time
                'timestamp': tt_data.get('timestamp') or datetime.now().isoformat(),
                # Source tracking
                'source': 'tastytrade' if tt_data else ('yfinance' if yf_data else 'none')
            }
            
            # Remove None values to ensure they're shown as blank
            formatted_data[symbol] = {k: v for k, v in formatted_data[symbol].items() if k == 'symbol' or v is not None}
        
        print(f"✅ Got global market data for {len(formatted_data)} symbols")
        return formatted_data
        
    except Exception as e:
        print(f"❌ Error fetching global market overview: {e}")
        # Return minimal data with just symbols - no fallback values
        return {symbol: {'symbol': symbol} for symbol in symbols}


def get_spy_giants_overview() -> Dict[str, Dict]:
    """
    Get current prices of SPY's largest holdings with day-over-day data
    Uses TastyTrade as primary source, yfinance as fallback
    Returns blank fields instead of fallback values if both sources fail
    
    Returns:
    Dict with symbols as keys and market data as values  
    """
    spy_giants = ['NVDA', 'MSFT', 'AAPL', 'AMZN', 'META', 'GOOGL']
    
    print(f"🏢 Fetching SPY giants overview for: {', '.join(spy_giants)}")
    
    try:
        # Get basic market data from TastyTrade
        market_data = get_market_overview(symbols=spy_giants, force_refresh=True)
        
        # Get yfinance data as backup only if needed
        day_changes = {}
        if YFINANCE_AVAILABLE:
            day_changes = get_day_changes_yfinance(spy_giants)
        
        # Format for consistency with enhanced day change data
        formatted_data = {}
        
        # Process each symbol, preferring TastyTrade data when available
        for symbol in spy_giants:
            tt_data = market_data.get(symbol, {})
            yf_data = day_changes.get(symbol, {})
            
            # Create entry using primary TastyTrade data, with yfinance as backup
            # Use None (not 0.0) for missing data to display as blank
            formatted_data[symbol] = {
                'symbol': symbol,
                # Current price: TastyTrade → yfinance → None
                'current_price': tt_data.get('current_price') or yf_data.get('current_price'),
                # Bid/Ask: TastyTrade only → None
                'bid': tt_data.get('bid'),
                'ask': tt_data.get('ask'),
                # Day change: TastyTrade → yfinance → None
                'day_change': tt_data.get('day_change') or yf_data.get('day_change'),
                'day_change_percent': tt_data.get('day_change_percent') or yf_data.get('day_change_percent'),
                # Volume: TastyTrade → yfinance → None
                'volume': tt_data.get('volume'),
                # Timestamp: TastyTrade → current time
                'timestamp': tt_data.get('timestamp') or datetime.now().isoformat(),
                # Source tracking
                'source': 'tastytrade' if tt_data else ('yfinance' if yf_data else 'none')
            }
            
            # Remove None values to ensure they're shown as blank
            formatted_data[symbol] = {k: v for k, v in formatted_data[symbol].items() if k == 'symbol' or v is not None}
        
        print(f"✅ Got SPY giants data for {len(formatted_data)} symbols")
        return formatted_data
        
    except Exception as e:
        print(f"❌ Error fetching SPY giants overview: {e}")
        # Return minimal data with just symbols - no fallback values
        return {symbol: {'symbol': symbol} for symbol in spy_giants}


def get_ticker_30min_data(ticker: str) -> Dict[str, Any]:
    """
    Get last 30 minutes of ticker data with enhanced technical analysis
    
    Parameters:
    ticker: Stock symbol to get data for
    
    Returns:
    Dict containing recent price data and enhanced technical analysis
    """
    print(f"📊 Fetching last 30 minutes of {ticker} data...")
    
    try:
        # Get recent data from TastyTrade
        ticker_data = get_ticker_recent_data(
            ticker=ticker, 
            period="1d", 
            interval="1m", 
            last_minutes=30
        )
        
        if not ticker_data:
            print(f"❌ No recent data available for {ticker} from TastyTrade")
            ticker_data = {}
        
        # Get enhanced technical analysis from yfinance
        print(f"📈 Getting enhanced technical analysis for {ticker}...")
        enhanced_data = get_enhanced_historical_data(ticker, dte=0)
        
        if enhanced_data is not None and not enhanced_data.empty:
            latest = enhanced_data.iloc[-1]
            
            # Enhanced technical indicators from yfinance
            enhanced_technical = {
                'rsi': float(latest.get('RSI', 50.0)),
                'bb_position': float(latest.get('BB_Position', 0.5)),
                'bb_upper': float(latest.get('BB_Upper', 0)),
                'bb_lower': float(latest.get('BB_Lower', 0)),
                'bb_width': float(latest.get('BB_Width', 0)),
                'sma_20': float(latest.get('SMA_20', 0)),
                'sma_50': float(latest.get('SMA_50', 0)),
                'ema_10': float(latest.get('EMA_10', 0)),
                'ema_20': float(latest.get('EMA_20', 0)),
                'volume_ratio': float(latest.get('Volume_Ratio', 1.0)),
                'atr': float(latest.get('ATR', 0)),
                'data_source': 'yfinance_enhanced'
            }
        else:
            print(f"⚠️ Using fallback technical indicators for {ticker}")
            enhanced_technical = {
                'rsi': 50.0,
                'bb_position': 0.5,
                'bb_upper': 0,
                'bb_lower': 0,
                'bb_width': 0,
                'sma_20': 0,
                'sma_50': 0,
                'ema_10': 0,
                'ema_20': 0,
                'volume_ratio': 1.0,
                'atr': 0,
                'data_source': 'fallback'
            }
        
        # Extract key information with yfinance fallback for current price
        current_price = ticker_data.get('current_price', 0.0)
        
        # If TastyTrade failed to get current price, use yfinance data as fallback
        if current_price == 0.0 and enhanced_data is not None and not enhanced_data.empty:
            yf_current_price = float(enhanced_data['Close'].iloc[-1])
            print(f"🔄 TastyTrade current_price unavailable, using yfinance fallback: ${yf_current_price:.2f}")
            current_price = yf_current_price
            
            # Also get volume and other price data from yfinance
            if ticker_data.get('volume', 0) == 0:
                yf_volume = int(enhanced_data['Volume'].iloc[-1])
                ticker_data['volume'] = yf_volume
                print(f"🔄 Using yfinance volume: {yf_volume:,}")
            
            # Update price change calculations using yfinance data
            if len(enhanced_data) >= 2:
                prev_close = float(enhanced_data['Close'].iloc[-2])
                price_change = current_price - prev_close
                price_change_pct = (price_change / prev_close * 100) if prev_close != 0 else 0
                ticker_data['price_change'] = price_change
                ticker_data['price_change_pct'] = price_change_pct
                print(f"🔄 Using yfinance price change: ${price_change:.2f} ({price_change_pct:+.2f}%)")
        
        result = {
            'ticker': ticker,
            'current_price': current_price,
            'price_change': ticker_data.get('price_change', 0.0),
            'price_change_pct': ticker_data.get('price_change_pct', 0.0),
            'volume': ticker_data.get('volume', 0),
            'timestamp': ticker_data.get('timestamp', datetime.now().isoformat()),
            'data_points': len(ticker_data.get('historical_data', [])),
            'period_summary': {
                'high': ticker_data.get('high', current_price),
                'low': ticker_data.get('low', current_price),
                'open': ticker_data.get('open', current_price),
                'close': current_price,
                'vwap': ticker_data.get('vwap', current_price)
            },
            'technical_indicators': enhanced_technical,
            'source': 'yfinance_fallback' if current_price != ticker_data.get('current_price', 0.0) else 'tastytrade_with_yfinance_technical'
        }
        
        # Check if we have valid current price data
        if current_price == 0.0:
            print(f"❌ Failed to get current price for {ticker} from both TastyTrade and yfinance")
            print(f"⚠️ Using fallback data structure with technical indicators only")
        
        print(f"✅ Got {result['data_points']} data points for {ticker} with enhanced technical analysis")
        print(f"💰 Current price: ${current_price:.2f}" if current_price > 0 else "❌ No current price available")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching {ticker} enhanced data: {e}")
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
        print(f"🔍 [LOGGING] About to call get_options_chain_data with:")
        print(f"   📊 ticker: {ticker}")
        print(f"   📊 dte: {dte}")
        print(f"   📊 current_price: ${current_price:.2f}" if current_price else "   📊 current_price: None")
        
        result['options_chain'] = get_options_chain_data(ticker, dte, current_price)
        
        print(f"🔍 [LOGGING] get_options_chain_data returned:")
        options_chain = result['options_chain']
        if options_chain:
            calls = options_chain.get('calls', [])
            puts = options_chain.get('puts', [])
            print(f"   📊 calls: {len(calls)}")
            print(f"   📊 puts: {len(puts)}")
            if calls:
                call_strikes = [c.get('strike', 0) for c in calls[:5]]
                print(f"   📊 sample call strikes: {call_strikes}")
            if puts:
                put_strikes = [p.get('strike', 0) for p in puts[:5]]
                print(f"   📊 sample put strikes: {put_strikes}")
            else:
                print(f"   ❌ No puts returned from get_options_chain_data!")
        else:
            print(f"   ❌ Empty options_chain returned!")
        
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




# =============================================================================
# TECHNICAL ANALYSIS FUNCTIONS
# =============================================================================
# Moved from tt_data.py to consolidate all market analysis in one place

def calculate_simple_moving_average(data, window: int):
    """Calculate Simple Moving Average"""
    import pandas as pd
    if isinstance(data, list):
        data = pd.Series(data)
    return data.rolling(window=window, min_periods=1).mean()

def calculate_exponential_moving_average(data, window: int):
    """Calculate Exponential Moving Average"""
    import pandas as pd
    if isinstance(data, list):
        data = pd.Series(data)
    return data.ewm(span=window, adjust=False).mean()

def calculate_bollinger_bands(data, period: int = 20, std_dev: float = 2.0):
    """
    Enhanced Bollinger Bands calculation with squeeze detection and volatility breakout analysis
    
    Parameters:
    data: DataFrame or Series with price data
    period: Period for moving average calculation (default: 20)
    std_dev: Standard deviation multiplier (default: 2.0)
    
    Returns:
    Dictionary with Bollinger Bands data
    """
    import pandas as pd
    
    if isinstance(data, list):
        data = pd.Series(data)
    elif isinstance(data, pd.DataFrame):
        data = data['close'] if 'close' in data.columns else data.iloc[:, 0]
    
    try:
        # Calculate moving average and standard deviation
        sma = data.rolling(window=period, min_periods=1).mean()
        std = data.rolling(window=period, min_periods=1).std()
        
        # Calculate bands
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        # Calculate additional metrics
        current_price = data.iloc[-1] if len(data) > 0 else 0
        current_sma = sma.iloc[-1] if len(sma) > 0 else 0
        current_upper = upper_band.iloc[-1] if len(upper_band) > 0 else 0
        current_lower = lower_band.iloc[-1] if len(lower_band) > 0 else 0
        
        # Band width (measure of volatility)
        band_width = ((current_upper - current_lower) / current_sma * 100) if current_sma > 0 else 0
        
        # Position within bands
        band_position = ((current_price - current_lower) / (current_upper - current_lower) * 100) if (current_upper - current_lower) > 0 else 50
        
        return {
            'sma': current_sma,
            'upper_band': current_upper,
            'lower_band': current_lower,
            'band_width': band_width,
            'band_position': band_position,
            'price': current_price,
            'squeeze': band_width < 10,  # Bollinger Band squeeze threshold
            'breakout': band_position > 95 or band_position < 5
        }
        
    except Exception as e:
        print(f"❌ Error calculating Bollinger Bands: {e}")
        return {
            'sma': 0, 'upper_band': 0, 'lower_band': 0, 'band_width': 0,
            'band_position': 50, 'price': 0, 'squeeze': False, 'breakout': False
        }

def calculate_rsi_enhanced(ticker: str, dte: int = 0, period: int = 14) -> Dict:
    """
    Enhanced RSI analysis using yfinance historical data for accurate calculations
    
    Parameters:
    ticker: Stock symbol
    dte: Days to expiration (affects timeframe selection)
    period: RSI calculation period (default: 14)
    
    Returns:
    Dictionary with comprehensive RSI data
    """
    try:
        # Get enhanced historical data with technical indicators
        historical_data = get_enhanced_historical_data(ticker, dte)
        
        if historical_data is None or historical_data.empty:
            print(f"❌ No historical data for RSI calculation - using fallback")
            return {
                'current_rsi': 50.0,
                'trend': 'neutral',
                'signal': 'hold',
                'strength': 0.0,
                'momentum': 'neutral',
                'timeframe': f'dte_{dte}',
                'error': 'No historical data available',
                'data_source': 'fallback'
            }
        
        # Get RSI from the pre-calculated technical indicators
        if 'RSI' in historical_data.columns:
            current_rsi = historical_data['RSI'].iloc[-1]
            
            # Calculate RSI momentum (rate of change)
            if len(historical_data) >= 5:
                rsi_5_ago = historical_data['RSI'].iloc[-5]
                rsi_momentum = current_rsi - rsi_5_ago
                momentum_strength = abs(rsi_momentum)
            else:
                rsi_momentum = 0
                momentum_strength = 0
            
            # Enhanced trend analysis
            if current_rsi >= 70:
                if rsi_momentum > 2:
                    trend = 'strongly_overbought'
                    signal = 'strong_sell'
                else:
                    trend = 'overbought'
                    signal = 'sell'
            elif current_rsi <= 30:
                if rsi_momentum < -2:
                    trend = 'strongly_oversold'
                    signal = 'strong_buy'
                else:
                    trend = 'oversold'
                    signal = 'buy'
            elif current_rsi >= 60:
                trend = 'bullish'
                signal = 'hold' if rsi_momentum < 0 else 'weak_buy'
            elif current_rsi <= 40:
                trend = 'bearish'
                signal = 'hold' if rsi_momentum > 0 else 'weak_sell'
            else:
                trend = 'neutral'
                signal = 'hold'
            
            # Determine momentum direction
            if rsi_momentum > 1:
                momentum = 'accelerating_up'
            elif rsi_momentum < -1:
                momentum = 'accelerating_down'
            elif rsi_momentum > 0:
                momentum = 'rising'
            elif rsi_momentum < 0:
                momentum = 'falling'
            else:
                momentum = 'neutral'
            
            return {
                'current_rsi': float(current_rsi),
                'trend': trend,
                'signal': signal,
                'strength': float(momentum_strength),
                'momentum': momentum,
                'timeframe': f'dte_{dte}',
                'period': period,
                'data_points': len(historical_data),
                'data_source': 'yfinance'
            }
        else:
            print(f"❌ RSI not calculated in technical indicators")
            return {
                'current_rsi': 50.0,
                'trend': 'neutral',
                'signal': 'hold',
                'error': 'RSI calculation failed'
            }
        
    except Exception as e:
        print(f"❌ Error calculating enhanced RSI: {e}")
        return {
            'current_rsi': 50.0,
            'trend': 'neutral',
            'signal': 'hold',
            'error': str(e)
        }


def get_enhanced_market_state(ticker: str, dte: int = 0) -> Optional[Dict]:
    """
    Get comprehensive market state using yfinance historical data
    
    Parameters:
    ticker: Stock symbol
    dte: Days to expiration
    
    Returns:
    Dict with comprehensive market state analysis
    """
    try:
        # Get enhanced historical data
        data = get_enhanced_historical_data(ticker, dte)
        
        if data is None or data.empty:
            print(f"❌ No data for market state analysis")
            return None
        
        latest = data.iloc[-1]
        current_price = latest['Close']
        
        # Get technical indicators
        rsi = latest.get('RSI', 50.0)
        bb_position = latest.get('BB_Position', 0.5)
        bb_upper = latest.get('BB_Upper', current_price)
        bb_lower = latest.get('BB_Lower', current_price)
        bb_width = latest.get('BB_Width', 0)
        
        # Moving averages
        sma_20 = latest.get('SMA_20', current_price)
        sma_50 = latest.get('SMA_50', current_price)
        ema_10 = latest.get('EMA_10', current_price)
        ema_20 = latest.get('EMA_20', current_price)
        
        # Volume analysis
        volume_ratio = latest.get('Volume_Ratio', 1.0)
        atr = latest.get('ATR', 0)
        
        # Market state determination
        if bb_width < 10:
            market_state = 'Low Volatility Squeeze'
        elif bb_position > 0.95:
            market_state = 'Upper Bollinger Breakout'
        elif bb_position < 0.05:
            market_state = 'Lower Bollinger Breakout'
        elif bb_position > 0.8:
            market_state = 'Near Upper Band'
        elif bb_position < 0.2:
            market_state = 'Near Lower Band'
        elif bb_width > 25:
            market_state = 'High Volatility'
        else:
            market_state = 'Normal Range'
        
        # Trend analysis
        sma_trend_strength = abs(sma_20 - sma_50) / sma_50 if sma_50 > 0 else 0
        ema_trend_strength = abs(ema_10 - ema_20) / ema_20 if ema_20 > 0 else 0
        
        # Enhanced trend classification
        if current_price > sma_20 > sma_50:
            if sma_trend_strength > 0.02:
                sma_trend = 'strong_bullish'
            else:
                sma_trend = 'bullish'
        elif current_price < sma_20 < sma_50:
            if sma_trend_strength > 0.02:
                sma_trend = 'strong_bearish'
            else:
                sma_trend = 'bearish'
        else:
            sma_trend = 'neutral'
        
        if ema_10 > ema_20:
            if ema_trend_strength > 0.015:
                ema_trend = 'strong_bullish'
            else:
                ema_trend = 'bullish'
        elif ema_10 < ema_20:
            if ema_trend_strength > 0.015:
                ema_trend = 'strong_bearish' 
            else:
                ema_trend = 'bearish'
        else:
            ema_trend = 'neutral'
        
        return {
            'current_price': current_price,
            'rsi': float(rsi),
            'bb_position': float(bb_position),
            'bb_upper': float(bb_upper),
            'bb_lower': float(bb_lower),
            'bb_width': float(bb_width),
            'sma_20': float(sma_20),
            'sma_50': float(sma_50),
            'ema_10': float(ema_10),
            'ema_20': float(ema_20),
            'market_state': market_state,
            'sma_trend': sma_trend,
            'ema_trend': ema_trend,
            'trend_strength_sma': float(sma_trend_strength),
            'trend_strength_ema': float(ema_trend_strength),
            'volume_ratio': float(volume_ratio),
            'atr': float(atr),
            'volatility_regime': 'high' if bb_width > 20 else 'low' if bb_width < 10 else 'normal',
            'data_points': len(data),
            'timestamp': latest.name.isoformat() if hasattr(latest.name, 'isoformat') else datetime.now().isoformat(),
            'data_source': 'yfinance'
        }
        
    except Exception as e:
        logging.error(f"Error getting enhanced market state: {e}")
        return None

def get_market_overview_comprehensive(symbols: List[str] = None, force_refresh: bool = False) -> Dict[str, Dict]:
    """
    Comprehensive market overview with technical analysis integration
    
    Parameters:
    symbols: List of symbols to analyze (defaults to major market indicators)
    force_refresh: Force refresh of cached data
    
    Returns:
    Dictionary with comprehensive market data and technical analysis
    """
    from tt_data import get_market_overview_tastytrade
    
    # Default symbols for market overview
    if symbols is None:
        symbols = ['SPY', 'QQQ', 'IWM', 'TLT', 'GLD', 'VIX']
    
    # Get basic market data
    market_data = get_market_overview_tastytrade(symbols, force_refresh)
    
    # Add technical analysis for each symbol
    for symbol in symbols:
        if symbol in market_data:
            try:
                # Add RSI analysis using enhanced function
                rsi_data = calculate_rsi_enhanced(symbol, dte=0)
                market_data[symbol]['rsi'] = rsi_data
                
                # Add trend analysis based on RSI
                market_data[symbol]['technical_trend'] = rsi_data.get('trend', 'neutral')
                market_data[symbol]['technical_signal'] = rsi_data.get('signal', 'hold')
                
            except Exception as e:
                print(f"⚠️ Could not add technical analysis for {symbol}: {e}")
                market_data[symbol]['rsi'] = {'current_rsi': 50.0, 'trend': 'neutral', 'signal': 'hold'}
    
    return market_data

def get_current_market_state(data: pd.DataFrame) -> Optional[Dict]:
    """Enhanced market state analysis with volatility breakout and squeeze detection"""
    if data is None or data.empty:
        return None
    
    try:
        latest = data.iloc[-1]
        current_price = latest['Close']
        
        # Standard Bollinger Bands
        upper_band = latest.get('BB_Upper', latest.get('Upper_Band', current_price))
        lower_band = latest.get('BB_Lower', latest.get('Lower_Band', current_price))
        bb_middle = latest.get('BB_Middle', latest.get('SMA_20', current_price))
        
        # Enhanced volatility analysis
        bb_width = latest.get('BB_Width', 0)
        bb_squeeze = latest.get('BB_Squeeze', False)
        bb_position = latest.get('BB_Position', 0.5)
        upper_breakout = latest.get('BB_Upper_Breakout', False)
        lower_breakout = latest.get('BB_Lower_Breakout', False)
        significant_breakout = latest.get('Significant_Breakout', False)
        volatility_expansion = latest.get('Volatility_Expansion', False)
        
        # Volume analysis
        volume_ratio = latest.get('Volume_Ratio', 1.0)
        atr = latest.get('ATR', 0)
        atr_ratio = latest.get('ATR_Ratio', 1.0)
        
        # Calculate bb_percent (position within bands)
        if upper_band != lower_band:
            bb_percent = (current_price - lower_band) / (upper_band - lower_band)
            # Calculate deviation from center (-1 to +1, where 0 is center)
            deviation_from_center = (bb_percent - 0.5) * 2
        else:
            bb_percent = 0.5
            deviation_from_center = 0.0
        
        # Get additional moving averages
        sma_20 = latest.get('SMA_20', current_price)
        sma_50 = latest.get('SMA_50', current_price)
        ema_10 = latest.get('EMA_10', current_price)
        ema_20 = latest.get('EMA_20', current_price)
        
        # Enhanced market state determination
        if bb_squeeze:
            market_state = 'Squeeze (Low Volatility)'
        elif significant_breakout:
            if upper_breakout:
                market_state = 'Bullish Breakout (High Volume)'
            elif lower_breakout:
                market_state = 'Bearish Breakout (High Volume)'
            else:
                market_state = 'Significant Breakout'
        elif upper_breakout:
            market_state = 'Upper Band Breakout'
        elif lower_breakout:
            market_state = 'Lower Band Breakout'
        elif volatility_expansion:
            market_state = 'Volatility Expansion'
        elif bb_percent > 0.8:
            market_state = 'Near Upper Band'
        elif bb_percent < 0.2:
            market_state = 'Near Lower Band'
        else:
            market_state = 'Normal Range'
        
        # Trend analysis with strength
        sma_trend_strength = abs(sma_20 - sma_50) / sma_50 if sma_50 > 0 else 0
        ema_trend_strength = abs(ema_10 - ema_20) / ema_20 if ema_20 > 0 else 0
        
        # Enhanced trend interpretation
        if sma_20 > sma_50:
            if sma_trend_strength > 0.02:  # 2% difference
                sma_trend = 'strong_bullish'
            else:
                sma_trend = 'bullish'
        elif sma_20 < sma_50:
            if sma_trend_strength > 0.02:
                sma_trend = 'strong_bearish'
            else:
                sma_trend = 'bearish'
        else:
            sma_trend = 'neutral'
        
        if ema_10 > ema_20:
            if ema_trend_strength > 0.015:  # 1.5% difference for faster EMA
                ema_trend = 'strong_bullish'
            else:
                ema_trend = 'bullish'
        elif ema_10 < ema_20:
            if ema_trend_strength > 0.015:
                ema_trend = 'strong_bearish'
            else:
                ema_trend = 'bearish'
        else:
            ema_trend = 'neutral'
        
        return {
            'current_price': current_price,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'sma_20': sma_20,
            'sma_50': sma_50,
            'ema_10': ema_10,
            'ema_20': ema_20,
            'bb_percent': bb_percent,
            'percent_position': bb_percent,  # Alias for grok.py compatibility
            'deviation_from_center': deviation_from_center,
            'market_state': market_state,
            'sma_trend': sma_trend,
            'ema_trend': ema_trend,
            
            # Enhanced volatility metrics
            'bb_width': round(bb_width, 4),
            'bb_squeeze': bb_squeeze,
            'bb_position': round(bb_position, 3),
            'upper_breakout': upper_breakout,
            'lower_breakout': lower_breakout,
            'significant_breakout': significant_breakout,
            'volatility_expansion': volatility_expansion,
            'volume_ratio': round(volume_ratio, 2),
            'atr': round(atr, 4),
            'atr_ratio': round(atr_ratio, 2),
            'trend_strength_sma': round(sma_trend_strength, 4),
            'trend_strength_ema': round(ema_trend_strength, 4),
            
            'timestamp': latest.name.isoformat() if hasattr(latest.name, 'isoformat') else datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error getting enhanced market state: {e}")
        return None

class TechnicalAnalysisManager:
    """Simplified Technical Analysis Manager for DTE-aware analysis"""
    
    def __init__(self, dte: int = 0, ticker: str = "SPY"):
        self.dte = dte
        self.ticker = ticker
        
    def calculate_rsi(self, period: int = 14) -> Dict:
        """Calculate RSI using enhanced yfinance data"""
        try:
            # Use the enhanced RSI calculation
            rsi_data = calculate_rsi_enhanced(self.ticker, self.dte, period)
            
            # Format response to match expected interface
            current_rsi = rsi_data.get('current_rsi', 50.0)
            
            # Basic interpretation
            if current_rsi >= 70:
                interpretation = 'overbought'
                signal = 'sell'
            elif current_rsi <= 30:
                interpretation = 'oversold'
                signal = 'buy'
            else:
                interpretation = 'neutral'
                signal = 'hold'
            
            # Basic trend (simplified)
            trend = rsi_data.get('trend', 'neutral')
            
            return {
                'status': 'success',
                'current_rsi': current_rsi,
                'interpretation': interpretation,
                'trend': trend,
                'signal': signal,
                'timeframe': rsi_data.get('timeframe', f'dte_{self.dte}'),
                'data_source': rsi_data.get('data_source', 'yfinance')
            }
            
        except Exception as e:
            logging.error(f"Error calculating RSI for {self.ticker}: {e}")
            return {
                'status': 'error',
                'current_rsi': 50.0,
                'interpretation': 'neutral',
                'trend': 'neutral',
                'signal': 'hold'
            }

if __name__ == "__main__":
    # Test the streamlined data collection
    print("🧪 Testing streamlined market data collection...")
    
    # Test with SPY 1DTE
    data = get_streamlined_market_data('SPY', 1)
    
    if data['success']:
        print("\n✅ Test successful!")
        print(f"📊 Summary: {len(data.get('options_chain', {}).get('calls', []))} calls, {len(data.get('options_chain', {}).get('puts', []))} puts")
    else:
        print(f"\n❌ Test failed: {data.get('error', 'Unknown error')}")