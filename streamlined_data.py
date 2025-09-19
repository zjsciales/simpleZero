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
        result['options_chain'] = get_options_chain_data_v2(ticker, dte, current_price)
        
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


def get_compact_options_chain(ticker: str) -> Dict[str, Any]:
    """
    Get compact options chain from TastyTrade API
    
    Returns:
    Dict with 'success' boolean and 'symbols' list
    """
    print(f"📋 Fetching compact options chain for {ticker}...")
    
    try:
        import requests
        from config import TT_SANDBOX_BASE_URL as TT_BASE_URL
        
        # Get authentication headers
        headers = get_authenticated_headers()
        if not headers:
            print("❌ No access token available")
            return {'success': False, 'symbols': []}
        
        url = f"{TT_BASE_URL}/option-chains/{ticker}/compact"
        
        print(f"🔗 Calling: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"🔍 Checking compact response structure...")
        print(f"🔍 Response keys available: {len(list(data.keys())) if isinstance(data, dict) else 0}")
        
        if 'data' in data and 'items' in data['data'] and data['data']['items']:
            raw_items = data['data']['items']
            print(f"📋 Found {len(raw_items) if raw_items else 0} option items")
            
            # Extract symbols from the data structure
            symbols = []
            if isinstance(raw_items, list):
                for item in raw_items:
                    if isinstance(item, dict):
                        # If it's a dict, look for symbols in the 'symbols' field
                        if 'symbols' in item and isinstance(item['symbols'], list):
                            symbols.extend(item['symbols'])
                        else:
                            print(f"⚠️ Unexpected item structure: {item}")
                    elif isinstance(item, str):
                        # If it's already a string symbol, use it directly
                        symbols.append(item)
                    else:
                        print(f"⚠️ Unknown item type: {type(item)} - {item}")
            
            print(f"✅ Extracted {len(symbols)} option symbols for {ticker}")
            print(f"🔍 Sample extracted symbols: {symbols[:5] if symbols else 'None'}")
            return {'success': True, 'symbols': symbols}
        else:
            print(f"❌ No option symbols found in response for {ticker}")
            return {'success': False, 'symbols': []}
            
    except Exception as e:
        print(f"❌ Error fetching compact options chain for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'symbols': []}


def parse_option_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Parse a TastyTrade option symbol into components
    
    Format: 'SPY   250919C00630000'
    - SPY: underlying
    - 250919: expiration date (YYMMDD)
    - C/P: call/put
    - 00630000: strike price * 1000
    """
    try:
        # Validate input type
        if not isinstance(symbol, str):
            print(f"⚠️ Expected string symbol, got {type(symbol)}: {symbol}")
            return None
            
        import re
        
        # Pattern for TastyTrade option symbols
        pattern = r'([A-Z]+)\s+(\d{6})([CP])(\d{8})'
        match = re.match(pattern, symbol)
        
        if not match:
            print(f"⚠️ Symbol doesn't match expected pattern: '{symbol}'")
            return None
            
        if len(symbol) < 18:
            print(f"⚠️ Symbol too short ({len(symbol)} chars): '{symbol}'")
            return None
            
        # Extract parts
        underlying = symbol[:3].strip()  # SPY
        date_part = symbol[6:12]  # YYMMDD
        option_type = symbol[12]  # C or P
        strike_part = symbol[13:21]  # Strike price * 1000
        
        # Parse expiration date (keep in compact format for filtering)
        year = 2000 + int(date_part[:2])
        month = int(date_part[2:4])
        day = int(date_part[4:6])
        expiration_full = f"{year:04d}-{month:02d}-{day:02d}"  # Full format for display
        expiration_compact = date_part  # Keep original YYMMDD format for filtering
        
        # Parse strike price (divide by 1000)
        strike_raw = int(strike_part)
        strike = strike_raw / 1000.0
        
        # Parse option type
        option_type_full = "call" if option_type.upper() == "C" else "put"
        
        return {
            'symbol': symbol,
            'underlying': underlying,
            'expiration': expiration_compact,  # Use compact format for filtering
            'expiration_full': expiration_full,  # Keep full format for display
            'option_type': option_type_full,
            'strike': strike,
            'strike_raw': strike_raw
        }
        
    except Exception as e:
        print(f"⚠️ Failed to parse option symbol {symbol}: {e}")
        return None


def filter_options_by_criteria(symbols: List[str], current_price: float, dte: int, strike_range_pct: float = None) -> Dict[str, List[str]]:
    """
    Filter option symbols based on expiration date and strike range
    
    Parameters:
    symbols: List of option symbols
    current_price: Current stock price
    dte: Days to expiration target
    strike_range_pct: Strike range percentage (default varies by DTE)
    
    Returns:
    Dict with 'calls' and 'puts' lists of filtered symbols
    """
    # Set default strike range based on DTE
    if strike_range_pct is None:
        if dte == 0:
            strike_range_pct = 0.08  # 8% for 0DTE (wider range)
        elif dte <= 2:
            strike_range_pct = 0.06  # 6% for 1-2DTE
        else:
            strike_range_pct = 0.05  # 5% for longer DTE
    
    print(f"🔍 Filtering options for {dte}DTE, price ${current_price:.2f}, range ±{strike_range_pct*100:.1f}%...")
    
    # Debug: Check what we're starting with
    print(f"🔍 Total symbols to filter: {len(symbols)}")
    if len(symbols) > 0:
        print(f"🔍 First few symbols: {symbols[:5]}")
    else:
        print("❌ No symbols provided to filter!")
        return {'calls': [], 'puts': [], 'target_date': '', 'strike_range': {'min': 0, 'max': 0}}
    
    # Calculate target expiration date (FIXED: use correct format)
    target_date = datetime.now() + timedelta(days=dte)
    target_str = target_date.strftime('%y%m%d')  # Fixed: was '%Y-%m-%d'
    
    print(f"🎯 Target expiration: {target_str} (for {target_date.strftime('%Y-%m-%d')})")
    
    # Calculate strike range (FIXED: use ± not *)
    strike_range = current_price * strike_range_pct
    min_strike = current_price - strike_range  # Fixed: was current_price * (1 - strike_range_pct)
    max_strike = current_price + strike_range  # Fixed: was current_price * (1 + strike_range_pct)
    
    print(f"🎯 Strike range: ${min_strike:.2f} - ${max_strike:.2f}")
    
    calls = []
    puts = []
    expiration_dates_seen = set()
    strikes_seen = set()
    
    for symbol in symbols:
        parsed = parse_option_symbol(symbol)
        if not parsed:
            continue
            
        # Track what we're seeing for debugging
        expiration_dates_seen.add(parsed['expiration'])
        strikes_seen.add(parsed['strike'])
        
        # Check expiration date
        if parsed['expiration'] != target_str:
            # Debug: show what we're comparing
            if len(calls) == 0 and len(puts) == 0:  # Only log for first few mismatches
                print(f"🔍 Date mismatch: found '{parsed['expiration']}' vs target '{target_str}' for symbol {symbol}")
            continue
            
        # Check strike range
        if not (min_strike <= parsed['strike'] <= max_strike):
            continue
            
        # Add to appropriate list
        if parsed['option_type'] == 'call':
            calls.append(symbol)
        else:
            puts.append(symbol)
    
    # Debug information
    print(f"🔍 Expiration dates found: {sorted(list(expiration_dates_seen))[:10]}")
    print(f"🔍 Strike prices found: {sorted(list(strikes_seen))[:10]}")
    print(f"✅ Filtered to {len(calls)} calls and {len(puts)} puts")
    
    return {
        'calls': calls,
        'puts': puts,
        'target_date': target_str,
        'strike_range': {'min': min_strike, 'max': max_strike}
    }


def get_options_market_data(option_symbols: List[str]) -> Dict[str, Dict]:
    """
    Get market data for multiple option symbols using individual API calls
    (matches the working dashboard pattern)
    """
    if not option_symbols:
        print("❌ No option symbols provided to get_options_market_data")
        return {}
    
    print(f"💰 Fetching market data for {len(option_symbols)} option symbols...")
    
    try:
        import requests
        from config import TT_SANDBOX_BASE_URL as TT_BASE_URL
        
        # Get authentication headers
        headers = get_authenticated_headers()
        if not headers:
            print(f"❌ Could not get authentication headers")
            return {}
        
        result = {}
        successful_calls = 0
        failed_calls = 0
        
        # Make individual calls for each symbol (matches working dashboard pattern)
        for i, symbol in enumerate(option_symbols):
            try:
                url = f"{TT_BASE_URL}/market-data/{symbol}"
                if i < 3:  # Show details for first 3 calls
                    print(f"🔗 Calling ({i+1}/{len(option_symbols)}): {url}")
                
                response = requests.get(url, headers=headers)
                
                if i < 3:  # Show response details for first 3 calls
                    print(f"📡 Response status: {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                if i < 3:  # Log status for first 3 calls
                    print(f"� Processing option {i+1}: Status {response.status_code}")
                    if 'data' in data and data['data']:
                        print(f"� Data structure contains expected fields")
                
                # Process the individual response
                if 'data' in data and data['data']:
                    item = data['data']
                    
                    # Debug: show what fields are available
                    if i < 2:
                        print(f"🔍 Available fields for {symbol}: {list(item.keys())}")
                        print(f"🔍 Volume field: {item.get('volume', 'NOT_FOUND')}")
                        print(f"🔍 Open Interest field: {item.get('open-interest', 'NOT_FOUND')}")
                    
                    result[symbol] = {
                        'symbol': symbol,
                        'bid': float(item.get('bid', 0)),
                        'ask': float(item.get('ask', 0)),
                        'last': float(item.get('last', 0)),
                        'bid_size': int(item.get('bid-size', 0)),
                        'ask_size': int(item.get('ask-size', 0)),
                        'volume': int(item.get('volume', 0)),
                        'open_interest': int(item.get('open-interest', 0)),
                        'mark': float(item.get('mark', 0)),
                        'timestamp': item.get('updated-at', datetime.now().isoformat())
                    }
                    successful_calls += 1
                    if i < 3:  # Show data for first 3 successful calls
                        print(f"✅ Got data for {symbol}: bid=${item.get('bid', 0)}, ask=${item.get('ask', 0)}")
                else:
                    failed_calls += 1
                    if i < 3:
                        print(f"⚠️ No data field in response for {symbol}")
                
            except requests.exceptions.HTTPError as e:
                failed_calls += 1
                if i < 3:
                    print(f"⚠️ HTTP error for {symbol}: {e}")
                continue
            except Exception as e:
                failed_calls += 1
                if i < 3:
                    print(f"⚠️ Failed to get data for {symbol}: {e}")
                continue
        
        print(f"✅ Market data results: {successful_calls} successful, {failed_calls} failed out of {len(option_symbols)} total")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching options market data: {e}")
        return {}


def get_options_chain_data_v2(ticker: str, dte: int, current_price: Optional[float] = None) -> Dict[str, Any]:
    """
    Get options chain data using new compact approach with market data lookup
    
    Parameters:
    ticker: Stock symbol
    dte: Days to expiration
    current_price: Current stock price (will fetch if not provided)
    
    Returns:
    Dict containing calls and puts with price and volume data
    """
    print(f"⚙️ Fetching {ticker} options chain for {dte}DTE using compact approach...")
    
    try:
        # Get current price if not provided
        if current_price is None:
            print(f"📈 Getting current price for {ticker}...")
            current_price = get_current_price(ticker)
            
        if not current_price:
            print(f"❌ Could not get current price for {ticker}")
            return {}
        
        print(f"📈 Current {ticker} price: ${current_price:.2f}")
        
        # Step 1: Get compact options chain (all symbols)
        print(f"📋 Step 1: Getting compact options chain...")
        compact_chain = get_compact_options_chain(ticker)
        if not compact_chain.get('success'):
            print(f"❌ Failed to get compact options chain for {ticker}")
            return {}
        
        all_symbols = compact_chain.get('symbols', [])
        if not all_symbols:
            print(f"❌ No option symbols found for {ticker}")
            return {}
        
        print(f"✅ Got {len(all_symbols)} total option symbols")
        print(f"🔍 Sample symbols: {all_symbols[:3] if all_symbols else 'None'}")
        
        # Debug: Let's see what format these symbols are in
        if all_symbols:
            for i, symbol in enumerate(all_symbols[:5]):
                parsed = parse_option_symbol(symbol)
                if parsed:
                    print(f"🔍 Symbol {i+1}: {symbol} -> {parsed['expiration']} {parsed['option_type']} ${parsed['strike']}")
                else:
                    print(f"❌ Could not parse symbol {i+1}: {symbol}")
        
        # Step 2: Filter symbols by DTE and strike range
        print(f"🔍 Step 2: Filtering symbols by {dte}DTE criteria...")
        print(f"🔍 About to call filter_options_by_criteria with:")
        print(f"   - {len(all_symbols)} symbols")
        print(f"   - current_price: ${current_price:.2f}")
        print(f"   - dte: {dte}")
        
        filtered_symbols = filter_options_by_criteria(all_symbols, current_price, dte)
        
        call_symbols = filtered_symbols['calls']
        put_symbols = filtered_symbols['puts']
        
        print(f"🔍 Filter results: {len(call_symbols)} calls, {len(put_symbols)} puts")
        
        if not call_symbols and not put_symbols:
            print(f"❌ No options found matching {dte}DTE criteria")
            return {}
        
        # Step 3: Get market data for filtered symbols
        print(f"💰 Step 3: Getting market data for {len(call_symbols + put_symbols)} symbols...")
        all_filtered_symbols = call_symbols + put_symbols
        market_data = get_options_market_data(all_filtered_symbols)
        
        print(f"💰 Market data retrieved for {len(market_data)} symbols")
        
        # Step 4: Organize data by calls/puts with parsed details
        print(f"📊 Step 4: Organizing final data...")
        calls = []
        puts = []
        
        for symbol in call_symbols:
            parsed = parse_option_symbol(symbol)
            if parsed and symbol in market_data:
                option_data = market_data[symbol].copy()
                option_data.update({
                    'strike': parsed['strike'],
                    'expiration': parsed['expiration_full'],
                    'option_type': parsed['option_type']
                })
                calls.append(option_data)
        
        for symbol in put_symbols:
            parsed = parse_option_symbol(symbol)
            if parsed and symbol in market_data:
                option_data = market_data[symbol].copy()
                option_data.update({
                    'strike': parsed['strike'],
                    'expiration': parsed['expiration_full'],
                    'option_type': parsed['option_type']
                })
                puts.append(option_data)
        
        total_options = len(calls) + len(puts)
        print(f"✅ Final result: {len(calls)} calls and {len(puts)} puts for {ticker} {dte}DTE")
        
        result = {
            'calls': calls,
            'puts': puts,
            'total_options': total_options,
            'current_price': current_price,
            'target_date': filtered_symbols.get('target_date'),
            'symbols_filtered': len(all_filtered_symbols),
            'total_symbols_available': len(all_symbols)
        }
        
        print(f"✅ Returning result with {total_options} total options")
        return result
        
    except Exception as e:
        print(f"❌ Error in get_options_chain_data_v2: {e}")
        import traceback
        traceback.print_exc()
        return {}


def get_authenticated_headers():
    """Get authentication headers for TastyTrade API calls"""
    try:
        from tt import get_oauth_token
        
        token = get_oauth_token()
        if not token:
            print("❌ No access token available from tt.py")
            return None
            
        print(f"✅ Got access token from tt.py: {token[:20]}...")
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    except Exception as e:
        print(f"❌ Error getting auth headers: {e}")
        return None


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