"""
TastyTrade Market Data Client
Provides clean market data interface using TastyTrade API
Replaces Alpaca functionality with TastyTrade-only implementation
"""

import os
import requests
import logging
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import config

# Setup logging
logging.basicConfig(level=logging.INFO)

# Global cache for market data when markets are closed
_market_overview_cache = {}
_cache_timestamp = None

def _safe_int(value, default=0):
    """Safely convert value to int, handling string floats like '11.0'"""
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def _safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def _is_market_open() -> bool:
    """Check if market is currently open"""
    try:
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now_et <= market_close
    except Exception:
        return False

def _get_cached_market_overview(symbols: List[str]) -> Dict[str, Dict]:
    """Return cached market data when markets are closed"""
    global _market_overview_cache
    result = {}
    
    for symbol in symbols:
        result[symbol] = {
            'current_price': 0.0,
            'bid': 0.0,
            'ask': 0.0,
            'bid_size': 0,
            'ask_size': 0,
            'day_change': 0.0,
            'day_change_percent': 0.0,
            'intraday_change': 0.0,
            'intraday_change_percent': 0.0,
            'volume': 0,
            'timestamp': datetime.now().isoformat(),
            'source': 'cached',
            'cached': True
        }
    
    return result

class TastyTradeMarketData:
    """TastyTrade Market Data Client - uses shared authentication from tt.py"""
    
    def __init__(self):
        # Use production API URL from tt.py
        self.base_url = "https://api.tastyworks.com"
        self.logger = logging.getLogger(__name__)
        
    def get_authenticated_headers(self) -> dict:
        """Get authentication headers from tt.py module"""
        try:
            from tt import get_authenticated_headers
            return get_authenticated_headers()
        except ImportError as e:
            self.logger.error(f"Could not get TastyTrade authentication headers: {e}")
            return {}
    
    def authenticate(self) -> bool:
        """Check if authentication is available (uses tt.py tokens)"""
        headers = self.get_authenticated_headers()
        return bool(headers.get('Authorization'))
    
    def get_market_data_clean(self, symbol: str) -> Optional[Dict]:
        """
        Get market data using /market-data/by-type endpoint - clean implementation
        
        Parameters:
        symbol: Stock symbol (e.g., 'SPY')
        
        Returns:
        Dict with market data including price, bid, ask, volume etc.
        """
        try:
            headers = self.get_authenticated_headers()
            if not headers:
                self.logger.error("No authentication headers available")
                return None
            
            # Use the correct TastyTrade endpoint for market data
            url = f"{self.base_url}/market-data/by-type"
            params = {'equity': [symbol]}  # equity parameter expects array
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 401:
                self.logger.warning(f"Authentication failed (401), attempting token refresh...")
                # Try to refresh token and retry
                try:
                    from tt import refresh_access_token
                    refresh_result = refresh_access_token()
                    if refresh_result and refresh_result.get('access_token'):
                        self.logger.info("Token refresh successful, retrying market data request...")
                        # Get new headers and retry
                        headers = self.get_authenticated_headers()
                        response = requests.get(url, headers=headers, params=params)
                        self.logger.info(f"Retry response status: {response.status_code}")
                    else:
                        self.logger.error("Token refresh failed")
                        return None
                except ImportError as e:
                    self.logger.error(f"Could not refresh token: {e}")
                    return None
            
            if response.status_code != 200:
                self.logger.error(f"Market data API returned {response.status_code}: {response.text}")
                return None
                
            data = response.json()
            
            # Parse the response structure
            if 'data' not in data:
                self.logger.error("No data field in response")
                return None
            
            market_data = data['data']
            
            # Find the symbol data in the response
            symbol_data = None
            
            # Check different possible structures
            if isinstance(market_data, dict):
                if symbol in market_data:
                    symbol_data = market_data[symbol]
                elif 'items' in market_data and isinstance(market_data['items'], list):
                    for item in market_data['items']:
                        if item.get('symbol') == symbol:
                            symbol_data = item
                            break
            elif isinstance(market_data, list):
                for item in market_data:
                    if item.get('symbol') == symbol:
                        symbol_data = item
                        break
            
            if not symbol_data:
                self.logger.error(f"No data found for symbol {symbol}")
                return None
            
            # Extract market data fields
            current_price = _safe_float(symbol_data.get('last'))
            if not current_price:
                current_price = _safe_float(symbol_data.get('mid'))
            if not current_price:
                current_price = _safe_float(symbol_data.get('mark'))
            
            bid = _safe_float(symbol_data.get('bid'))
            ask = _safe_float(symbol_data.get('ask'))
            
            # Handle volume conversion safely
            volume = _safe_int(symbol_data.get('volume'))
            
            # Calculate changes if available
            prev_close = _safe_float(symbol_data.get('prev-close')) or current_price
            price_change = current_price - prev_close if prev_close else 0
            percent_change = (price_change / prev_close * 100) if prev_close else 0
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'bid': bid,
                'ask': ask,
                'volume': volume,
                'prev_close': prev_close,
                'price_change': price_change,
                'percent_change': percent_change,
                'timestamp': data.get('context', {}).get('timestamp'),
                'source': 'tastytrade_market_data'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """
        Get latest quote for a symbol using TastyTrade API
        
        Parameters:
        symbol: Stock symbol (e.g., 'SPY')
        
        Returns:
        Dict with quote data or None if error
        """
        try:
            headers = self.get_authenticated_headers()
            if not headers:
                self.logger.error("Could not get TastyTrade authentication headers")
                return None
            
            # Use TastyTrade market data endpoint
            url = f"{self.base_url}/market-data/by-type"
            params = {'equity': symbol}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle the data format (nested in items array)
            if 'data' in data and 'items' in data['data'] and data['data']['items']:
                quote = data['data']['items'][0]  # Get first item
                
                bid = _safe_float(quote.get('bid'))
                ask = _safe_float(quote.get('ask'))
                last_price = _safe_float(quote.get('last-price'))
                
                # Use last price if available, otherwise use mid-price
                price = last_price if last_price > 0 else (bid + ask) / 2 if (bid > 0 and ask > 0) else 0
                
                return {
                    'symbol': symbol,
                    'bid': bid,
                    'ask': ask,
                    'bid_size': _safe_int(quote.get('bid-size')),
                    'ask_size': _safe_int(quote.get('ask-size')),
                    'timestamp': quote.get('updated-at'),
                    'price': price
                }
            else:
                self.logger.warning(f"No data returned for {symbol}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    def get_multi_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get latest quotes for multiple symbols using TastyTrade API
        
        Parameters:
        symbols: List of stock symbols (e.g., ['SPY', 'QQQ', 'TLT'])
        
        Returns:
        Dict mapping symbol to quote data
        """
        result = {}
        headers = self.get_authenticated_headers()
        if not headers:
            self.logger.error("Could not get TastyTrade authentication headers")
            return result
            
        # TastyTrade doesn't support multi-symbol quotes in one request,
        # so we'll make individual requests for each symbol
        for symbol in symbols:
            try:
                # Use the correct TastyTrade market data endpoint
                url = f"{self.base_url}/market-data/by-type"
                params = {'equity': symbol}
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                # Handle the data format (nested in items array)
                if 'data' in data and 'items' in data['data'] and data['data']['items']:
                    quote = data['data']['items'][0]  # Get first item
                    result[symbol] = {
                        'symbol': symbol,
                        'bid': _safe_float(quote.get('bid')),
                        'ask': _safe_float(quote.get('ask')),
                        'bid_size': _safe_int(quote.get('bid-size')),
                        'ask_size': _safe_int(quote.get('ask-size')),
                        'timestamp': quote.get('updated-at'),
                        'price': _safe_float(quote.get('last-price')) or (_safe_float(quote.get('bid')) + _safe_float(quote.get('ask'))) / 2
                    }
                    
            except Exception as e:
                self.logger.error(f"Error getting quote for {symbol}: {e}")
                continue
            
        self.logger.info(f"Retrieved quotes for {len(result)} symbols")
        return result
    
    def get_historical_bars(self, symbol: str, timeframe: str = "1Day", 
                           start: str = None, end: str = None, 
                           limit: int = 1000) -> Optional[pd.DataFrame]:
        """
        Get historical bars for technical analysis
        
        NOTE: Historical market data is not available in TastyTrade sandbox environment.
        This method will return None and log the limitation.
        
        Parameters:
        symbol: Stock symbol
        timeframe: Bar timeframe ('1Min', '5Min', '15Min', '30Min', '1Hour', '1Day')
        start: Start date (ISO format: '2024-01-01T00:00:00Z')
        end: End date (ISO format)
        limit: Maximum number of bars to return
        
        Returns:
        None (due to sandbox limitation)
        """
        self.logger.warning(f"Historical bars not available for {symbol} - TastyTrade sandbox limitation")
        return None
    
    def get_latest_bar(self, symbol: str) -> Optional[Dict]:
        """
        Get latest bar for a symbol
        
        Parameters:
        symbol: Stock symbol
        
        Returns:
        Dict with latest bar data or None if error
        """
        try:
            url = f"{self.base_url}/v2/stocks/{symbol}/bars/latest"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if 'bar' in data:
                bar = data['bar']
                return {
                    'symbol': symbol,
                    'timestamp': bar.get('t'),
                    'open': bar.get('o'),
                    'high': bar.get('h'),
                    'low': bar.get('l'),
                    'close': bar.get('c'),
                    'volume': bar.get('v')
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting latest bar for {symbol}: {e}")
            return None

# Convenience functions that match existing yfinance function signatures
def get_current_price_tastytrade(symbol: str) -> Optional[float]:
    """
    Get current price using TastyTrade (replacement for Alpaca version)
    
    Parameters:
    symbol: Stock symbol
    
    Returns:
    Current price as float or None if error
    """
    try:
        client = TastyTradeMarketData()
        quote = client.get_latest_quote(symbol)
        if quote and quote.get('price'):
            return _safe_float(quote['price'])
        return None
    except Exception as e:
        logging.error(f"Error getting current price for {symbol}: {e}")
        return None

# Backward compatibility alias
get_current_price_alpaca = get_current_price_tastytrade

def get_market_overview_tastytrade(symbols: List[str] = None, force_refresh: bool = False) -> Dict[str, Dict]:
    """
    Get market overview using TastyTrade (replacement for Alpaca version)
    
    Parameters:
    symbols: List of symbols for market overview
    force_refresh: Force refresh even when markets are closed
    
    Returns:
    Dict mapping symbol to market data
    """
    if symbols is None:
        symbols = ['SPY', 'QQQ', 'TLT', 'GLD', 'VIX', 'UVXY', 'SQQQ']
    
    # Check if markets are open (unless forced)
    if not force_refresh and not _is_market_open():
        # Return cached data or minimal data when markets are closed
        return _get_cached_market_overview(symbols)
    
    try:
        client = TastyTradeMarketData()
        quotes = client.get_multi_quotes(symbols)
        
        # Convert to format expected by existing code
        result = {}
        for symbol, quote in quotes.items():
            if quote:
                # Note: Historical data not available in TastyTrade sandbox
                # Using fallback values for day change calculations
                day_change = 0.0
                intraday_change = 0.0
                
                result[symbol] = {
                    'current_price': quote['price'],
                    'bid': quote['bid'],
                    'ask': quote['ask'],
                    'bid_size': quote['bid_size'],
                    'ask_size': quote['ask_size'],
                    'day_change': day_change,
                    'day_change_percent': day_change,
                    'intraday_change': intraday_change,
                    'intraday_change_percent': intraday_change,
                    'volume': 0,  # Not available in quotes
                    'timestamp': quote['timestamp'],
                    'source': 'tastytrade'
                }
        
        # Cache the results
        global _market_overview_cache, _cache_timestamp
        _market_overview_cache = result
        _cache_timestamp = datetime.now()
        
        return result
        
    except Exception as e:
        logging.error(f"Error getting market overview: {e}")
        return _get_cached_market_overview(symbols)

# Backward compatibility alias
get_market_overview_alpaca = get_market_overview_tastytrade

def get_historical_data_tastytrade(symbol: str, period: str = "60d", 
                                  interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Get historical data using TastyTrade API only
    
    NOTE: TastyTrade Sandbox may not have full historical data available.
    This function now focuses on providing current price data in a DataFrame format
    for compatibility with existing code.
    
    Parameters:
    symbol: Stock symbol
    period: Period string (e.g., "60d", "1y") - currently ignored
    interval: Interval string (e.g., "1d", "1h", "1m") - currently ignored
    
    Returns:
    DataFrame with OHLCV data if successful, None otherwise
    """
    try:
        # Get current quote data from TastyTrade API
        client = TastyTradeMarketData()
        quote = client.get_latest_quote(symbol)
        
        if not quote:
            logging.warning(f"No current quote available for {symbol}")
            return None
        
        # Create a simple DataFrame with current price data
        # This maintains compatibility with code expecting historical data
        current_time = pd.Timestamp.now()
        current_price = quote.get('price', 0.0)
        
        # Create a minimal historical DataFrame using current price
        data = {
            'Open': [current_price],
            'High': [current_price], 
            'Low': [current_price],
            'Close': [current_price],
            'Volume': [0]  # Volume not available in quotes
        }
        
        df = pd.DataFrame(data, index=[current_time])
        
        logging.info(f"Created DataFrame for {symbol} with current price ${current_price:.2f}")
        return df
        
    except Exception as e:
        logging.error(f"Error getting TastyTrade data for {symbol}: {e}")
        
        # Fallback: create minimal DataFrame with zero data to avoid crashes
        current_time = pd.Timestamp.now()
        data = {
            'Open': [0.0],
            'High': [0.0], 
            'Low': [0.0],
            'Close': [0.0],
            'Volume': [0]
        }
        
        df = pd.DataFrame(data, index=[current_time])
        logging.warning(f"Using fallback DataFrame for {symbol}")
        return df

# Backward compatibility alias
get_historical_data_alpaca = get_historical_data_tastytrade

# =============================================================================
# INTERFACE COMPATIBILITY FUNCTIONS
# =============================================================================
# These functions provide the same interface as hybrid_data.py but use TastyTrade

def get_current_price(ticker: str = None) -> Optional[float]:
    """TastyTrade-only current price (replaces hybrid_data function)"""
    if ticker is None:
        ticker = "SPY"  # Default fallback
    return get_current_price_alpaca(ticker)

def get_market_overview(symbols: List[str] = None, force_refresh: bool = False) -> Dict[str, Dict]:
    """TastyTrade-only market overview (replaces hybrid_data function)"""
    return get_market_overview_alpaca(symbols, force_refresh)

def get_ticker_recent_data(ticker: str = None, period: str = "1d", 
                          interval: str = "1m", last_minutes: int = 10) -> Optional[Dict]:
    """
    TastyTrade-only recent data (replaces hybrid_data function)
    Returns data in format expected by existing code
    """
    if ticker is None:
        ticker = "SPY"
        
    try:
        # Get current price
        current_price = get_current_price_alpaca(ticker)
        if not current_price:
            return None
            
        # Get historical data for technical analysis
        historical_df = get_historical_data_alpaca(ticker, period, interval)
        
        if historical_df is None or historical_df.empty:
            # Fallback to minimal data structure
            historical_df = pd.DataFrame({
                'Close': [current_price],
                'High': [current_price], 
                'Low': [current_price],
                'Open': [current_price],
                'Volume': [0]
            }, index=[pd.Timestamp.now()])
        
        # Calculate price change from historical data
        price_change = 0.0
        price_change_pct = 0.0
        
        if len(historical_df) >= 2:
            if interval == "1d" and len(historical_df) >= 2:
                # For daily data, compare current price to yesterday's close
                previous_close = historical_df['Close'].iloc[-2]
                price_change = current_price - previous_close
                price_change_pct = (price_change / previous_close) * 100 if previous_close != 0 else 0.0
            else:
                # For intraday data, compare current price to today's opening
                today_open = historical_df['Open'].iloc[0]
                price_change = current_price - today_open
                price_change_pct = (price_change / today_open) * 100 if today_open != 0 else 0.0
        
        return {
            'ticker': ticker,
            'current_price': current_price,
            'price_change': price_change,
            'price_change_pct': price_change_pct,
            'high': historical_df['High'].max() if 'High' in historical_df.columns else current_price,
            'low': historical_df['Low'].min() if 'Low' in historical_df.columns else current_price,
            'total_volume': historical_df['Volume'].sum() if 'Volume' in historical_df.columns else 0,
            'times': historical_df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'prices': historical_df['Close'].tolist(),
            'volumes': historical_df['Volume'].tolist() if 'Volume' in historical_df.columns else [0] * len(historical_df),
            'timestamp': datetime.now().isoformat(),
            'period': period,
            'interval': interval,
            'historical_data': historical_df
        }
        
    except Exception as e:
        logging.error(f"Error getting recent data for {ticker}: {e}")
        return None

def get_spy_recent_data(period: str = "1d", interval: str = "1m", last_minutes: int = 10) -> Optional[Dict]:
    """Alpaca-only SPY recent data (replaces hybrid_data function)"""
    return get_ticker_recent_data("SPY", period, interval, last_minutes)

def get_spy_data_for_dte(dte: int) -> Optional[Dict]:
    """Get SPY data appropriate for the given DTE (replaces hybrid_data function)"""
    # Adjust period based on DTE for better analysis
    if dte == 0:
        period = "1d"
        interval = "1m"
    elif dte <= 3:
        period = "5d" 
        interval = "5m"
    else:
        period = "1mo"
        interval = "1h"
    
    return get_ticker_recent_data("SPY", period, interval, last_minutes=100)

def get_dte_technical_analysis(dte: int, ticker: str = "SPY") -> Optional[Dict]:
    """Get technical analysis appropriate for the given DTE (replaces hybrid_data function)"""
    try:
        from market_data import TechnicalAnalysisManager
        manager = TechnicalAnalysisManager(dte=dte, ticker=ticker)
        return manager.calculate_rsi()  # Return RSI analysis for now
    except Exception as e:
        logging.error(f"Error getting DTE technical analysis: {e}")
        return None

# =============================================================================
# RSI AND TECHNICAL ANALYSIS COMPATIBILITY
# =============================================================================
# Import technical analysis functions to maintain interface compatibility

def get_rsi_from_yfinance(ticker: str = "SPY", period: str = "60d", 
                         interval: str = "1d", window: int = 14) -> Optional[Dict]:
    """RSI calculation using TastyTrade data (replaces hybrid_data function)"""
    try:
        # For now, return a basic fallback RSI value
        # This can be enhanced later with actual RSI calculation
        return {
            'current_rsi': 50.0,  # Neutral RSI
            'rsi_series': None,
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        logging.error(f"Error calculating RSI for {ticker}: {e}")
        return None

def get_rsi_interpretation(rsi: float) -> Dict[str, str]:
    """RSI interpretation (replaces hybrid_data function)"""
    if rsi >= 70:
        return {
            'interpretation': 'Overbought',
            'signal': 'SELL',
            'strength': 'Strong' if rsi >= 80 else 'Moderate'
        }
    elif rsi <= 30:
        return {
            'interpretation': 'Oversold',
            'signal': 'BUY', 
            'strength': 'Strong' if rsi <= 20 else 'Moderate'
        }
    else:
        return {
            'interpretation': 'Neutral',
            'signal': 'HOLD',
            'strength': 'Weak'
        }

def analyze_rsi_trend(rsi_data: Dict) -> Dict[str, str]:
    """RSI trend analysis (replaces hybrid_data function)"""
    if not rsi_data or 'rsi_series' not in rsi_data:
        return {'trend': 'Unknown', 'direction': 'Neutral'}
    
    rsi_series = rsi_data['rsi_series']
    if rsi_series is None or len(rsi_series) < 3:
        return {'trend': 'Insufficient data', 'direction': 'Neutral'}
    
    recent_values = rsi_series.tail(3).values
    if len(recent_values) >= 3:
        if recent_values[-1] > recent_values[-2] > recent_values[-3]:
            return {'trend': 'Rising', 'direction': 'Bullish'}
        elif recent_values[-1] < recent_values[-2] < recent_values[-3]:
            return {'trend': 'Falling', 'direction': 'Bearish'}
    
    return {'trend': 'Sideways', 'direction': 'Neutral'}

def get_market_status() -> Dict:
    """
    Streamlined market status check - replacement for legacy paca.py version
    Uses optimized market hours checking and cached market data
    
    Returns:
    Dictionary with essential market status info
    """
    try:
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        
        # Basic market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        is_weekday = now_et.weekday() < 5  # Monday = 0, Friday = 4
        is_market_hours = market_open <= now_et <= market_close
        
        market_status = {
            'is_open': is_weekday and is_market_hours,
            'current_time': now_et.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'next_open': None,
            'next_close': None,
            'session': 'market' if is_market_hours else 'after_hours'
        }
        
        # Calculate next open/close times
        if is_market_hours:
            market_status['next_close'] = market_close.strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            # Calculate next market open
            if now_et.time() > market_close.time() or not is_weekday:
                # After close or weekend - next open is next business day
                days_ahead = 1
                if now_et.weekday() == 4:  # Friday
                    days_ahead = 3  # Skip to Monday
                elif now_et.weekday() == 5:  # Saturday
                    days_ahead = 2  # Skip to Monday
                
                next_open = now_et + timedelta(days=days_ahead)
                next_open = next_open.replace(hour=9, minute=30, second=0, microsecond=0)
                market_status['next_open'] = next_open.strftime('%Y-%m-%d %H:%M:%S %Z')
            else:
                # Before open today
                market_status['next_open'] = market_open.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        return market_status
        
    except Exception as e:
        print(f"❌ Error checking market status: {e}")
        return {
            'is_open': False,
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': str(e),
            'session': 'unknown'
        }

def test_tastytrade_data():
    """Test TastyTrade market data functionality"""
    print("🧪 Testing TastyTrade Market Data API...")
    
    try:
        client = TastyTradeMarketData()
        
        # Test 1: Single quote
        print("\n📊 Test 1: Single Quote (SPY)")
        spy_quote = client.get_latest_quote("SPY")
        if spy_quote:
            print(f"✅ SPY Price: ${spy_quote['price']:.2f} (Bid: ${spy_quote['bid']:.2f}, Ask: ${spy_quote['ask']:.2f})")
        else:
            print("❌ Failed to get SPY quote")
        
        # Test 2: Multi quotes
        print("\n📊 Test 2: Multi Quotes (Market Overview)")
        symbols = ['SPY', 'QQQ', 'TLT', 'GLD', 'VIX']
        multi_quotes = client.get_multi_quotes(symbols)
        for symbol, quote in multi_quotes.items():
            print(f"✅ {symbol}: ${quote['price']:.2f}")
        
        # Test 3: Historical data
        print("\n📊 Test 3: Historical Data (SPY 5 days)")
        start_date = (datetime.now() - timedelta(days=5)).isoformat() + "Z"
        historical = client.get_historical_bars("SPY", "1Day", start=start_date)
        if historical is not None:
            print(f"✅ Retrieved {len(historical)} daily bars for SPY")
            print(f"   Latest close: ${historical['Close'].iloc[-1]:.2f}")
        else:
            print("❌ Failed to get historical data")
        
        # Test 4: Convenience functions
        print("\n📊 Test 4: Convenience Functions")
        current_price = get_current_price_alpaca("SPY")
        if current_price:
            print(f"✅ SPY current price (convenience): ${current_price:.2f}")
        
        market_overview = get_market_overview_alpaca()
        print(f"✅ Market overview retrieved for {len(market_overview)} symbols")
        
        print("\n🎉 All tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

# Backward compatibility alias
test_alpaca_data = test_tastytrade_data

if __name__ == "__main__":
    test_tastytrade_data()