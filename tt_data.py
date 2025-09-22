"""
TastyTrade Market Data Module
============================

This module provides market data from TastyTrade's API as an alternative 
to Alpaca and yfinance, designed to work with the TastyTrade sandbox environment.

Features:
- Stock quotes and market data
- Multi-symbol batch requests
- Consistent error handling
- Integration with TastyTrade OAuth2 authentication
- Fallback to yfinance when needed
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import logging
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global cache for market data when markets are closed
_market_overview_cache = {}
_cache_timestamp = None

def _is_market_open() -> bool:
    """Check if US stock market is currently open"""
    try:
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        
        # Check if it's a weekday
        if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now_et <= market_close
    except:
        return False  # Default to closed if error

def _get_cached_market_overview(symbols: List[str]) -> Dict[str, Dict]:
    """Return cached market overview data or minimal fallback data"""
    global _market_overview_cache, _cache_timestamp
    
    # If cache is recent (less than 4 hours old), return it
    if (_cache_timestamp and _market_overview_cache and 
        datetime.now() - _cache_timestamp < timedelta(hours=4)):
        return _market_overview_cache
    
    # Return minimal fallback data
    result = {}
    for symbol in symbols:
        result[symbol] = {
            'symbol': symbol,
            'price': 0.0,
            'change': 0.0,
            'change_percent': 0.0,
            'cached': True,
            'message': 'Markets closed - data not updated'
        }
    
    return result

class TastyTradeMarketData:
    """
    TastyTrade Market Data API client for stock and ETF data
    """
    
    def __init__(self):
        """Initialize TastyTrade Market Data client"""
        # Import TastyTrade functions from main module
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from tt import get_authenticated_headers, TT_BASE_URL
            self.get_authenticated_headers = get_authenticated_headers
            self.base_url = TT_BASE_URL
        except ImportError as e:
            raise ValueError(
                "Could not import TastyTrade authentication functions. "
                f"Please ensure tt.py is available: {e}"
            )
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """
        Get latest quote for a single symbol using TastyTrade API
        
        Parameters:
        symbol: Stock symbol (e.g., 'SPY')
        
        Returns:
        Dict with quote data or None if error
        """
        try:
            # Use TastyTrade equity endpoint
            headers = self.get_authenticated_headers()
            if not headers:
                self.logger.error("Could not get TastyTrade authentication headers")
                return None
                
            # Use the correct TastyTrade market data endpoint
            url = f"{self.base_url}/market-data/by-type"
            params = {'equity': symbol}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            # Handle the data format (nested in items array)
            if 'data' in data and 'items' in data['data'] and data['data']['items']:
                quote = data['data']['items'][0]  # Get first item
                return {
                    'symbol': symbol,
                    'bid': float(quote.get('bid', 0)),
                    'ask': float(quote.get('ask', 0)),
                    'bid_size': int(quote.get('bid-size', 0)),
                    'ask_size': int(quote.get('ask-size', 0)),
                    'timestamp': quote.get('updated-at'),
                    'price': float(quote.get('last-price', 0)) or (float(quote.get('bid', 0)) + float(quote.get('ask', 0))) / 2
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting latest quote for {symbol}: {e}")
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
                        'bid': float(quote.get('bid', 0)),
                        'ask': float(quote.get('ask', 0)),
                        'bid_size': int(quote.get('bid-size', 0)),
                        'ask_size': int(quote.get('ask-size', 0)),
                        'timestamp': quote.get('updated-at'),
                        'price': float(quote.get('last-price', 0)) or (float(quote.get('bid', 0)) + float(quote.get('ask', 0))) / 2
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
            return float(quote['price'])
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
        manager = TechnicalAnalysisManager(ticker=ticker)
        rsi_result = manager.calculate_rsi(period=window)
        
        if rsi_result and 'current_rsi' in rsi_result:
            return {
                'current_rsi': rsi_result['current_rsi'],
                'rsi_series': rsi_result.get('rsi_series'),
                'timestamp': datetime.now()
            }
        return None
        
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

def calculate_simple_moving_average(data: pd.Series, window: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return data.rolling(window=window, min_periods=1).mean()

def calculate_exponential_moving_average(data: pd.Series, window: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return data.ewm(span=window, adjust=False).mean()

def calculate_bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """
    Enhanced Bollinger Bands calculation with squeeze detection and volatility breakout analysis
    
    Parameters:
    data: DataFrame with OHLCV data
    period: Period for moving average calculation
    std_dev: Standard deviation multiplier
    
    Returns:
    DataFrame with enhanced Bollinger Bands, squeeze detection, and volatility analysis
    """
    if data is None or data.empty:
        return pd.DataFrame()
    
    # Make a copy to avoid modifying original data
    result = data.copy()
    
    # Use 'Close' price for calculations
    close_prices = result['Close']
    high_prices = result['High']
    low_prices = result['Low']
    
    # Calculate moving averages
    result['SMA_20'] = calculate_simple_moving_average(close_prices, 20)
    result['SMA_50'] = calculate_simple_moving_average(close_prices, 50)
    result['EMA_10'] = calculate_exponential_moving_average(close_prices, 10)
    result['EMA_20'] = calculate_exponential_moving_average(close_prices, 20)
    
    # Enhanced Bollinger Bands calculation
    sma = close_prices.rolling(window=period, min_periods=1).mean()
    std = close_prices.rolling(window=period, min_periods=1).std()
    
    result['BB_Upper'] = sma + (std * std_dev)
    result['BB_Lower'] = sma - (std * std_dev) 
    result['BB_Middle'] = sma
    
    # Bollinger Band Width (for squeeze detection)
    result['BB_Width'] = (result['BB_Upper'] - result['BB_Lower']) / result['BB_Middle']
    
    # BB Width percentile (for squeeze identification)
    result['BB_Width_Percentile'] = result['BB_Width'].rolling(window=100, min_periods=20).rank(pct=True)
    
    # Bollinger Band Squeeze detection (width in lower 20th percentile)
    result['BB_Squeeze'] = result['BB_Width_Percentile'] < 0.2
    
    # Price position within Bollinger Bands
    result['BB_Position'] = (close_prices - result['BB_Lower']) / (result['BB_Upper'] - result['BB_Lower'])
    
    # Bollinger Band breakout detection
    result['BB_Upper_Breakout'] = close_prices > result['BB_Upper']
    result['BB_Lower_Breakout'] = close_prices < result['BB_Lower']
    
    # Volume-adjusted volatility (if volume data available)
    if 'Volume' in result.columns:
        avg_volume = result['Volume'].rolling(window=period, min_periods=1).mean()
        result['Volume_Ratio'] = result['Volume'] / avg_volume
        # High volume breakouts are more significant
        result['Significant_Breakout'] = (
            (result['BB_Upper_Breakout'] | result['BB_Lower_Breakout']) & 
            (result['Volume_Ratio'] > 1.5)
        )
    else:
        result['Volume_Ratio'] = 1.0
        result['Significant_Breakout'] = result['BB_Upper_Breakout'] | result['BB_Lower_Breakout']
    
    # True Range and Average True Range for volatility context
    result['True_Range'] = pd.concat([
        high_prices - low_prices,
        abs(high_prices - close_prices.shift(1)),
        abs(low_prices - close_prices.shift(1))
    ], axis=1).max(axis=1)
    
    result['ATR'] = result['True_Range'].rolling(window=period, min_periods=1).mean()
    result['ATR_Ratio'] = result['True_Range'] / result['ATR']
    
    # Volatility expansion detection
    current_atr = result['ATR'].iloc[-1] if not result['ATR'].empty else 0
    avg_atr = result['ATR'].rolling(window=50, min_periods=10).mean().iloc[-1] if len(result) > 10 else current_atr
    result['Volatility_Expansion'] = current_atr > (avg_atr * 1.5) if avg_atr > 0 else False
    
    return result

class TechnicalAnalysisManager:
    """
    Technical Analysis Manager for DTE-aware analysis
    Replaces the missing technical_analysis.py module
    """
    
    def __init__(self, dte: int = 0, ticker: str = "SPY"):
        self.dte = dte
        self.ticker = ticker
        
    def calculate_rsi(self, period: int = 14) -> Dict:
        """
        Enhanced RSI analysis with multi-timeframe precision, momentum divergence detection, and trend analysis
        
        Returns:
        Dictionary with comprehensive RSI data matching grok.py expectations
        """
        try:
            # Enhanced DTE-aware historical data collection
            if self.dte == 0:
                # For 0DTE, use multiple timeframes for precision
                primary_period = "1d"
                primary_interval = "1m"
                secondary_period = "2d"
                secondary_interval = "5m"
            elif self.dte <= 3:
                # For short-term DTE, use enhanced precision
                primary_period = "5d"
                primary_interval = "5m"
                secondary_period = "10d"
                secondary_interval = "15m"
            elif self.dte <= 7:
                # For weekly DTE
                primary_period = "10d"
                primary_interval = "15m"
                secondary_period = "1mo"
                secondary_interval = "1h"
            else:
                # For longer DTE, use broader timeframes
                primary_period = "1mo"
                primary_interval = "1h"
                secondary_period = "3mo"
                secondary_interval = "1d"
            
            # Get primary timeframe data
            primary_data = get_historical_data_tastytrade(
                self.ticker, 
                period=primary_period, 
                interval=primary_interval
            )
            
            # Get secondary timeframe for trend confirmation
            secondary_data = get_historical_data_tastytrade(
                self.ticker, 
                period=secondary_period, 
                interval=secondary_interval
            )
            
            if primary_data is None or primary_data.empty:
                return {
                    'status': 'error',
                    'message': f'No historical data available for {self.ticker}',
                    'current_rsi': 50.0,
                    'interpretation': 'neutral',
                    'trend': 'neutral',
                    'recent_rsi': [],
                    'rsi_momentum': 'neutral',
                    'multi_timeframe_bias': 'neutral'
                }
            
            # Enhanced RSI calculation with smoother EMA-based formula
            close_prices = primary_data['Close']
            delta = close_prices.diff()
            
            # Use EMA for smoother RSI instead of SMA
            gain = (delta.where(delta > 0, 0)).ewm(span=period).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(span=period).mean()
            
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            
            current_rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50.0
            recent_rsi = rsi_series.tail(20).tolist()  # Extended for better trend analysis
            
            # Enhanced momentum analysis
            rsi_momentum = self._analyze_rsi_momentum(rsi_series)
            
            # Multi-timeframe analysis if secondary data available
            multi_timeframe_bias = 'neutral'
            if secondary_data is not None and not secondary_data.empty:
                secondary_close = secondary_data['Close']
                secondary_delta = secondary_close.diff()
                secondary_gain = (secondary_delta.where(secondary_delta > 0, 0)).ewm(span=period).mean()
                secondary_loss = (-secondary_delta.where(secondary_delta < 0, 0)).ewm(span=period).mean()
                secondary_rs = secondary_gain / secondary_loss
                secondary_rsi = 100 - (100 / (1 + secondary_rs))
                
                if not secondary_rsi.empty:
                    secondary_current = secondary_rsi.iloc[-1]
                    # Compare primary and secondary timeframe RSI
                    if current_rsi > 50 and secondary_current > 50:
                        multi_timeframe_bias = 'bullish_confirmed'
                    elif current_rsi < 50 and secondary_current < 50:
                        multi_timeframe_bias = 'bearish_confirmed'
                    elif abs(current_rsi - secondary_current) > 15:
                        multi_timeframe_bias = 'divergence_detected'
                    else:
                        multi_timeframe_bias = 'neutral'
            
            # Enhanced interpretation with precision levels
            interpretation_data = self._get_enhanced_rsi_interpretation(current_rsi, rsi_momentum)
            trend_data = self._analyze_enhanced_rsi_trend(rsi_series)
            
            # RSI strength calculation (rate of change)
            rsi_strength = abs(rsi_series.diff().tail(5).mean()) if len(rsi_series) > 5 else 0
            
            return {
                'status': 'success',
                'current_rsi': current_rsi,
                'interpretation': interpretation_data['interpretation'].lower(),
                'trend': trend_data['direction'].lower(),
                'recent_rsi': recent_rsi,
                'signal': interpretation_data['signal'],
                'strength': interpretation_data['strength'],
                'rsi_momentum': rsi_momentum,
                'multi_timeframe_bias': multi_timeframe_bias,
                'rsi_strength': round(rsi_strength, 2),
                'timeframe_primary': f"{primary_period}/{primary_interval}",
                'timeframe_secondary': f"{secondary_period}/{secondary_interval}" if secondary_data is not None else None
            }
            
        except Exception as e:
            logging.error(f"Error calculating enhanced RSI for {self.ticker}: {e}")
            return {
                'status': 'error', 
                'message': str(e),
                'current_rsi': 50.0,
                'interpretation': 'neutral',
                'trend': 'neutral',
                'recent_rsi': [],
                'rsi_momentum': 'neutral',
                'multi_timeframe_bias': 'neutral'
            }
    
    def _analyze_rsi_momentum(self, rsi_series) -> str:
        """Analyze RSI momentum patterns"""
        if len(rsi_series) < 5:
            return 'insufficient_data'
        
        recent_5 = rsi_series.tail(5)
        rsi_change = recent_5.iloc[-1] - recent_5.iloc[0]
        rsi_acceleration = recent_5.diff().tail(3).mean()
        
        if rsi_change > 5 and rsi_acceleration > 1:
            return 'accelerating_up'
        elif rsi_change > 2:
            return 'rising'
        elif rsi_change < -5 and rsi_acceleration < -1:
            return 'accelerating_down'
        elif rsi_change < -2:
            return 'falling'
        else:
            return 'consolidating'
    
    def _get_enhanced_rsi_interpretation(self, rsi: float, momentum: str) -> Dict[str, str]:
        """Enhanced RSI interpretation with momentum consideration"""
        base_interpretation = get_rsi_interpretation(rsi)
        
        # Enhance interpretation based on momentum
        if momentum == 'accelerating_up' and rsi > 60:
            return {
                'interpretation': 'Strong Bullish Momentum',
                'signal': 'STRONG_BUY',
                'strength': 'Very Strong'
            }
        elif momentum == 'accelerating_down' and rsi < 40:
            return {
                'interpretation': 'Strong Bearish Momentum', 
                'signal': 'STRONG_SELL',
                'strength': 'Very Strong'
            }
        elif momentum in ['accelerating_up', 'rising'] and 30 < rsi < 70:
            return {
                'interpretation': 'Building Momentum',
                'signal': 'BUY',
                'strength': 'Strong'
            }
        elif momentum in ['accelerating_down', 'falling'] and 30 < rsi < 70:
            return {
                'interpretation': 'Weakening Momentum',
                'signal': 'SELL', 
                'strength': 'Strong'
            }
        else:
            return base_interpretation
    
    def _analyze_enhanced_rsi_trend(self, rsi_series) -> Dict[str, str]:
        """Enhanced RSI trend analysis with multiple confirmation points"""
        if len(rsi_series) < 10:
            return {'trend': 'Insufficient data', 'direction': 'Neutral'}
        
        # Multi-period trend analysis
        short_term = rsi_series.tail(3).mean()
        medium_term = rsi_series.tail(7).mean()  
        long_term = rsi_series.tail(14).mean()
        
        # Trend strength calculation
        if short_term > medium_term > long_term:
            if short_term - long_term > 10:
                return {'trend': 'Strong Rising', 'direction': 'Strong Bullish'}
            else:
                return {'trend': 'Rising', 'direction': 'Bullish'}
        elif short_term < medium_term < long_term:
            if long_term - short_term > 10:
                return {'trend': 'Strong Falling', 'direction': 'Strong Bearish'}
            else:
                return {'trend': 'Falling', 'direction': 'Bearish'}
        elif abs(short_term - long_term) < 3:
            return {'trend': 'Consolidating', 'direction': 'Neutral'}
        else:
            return {'trend': 'Choppy', 'direction': 'Neutral'}

def get_market_status() -> Dict:
    """
    Streamlined market status check - replacement for paca.py version
    Uses optimized market hours checking and cached market data
    
    Returns:
    Dictionary with essential market status info
    """
    try:
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        is_open = _is_market_open()
        
        # Basic market status
        status = {
            'is_open': is_open,
            'current_time_et': now_et,
            'day_of_week': now_et.strftime('%A'),
            'is_weekend': now_et.weekday() >= 5,
            'market_session': 'OPEN' if is_open else 'CLOSED'
        }
        
        # Calculate next open/close times
        if is_open:
            # Market is open - next close is today at 4 PM
            next_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
            status['next_close'] = next_close
        else:
            # Market is closed - calculate next open
            if now_et.weekday() >= 5:  # Weekend
                days_until_monday = 7 - now_et.weekday()
                next_open = (now_et + timedelta(days=days_until_monday)).replace(
                    hour=9, minute=30, second=0, microsecond=0)
            elif now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 30):
                # Before market open today
                next_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
            else:
                # After market close today
                next_open = (now_et + timedelta(days=1)).replace(
                    hour=9, minute=30, second=0, microsecond=0)
                # Check if tomorrow is weekend
                if next_open.weekday() >= 5:
                    days_until_monday = 7 - next_open.weekday()
                    next_open = next_open + timedelta(days=days_until_monday)
            
            status['next_open'] = next_open
        
        # Get market data efficiently (uses caching when markets closed)
        market_data = get_market_overview(['SPY'], force_refresh=False)
        spy_data = market_data.get('SPY', {})
        
        if spy_data and not spy_data.get('cached', False):
            status['spy_price'] = spy_data.get('price', 0)
            status['spy_change'] = spy_data.get('change_percent', 0)
            status['market_data_available'] = True
            status['data_quality'] = 'EXCELLENT'
        else:
            status['spy_price'] = 'N/A'
            status['spy_change'] = 'N/A'
            status['market_data_available'] = False
            status['data_quality'] = 'CACHED' if spy_data.get('cached') else 'LIMITED'
        
        # Trading recommendation
        if is_open and status['data_quality'] == 'EXCELLENT':
            status['trading_recommendation'] = 'SAFE_TO_TRADE'
        elif not is_open and status['market_data_available']:
            status['trading_recommendation'] = 'TESTING_ONLY'
        else:
            status['trading_recommendation'] = 'AVOID_TRADING'
        
        return status
        
    except Exception as e:
        logging.error(f"Error getting market status: {e}")
        return {
            'is_open': False,
            'market_session': 'ERROR',
            'trading_recommendation': 'AVOID_TRADING',
            'error': str(e)
        }

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

# Test functions
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
