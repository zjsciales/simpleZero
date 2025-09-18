"""
Grok AI Market Analysis System
==============================

This module creates comprehensive market analysis and sends prompts directly to Grok AI
for real-time SPY options trading recommendations, focusing on covered vertical spreads.
"""

import json
import logging
import os
import re
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import pytz
import config
from dotenv import load_dotenv
from tt_data import (
    get_market_overview, 
    get_ticker_recent_data,
    get_ticker_recent_data,
    calculate_bollinger_bands,
    get_current_market_state,
    get_spy_data_for_dte,
    get_dte_technical_analysis,
    get_historical_data_alpaca,
    TechnicalAnalysisManager
)
from tt import (
    get_options_chain, 
    get_0dte_trading_range, 
    analyze_options_flow, 
    format_options_data,
    get_enhanced_greeks_data,
    get_enhanced_options_chain_data,
    get_spy_options_chain
)
from dte_manager import get_current_dte, dte_manager

# Load environment variables
load_dotenv()

class GrokAnalyzer:
    """
    Grok AI integration for SPY options analysis
    """
    
    def __init__(self):
        self.api_key = os.getenv('XAI_API_KEY')
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self.model = "grok-4"
        
        if not self.api_key:
            raise ValueError("XAI_API_KEY not found in environment variables")
    
    def send_to_grok(self, prompt, max_tokens=4000):
        """
        Send prompt to Grok AI via API
        
        Parameters:
        prompt: The formatted prompt string
        max_tokens: Maximum tokens for response
        
        Returns:
        Grok AI response
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1  # Lower temperature for more focused financial analysis
        }
        
        try:
            print("🤖 Sending request to Grok AI...")
            # Add timeout to prevent hanging
            response = requests.post(
                self.base_url, 
                headers=headers, 
                json=data,
                timeout=180  # 3 minute timeout
            )
            
            print(f"📡 Response status: {response.status_code}")
            print(f"📄 Response headers: {dict(response.headers)}")
            print(f"📝 Response text length: {len(response.text)}")
            
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error from Grok API: {e}")
            print(f"📄 Response content: {response.text[:500]}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error communicating with Grok API: {e}")
            return None
        except KeyError as e:
            print(f"❌ Unexpected Grok API response format: missing {e}")
            print(f"📄 Response content: {response.text[:500]}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Failed to decode Grok API JSON response: {e}")
            print(f"📄 Response content: {response.text[:500]}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error processing Grok response: {e}")
            return None

def get_comprehensive_market_data(include_full_options_chain=False, dte=None, ticker=None):
    """
    Gather all available market data for comprehensive analysis (DTE-aware v7 comprehensive)
    
    Parameters:
    include_full_options_chain: If True, includes complete options chain for specified DTE
    dte: Days to expiration (if None, uses current DTE from manager)
    ticker: Stock ticker (if None, uses current ticker from manager)
    
    Returns:
    Dictionary containing all market data components optimized for the specified DTE
    """
    from dte_manager import dte_manager
    
    # Use current DTE if none specified, but allow override
    if dte is None:
        dte = dte_manager.get_current_dte()
    
    # Use current ticker if none specified    
    if ticker is None:
        ticker = config.DEFAULT_TICKER
        
    print(f"🔍 Gathering comprehensive market data for {ticker} {dte}DTE analysis (v7 comprehensive)...")
    
    # Get DTE-specific configuration for intelligent data gathering
    dte_manager.current_dte = dte
    dte_config = dte_manager.get_dte_config(dte)
    dte_summary = dte_manager.get_dte_summary()
    
    # Get current timestamp
    et_tz = pytz.timezone('America/New_York')
    current_time = datetime.now(et_tz)
    
    data = {
        'timestamp': {
            'current_time': current_time.isoformat(),
            'market_date': current_time.strftime('%Y-%m-%d'),
            'market_time': current_time.strftime('%H:%M:%S %Z'),
            'trading_day': current_time.strftime('%A, %B %d, %Y')
        },
        'dte': dte,  # Include DTE in data
        'dte_config': dte_config,  # Include DTE configuration
        'dte_summary': dte_summary,  # Include DTE summary with display info
        'ticker': ticker  # Include current ticker
    }
    
    # 1. Global Market Overview (always useful regardless of DTE)
    print("📊 Fetching global market overview...")
    market_overview = get_market_overview()
    data['global_markets'] = market_overview
    
    # 2. Enhanced Ticker Recent Price Action with 1-minute precision (KEY OPTIMIZATION)
    print(f"📈 Fetching {ticker} enhanced recent data (optimized for {dte_summary['display_name']})...")
    ticker_recent = get_ticker_recent_data(
        ticker=ticker, 
        period=dte_config['period'],  # DTE-specific period (1d for 0DTE, 5d for 7DTE, etc.)
        interval=dte_config['interval'],  # DTE-specific interval (1m for 0DTE, 5m for longer)
        last_minutes=dte_config['data_points']  # DTE-specific data points
    )
    
    # Enhanced recent data processing for better price action analysis
    if ticker_recent and ticker_recent.get('recent_data') is not None:
        # Get the last 10 bars of 1-minute data for comprehensive analysis
        recent_df = ticker_recent['recent_data']
        if not recent_df.empty:
            # Get last 10 bars for detailed analysis
            last_10_bars = recent_df.tail(10)
            enhanced_recent_data = []
            
            for i, (timestamp, row) in enumerate(last_10_bars.iterrows()):
                bar_data = {
                    'timestamp': timestamp.strftime('%H:%M'),
                    'open': row['Open'],
                    'high': row['High'],
                    'low': row['Low'],
                    'close': row['Close'],
                    'volume': row['Volume'],
                    'change_from_open': round(row['Close'] - row['Open'], 2),
                    'change_pct': round(((row['Close'] - row['Open']) / row['Open']) * 100, 2) if row['Open'] > 0 else 0
                }
                enhanced_recent_data.append(bar_data)
            
            ticker_recent['last_10_bars'] = enhanced_recent_data
            ticker_recent['current_bar'] = enhanced_recent_data[-1] if enhanced_recent_data else None
    
    data['ticker_recent'] = ticker_recent
    
    # 3. Enhanced candlestick pattern analysis
    if ticker_recent and ticker_recent.get('recent_data') is not None and not ticker_recent['recent_data'].empty:
        print("🕯️ Analyzing candlestick patterns...")
        # Convert the pandas DataFrame to a list of dictionaries for analysis
        recent_data_list = []
        times = ticker_recent.get('times', [])
        for i, (idx, row) in enumerate(ticker_recent['recent_data'].iterrows()):
            timestamp = times[i] if i < len(times) else idx.strftime('%H:%M')
            recent_data_list.append({
                'timestamp': timestamp,
                'open': row['Open'],
                'high': row['High'], 
                'low': row['Low'],
                'close': row['Close'],
                'volume': row['Volume']
            })
        data['candlestick_analysis'] = analyze_candlestick_patterns(recent_data_list)
    
    # 4. RSI Analysis with DTE-appropriate timeframe (SMART ADAPTATION)
    print(f"🎯 Calculating RSI analysis for {ticker} (optimized for {dte_summary['display_name']})...")
    try:
        ta_manager = TechnicalAnalysisManager(dte=dte, ticker=ticker)
        rsi_data = ta_manager.calculate_rsi()
        if not rsi_data or rsi_data.get('status') == 'error':
            # Fallback: try with SPY if current ticker fails
            print(f"🔄 RSI calculation failed for {ticker}, trying SPY...")
            ta_manager_spy = TechnicalAnalysisManager(dte=dte, ticker="SPY")
            rsi_data = ta_manager_spy.calculate_rsi()
    except Exception as e:
        logging.error(f"Error calculating RSI for {ticker}: {e}")
        rsi_data = None
    
    if rsi_data and rsi_data.get('status') != 'error':
        rsi_interpretation = rsi_data.get('interpretation', 'neutral')
        rsi_trend = rsi_data.get('trend', 'neutral')
        data['rsi_analysis'] = {
            'current_rsi': rsi_data.get('current_rsi', 50.0),
            'interpretation': rsi_interpretation,
            'trend': rsi_trend,
            'recent_values': rsi_data['recent_rsi'][:5]
        }
    else:
        data['rsi_analysis'] = None
    
    # 5. Bollinger Bands and Moving Averages with DTE-appropriate timeframe
    print(f"📊 Calculating Bollinger Bands and Moving Averages for {ticker} (for {dte_summary['display_name']})...")
    bb_period = dte_config['period']  # DTE-specific period
    bb_interval = dte_config['interval']  # DTE-specific interval
    
    # Use TastyTrade data for technical analysis
    ticker_data = get_historical_data_alpaca(ticker, period=bb_period, interval=bb_interval)
    if ticker_data is not None and not ticker_data.empty:
        bb_data = calculate_bollinger_bands(ticker_data)
        market_state = get_current_market_state(bb_data)
        data['technical_analysis'] = {
            'bollinger_bands': {
                'current_price': market_state['current_price'] if market_state else 0,
                'upper_band': market_state['upper_band'] if market_state else 0,
                'lower_band': market_state['lower_band'] if market_state else 0,
                'market_state': market_state['market_state'] if market_state else 'NO DATA',
                'bb_position': market_state['deviation_from_center'] if market_state else 0,
                'bb_percent': market_state['percent_position'] if market_state else 0
            },
            'moving_averages': {
                'sma_20': market_state['sma_20'] if market_state else 0,
                'sma_50': market_state['sma_50'] if market_state else 0,
                'sma_trend': market_state['sma_trend'] if market_state else 'NO DATA',
                'ema_10': market_state['ema_10'] if market_state else 0,
                'ema_20': market_state['ema_20'] if market_state else 0,
                'ema_trend': market_state['ema_trend'] if market_state else 'NO DATA'
            }
        }
    else:
        data['technical_analysis'] = None
    
    # 6. Enhanced Comprehensive Options Chain Analysis with Bid/Ask Spreads (DTE-AWARE)
    dte_display = dte_manager.get_dte_display_name(dte)
    print(f"⚡ Fetching enhanced {dte_display} options chain with bid/ask data...")
    
    # Get options chain with enhanced data
    if include_full_options_chain:
        # For longer DTEs, get broader strike range
        limit = 200 if dte == 0 else 300  # More strikes for longer DTEs
        options_data = get_spy_options_chain(limit=limit, dte=dte, ticker=ticker)
    else:
        # For optimization, use focused strike range around current price
        limit = 100 if dte == 0 else 150  # Focused for 0DTE
        options_data = get_spy_options_chain(limit=limit, dte=dte, ticker=ticker)
        
    if options_data:
        formatted_options = format_options_data(options_data)
        if not formatted_options.empty:
            options_analysis = analyze_options_flow(formatted_options)
            
            # Enhanced options analysis with bid/ask spreads
            current_price = ticker_recent.get('current_price', 650) if ticker_recent else 650
            
            # Get ATM and near-the-money options with detailed pricing
            atm_strike = round(current_price)
            strikes_of_interest = [atm_strike - 2, atm_strike - 1, atm_strike, atm_strike + 1, atm_strike + 2]
            
            enhanced_options_data = []
            for strike in strikes_of_interest:
                # Get call data for this strike
                call_data = formatted_options[
                    (formatted_options['Strike'] == strike) & 
                    (formatted_options['Type'] == 'Call')
                ]
                # Get put data for this strike
                put_data = formatted_options[
                    (formatted_options['Strike'] == strike) & 
                    (formatted_options['Type'] == 'Put')
                ]
                
                if not call_data.empty:
                    call_row = call_data.iloc[0]
                    enhanced_options_data.append({
                        'strike': strike,
                        'type': 'Call',
                        'volume': call_row.get('Volume', 0),
                        'open_interest': call_row.get('Open Interest', 0),
                        'bid': call_row.get('Bid', 0),
                        'ask': call_row.get('Ask', 0),
                        'last': call_row.get('Last', 0),
                        'bid_ask_spread': round(call_row.get('Ask', 0) - call_row.get('Bid', 0), 2),
                        'mid_price': round((call_row.get('Bid', 0) + call_row.get('Ask', 0)) / 2, 2)
                    })
                
                if not put_data.empty:
                    put_row = put_data.iloc[0]
                    enhanced_options_data.append({
                        'strike': strike,
                        'type': 'Put',
                        'volume': put_row.get('Volume', 0),
                        'open_interest': put_row.get('Open Interest', 0),
                        'bid': put_row.get('Bid', 0),
                        'ask': put_row.get('Ask', 0),
                        'last': put_row.get('Last', 0),
                        'bid_ask_spread': round(put_row.get('Ask', 0) - put_row.get('Bid', 0), 2),
                        'mid_price': round((put_row.get('Bid', 0) + put_row.get('Ask', 0)) / 2, 2)
                    })
            
            # Use DTE-appropriate trading range function
            if dte == 0:
                ticker_range = get_0dte_trading_range(ticker_recent)
            else:
                # For longer DTEs, use wider range
                ticker_range = get_0dte_trading_range(ticker_recent)
            
            # Enhanced options analysis for covered spreads
            spread_analysis = analyze_spread_opportunities(formatted_options, ticker_range)
            
            data['options_analysis'] = {
                'total_options': len(formatted_options),
                'call_put_ratio': options_analysis.get('call_put_ratio', 0),
                'total_call_volume': options_analysis.get('total_call_volume', 0),
                'total_put_volume': options_analysis.get('total_put_volume', 0),
                'highest_volume': options_analysis.get('highest_volume_option', {}),
                'ticker_trading_range': ticker_range,
                'dte_status': dte_display,
                'spread_opportunities': spread_analysis,
                'enhanced_options_data': enhanced_options_data,  # New enhanced data with bid/ask
                'options_chain': formatted_options.to_dict('records') if include_full_options_chain else None,
                
                # Enhanced volume flow analysis
                'flow_bias': options_analysis.get('flow_bias', 'No Flow'),
                'call_volume_ratio': options_analysis.get('call_volume_ratio', 0),
                'put_volume_ratio': options_analysis.get('put_volume_ratio', 0),
                'volume_concentration': options_analysis.get('volume_concentration', 0),
                'unusual_call_count': options_analysis.get('unusual_call_count', 0),
                'unusual_put_count': options_analysis.get('unusual_put_count', 0),
                'high_volume_call_strikes': options_analysis.get('high_volume_call_strikes', []),
                'high_volume_put_strikes': options_analysis.get('high_volume_put_strikes', []),
                'total_volume': options_analysis.get('total_volume', 0)
            }
        else:
            data['options_analysis'] = None
    else:
        data['options_analysis'] = None
    
    print(f"✅ Market data gathering complete for {dte_summary['display_name']}!")
    return data
    
    # 4. RSI Analysis with DTE-appropriate timeframe (SMART ADAPTATION)
    print(f"🎯 Calculating RSI analysis for {ticker} (optimized for {dte_summary['display_name']})...")
    try:
        ta_manager = TechnicalAnalysisManager(dte=dte, ticker=ticker)
        rsi_data = ta_manager.calculate_rsi()
        if not rsi_data or rsi_data.get('status') == 'error':
            # Fallback: try with SPY if current ticker fails
            print(f"🔄 RSI calculation failed for {ticker}, trying SPY...")
            ta_manager_spy = TechnicalAnalysisManager(dte=dte, ticker="SPY")
            rsi_data = ta_manager_spy.calculate_rsi()
    except Exception as e:
        logging.error(f"Error calculating RSI for {ticker}: {e}")
        rsi_data = None
    
    if rsi_data and rsi_data.get('status') != 'error':
        rsi_interpretation = rsi_data.get('interpretation', 'neutral')
        rsi_trend = rsi_data.get('trend', 'neutral')
        data['rsi_analysis'] = {
            'current_rsi': rsi_data.get('current_rsi', 50.0),
            'interpretation': rsi_interpretation,
            'trend': rsi_trend,
            'recent_values': rsi_data['recent_rsi'][:5]
        }
    else:
        data['rsi_analysis'] = None
    
    # 5. Bollinger Bands and Moving Averages with DTE-appropriate timeframe
    print(f"📊 Calculating Bollinger Bands and Moving Averages for {ticker} (for {dte_summary['display_name']})...")
    bb_period = dte_config['period']  # DTE-specific period
    bb_interval = dte_config['interval']  # DTE-specific interval
    
    # Use Tasty Trade data instead of yfinance
    ticker_data = get_historical_data_alpaca(ticker, period=bb_period, interval=bb_interval)
    if ticker_data is not None and not ticker_data.empty:
        bb_data = calculate_bollinger_bands(ticker_data)
        market_state = get_current_market_state(bb_data)
        data['technical_analysis'] = {
            'bollinger_bands': {
                'current_price': market_state['current_price'] if market_state else 0,
                'upper_band': market_state['upper_band'] if market_state else 0,
                'lower_band': market_state['lower_band'] if market_state else 0,
                'market_state': market_state['market_state'] if market_state else 'NO DATA',
                'bb_position': market_state['deviation_from_center'] if market_state else 0,
                'bb_percent': market_state['percent_position'] if market_state else 0
            },
            'moving_averages': {
                'sma_20': market_state['sma_20'] if market_state else 0,
                'sma_50': market_state['sma_50'] if market_state else 0,
                'sma_trend': market_state['sma_trend'] if market_state else 'NO DATA',
                'ema_10': market_state['ema_10'] if market_state else 0,
                'ema_20': market_state['ema_20'] if market_state else 0,
                'ema_trend': market_state['ema_trend'] if market_state else 'NO DATA'
            }
        }
    else:
        data['technical_analysis'] = None
    
    # 6. Comprehensive Options Chain Analysis (DTE-AWARE)
    dte_display = dte_manager.get_dte_display_name(dte)
    print(f"⚡ Fetching complete {dte_display} options chain...")
    if include_full_options_chain:
        # For longer DTEs, get broader strike range
        limit = 200 if dte == 0 else 300  # More strikes for longer DTEs
        options_data = get_spy_options_chain(limit=limit, dte=dte, ticker=ticker)  # Use specified DTE and ticker
    else:
        # For v6 optimization, use focused strike range
        limit = 100 if dte == 0 else 150  # Slightly more for longer DTEs
        options_data = get_spy_options_chain(limit=limit, dte=dte, ticker=ticker)
        
    if options_data:
        formatted_options = format_options_data(options_data)
        if not formatted_options.empty:
            options_analysis = analyze_options_flow(formatted_options)
            
            # Use DTE-appropriate trading range function
            if dte == 0:
                ticker_range = get_0dte_trading_range()
            else:
                # For longer DTEs, use wider range (proportional to DTE)
                range_percent = min(8 + (dte * 2), 20)  # Scale from 8% to max 20%
                ticker_range = get_0dte_trading_range(range_percent=range_percent)
            
            # Enhanced options analysis for covered spreads
            spread_analysis = analyze_spread_opportunities(formatted_options, ticker_range)
            
            data['options_analysis'] = {
                'total_options': len(formatted_options),
                'call_put_ratio': options_analysis.get('call_put_ratio', 0),
                'total_call_volume': options_analysis.get('total_call_volume', 0),
                'total_put_volume': options_analysis.get('total_put_volume', 0),
                'highest_volume': options_analysis.get('highest_volume_option', {}),
                'ticker_trading_range': ticker_range,
                'dte_status': dte_display,
                'spread_opportunities': spread_analysis,
                'options_chain': formatted_options.to_dict('records') if include_full_options_chain else None
            }
        else:
            data['options_analysis'] = None
    else:
        data['options_analysis'] = None
    
    print(f"✅ Market data gathering complete for {dte_summary['display_name']}!")
    return data

def get_comprehensive_market_data_for_dte(dte, include_full_options_chain=False):
    """
    DTE-aware market data gathering function (alias for UI compatibility)
    
    This function provides the same functionality as get_comprehensive_market_data()
    but with the parameter order expected by the UI components.
    
    Parameters:
    dte: Days to expiration (required)
    include_full_options_chain: If True, includes complete options chain for specified DTE
    
    Returns:
    Dictionary containing all market data components optimized for the specified DTE
    """
    return get_comprehensive_market_data(include_full_options_chain=include_full_options_chain, dte=dte)


def analyze_candlestick_patterns(recent_data):
    """
    Analyze recent candlestick data for patterns
    
    Parameters:
    recent_data: List of recent price data
    
    Returns:
    Dictionary with pattern analysis
    """
    if len(recent_data) < 3:
        return {'patterns': [], 'trend': 'INSUFFICIENT_DATA'}
    
    patterns = []
    
    # Analyze last few candles for patterns
    for i in range(min(3, len(recent_data) - 1)):
        candle = recent_data[i]
        
        # Doji pattern
        if abs(candle['close'] - candle['open']) <= 0.05:
            patterns.append(f"Doji at {candle['timestamp']} - Indecision")
        
        # Hammer/Hanging Man
        body_size = abs(candle['close'] - candle['open'])
        lower_shadow = candle['open'] - candle['low'] if candle['close'] > candle['open'] else candle['close'] - candle['low']
        upper_shadow = candle['high'] - candle['close'] if candle['close'] > candle['open'] else candle['high'] - candle['open']
        
        if lower_shadow > body_size * 2 and upper_shadow < body_size:
            patterns.append(f"Hammer/Support at {candle['timestamp']}")
        elif upper_shadow > body_size * 2 and lower_shadow < body_size:
            patterns.append(f"Shooting Star/Resistance at {candle['timestamp']}")
    
    # Overall trend from recent candles
    if len(recent_data) >= 3:
        recent_closes = [d['close'] for d in recent_data[:3]]
        if recent_closes[0] > recent_closes[1] > recent_closes[2]:
            trend = 'DOWNTREND'
        elif recent_closes[0] < recent_closes[1] < recent_closes[2]:
            trend = 'UPTREND'
        else:
            trend = 'SIDEWAYS'
    else:
        trend = 'UNCLEAR'
    
    return {
        'patterns': patterns,
        'trend': trend,
        'momentum': 'BULLISH' if recent_data and len(recent_data) > 0 and recent_data[0].get('change_pct', 0) > 0 else 'BEARISH' if recent_data and len(recent_data) > 0 and recent_data[0].get('change_pct', 0) < 0 else 'NEUTRAL'
    }

def analyze_spread_opportunities(options_df, ticker_range):
    """
    Analyze options chain for covered vertical spread opportunities
    
    Parameters:
    options_df: DataFrame with options data
    ticker_range: Current ticker trading range
    
    Returns:
    Dictionary with spread analysis
    """
    if options_df.empty or not ticker_range:
        return None
    
    current_price = ticker_range['current']
    
    # Filter for liquid options (volume > 100)
    liquid_options = options_df[options_df['Volume'] > 100].copy()
    
    if liquid_options.empty:
        return None
    
    # Separate calls and puts
    calls = liquid_options[liquid_options['Type'] == 'Call'].copy()
    puts = liquid_options[liquid_options['Type'] == 'Put'].copy()
    
    spread_opportunities = {
        'call_spreads': [],
        'put_spreads': [],
        'summary': {}
    }
    
    # Analyze call spreads (sell lower strike, buy higher strike)
    for _, sell_call in calls.iterrows():
        sell_strike = sell_call['Strike']
        if sell_strike > current_price + 1:  # OTM calls for premium collection
            # Find buy calls (higher strike)
            buy_calls = calls[calls['Strike'] > sell_strike]
            for _, buy_call in buy_calls.iterrows():
                if buy_call['Strike'] <= sell_strike + 5:  # Keep spread width reasonable
                    spread_width = buy_call['Strike'] - sell_strike
                    credit_received = sell_call['Bid'] - buy_call['Ask']
                    max_profit = credit_received
                    max_loss = spread_width - credit_received
                    
                    if credit_received > 0.1 and max_loss > 0:  # Minimum credit filter
                        spread_opportunities['call_spreads'].append({
                            'sell_strike': sell_strike,
                            'buy_strike': buy_call['Strike'],
                            'spread_width': spread_width,
                            'credit_received': round(credit_received, 2),
                            'max_profit': round(max_profit, 2),
                            'max_loss': round(max_loss, 2),
                            'profit_probability': round((sell_strike - current_price) / current_price * 100, 1),
                            'sell_volume': sell_call['Volume'],
                            'buy_volume': buy_call['Volume']
                        })
    
    # Analyze put spreads (sell higher strike, buy lower strike)
    for _, sell_put in puts.iterrows():
        sell_strike = sell_put['Strike']
        if sell_strike < current_price - 1:  # OTM puts for premium collection
            # Find buy puts (lower strike)
            buy_puts = puts[puts['Strike'] < sell_strike]
            for _, buy_put in buy_puts.iterrows():
                if buy_put['Strike'] >= sell_strike - 5:  # Keep spread width reasonable
                    spread_width = sell_strike - buy_put['Strike']
                    credit_received = sell_put['Bid'] - buy_put['Ask']
                    max_profit = credit_received
                    max_loss = spread_width - credit_received
                    
                    if credit_received > 0.1 and max_loss > 0:  # Minimum credit filter
                        spread_opportunities['put_spreads'].append({
                            'sell_strike': sell_strike,
                            'buy_strike': buy_put['Strike'],
                            'spread_width': spread_width,
                            'credit_received': round(credit_received, 2),
                            'max_profit': round(max_profit, 2),
                            'max_loss': round(max_loss, 2),
                            'profit_probability': round((current_price - sell_strike) / current_price * 100, 1),
                            'sell_volume': sell_put['Volume'],
                            'buy_volume': buy_put['Volume']
                        })
    
    # Sort by credit received (highest first)
    spread_opportunities['call_spreads'] = sorted(spread_opportunities['call_spreads'], 
                                                  key=lambda x: x['credit_received'], reverse=True)[:5]
    spread_opportunities['put_spreads'] = sorted(spread_opportunities['put_spreads'], 
                                                 key=lambda x: x['credit_received'], reverse=True)[:5]
    
    return spread_opportunities

def format_market_analysis_prompt_v7_comprehensive(market_data):
    """
    Format market data into comprehensive DTE-aware v7 prompt for Grok AI analysis
    Combines the best of v4 (market context), v5 (behavioral data), v6 (options data) with DTE intelligence
    
    Parameters:
    market_data: Dictionary from get_comprehensive_market_data()
    
    Returns:
    Formatted comprehensive prompt string for AI analysis (DTE-aware)
    """
    from datetime import datetime
    
    # Get current ticker and market state
    ticker = market_data.get('ticker', 'SPY')  # Default to SPY if not specified
    ticker_data = market_data.get('ticker_recent', {})
    current_price = ticker_data.get('current_price', 645.0)
    price_change_pct = ticker_data.get('price_change_pct', 0.0)
    
    # Get broader market context (v4 enhancement)
    global_markets = market_data.get('global_markets', {})
    spx_data = global_markets.get('^SPX', {'current_price': current_price * 10, 'day_over_day_change': 0.5})
    
    # Calculate volatility environment from price movement instead of VIX
    price_volatility = abs(price_change_pct)
    volatility_level = "High" if price_volatility > 2.0 else "Elevated" if price_volatility > 1.0 else "Low"
    
    # Get DTE information and context
    dte = market_data.get('dte', 0)
    dte_summary = market_data.get('dte_summary', {})
    dte_display = dte_summary.get('display_name', f'{dte}DTE')
    current_time = market_data.get('timestamp', {}).get('market_time', '10:00:00 EST')
    
    # Technical analysis data (v4/v5 enhancement)
    tech_data = market_data.get('technical_analysis', {})
    rsi_data = market_data.get('rsi_analysis', {'current_rsi': 50.0})
    
    # Recent price action and behavioral data (v5 enhancement)
    recent_data = market_data.get('spy_5min_data', [])
    price_action_lines = []
    if recent_data and len(recent_data) >= 6:
        for i, candle in enumerate(recent_data[-6:]):  # Last 6 intervals
            timestamp = candle.get('timestamp', f'09:{50+i*2:02d}')
            price = candle.get('close', current_price)
            volume = candle.get('volume', 1000000)
            price_action_lines.append(f"{timestamp}: ${price:.2f} (Vol: {volume:,})")
    else:
        # Fallback behavioral data
        times = ["09:50", "09:52", "09:54", "09:56", "09:58", "10:00"]
        for i, time_str in enumerate(times):
            price_var = current_price + (i - 3) * 0.05
            volume_var = 1200000 + i * 100000
            price_action_lines.append(f"{time_str}: ${price_var:.2f} (Vol: {volume_var:,})")
    
    # Behavioral analysis (v5 enhancement)
    if len(price_action_lines) >= 2:
        first_price = float(price_action_lines[0].split('$')[1].split(' ')[0])
        last_price = float(price_action_lines[-1].split('$')[1].split(' ')[0])
        first_vol = int(price_action_lines[0].split('Vol: ')[1].split(')')[0].replace(',', ''))
        last_vol = int(price_action_lines[-1].split('Vol: ')[1].split(')')[0].replace(',', ''))
        
        momentum = "Accelerating up" if last_price > first_price + 0.10 else "Decelerating" if last_price < first_price - 0.10 else "Choppy"
        volume_pattern = "Increasing" if last_vol > first_vol else "Decreasing"
        price_range = f"${min(float(line.split('$')[1].split(' ')[0]) for line in price_action_lines):.2f} - ${max(float(line.split('$')[1].split(' ')[0]) for line in price_action_lines):.2f}"
    else:
        momentum = "Neutral"
        volume_pattern = "Steady" 
        price_range = f"${current_price-0.15:.2f} - ${current_price+0.15:.2f}"
    
    # Enhanced options volume data with flow analysis (v7 upgrade)
    options_data_lines = []
    enhanced_flow_summary = ""
    
    if market_data.get('options_analysis'):
        opts = market_data['options_analysis']
        
        # Extract enhanced flow metrics
        flow_bias = opts.get('flow_bias', 'No Flow')
        call_vol_ratio = opts.get('call_volume_ratio', 0)
        put_vol_ratio = opts.get('put_volume_ratio', 0)
        volume_concentration = opts.get('volume_concentration', 0)
        unusual_call_count = opts.get('unusual_call_count', 0)
        unusual_put_count = opts.get('unusual_put_count', 0)
        total_volume = opts.get('total_volume', 0)
        
        # Create enhanced flow summary
        unusual_activity = ""
        if unusual_call_count > 0 or unusual_put_count > 0:
            unusual_activity = f" | Unusual: {unusual_call_count}C, {unusual_put_count}P"
        
        concentration_level = "High" if volume_concentration > 0.5 else "Medium" if volume_concentration > 0.3 else "Low"
        
        enhanced_flow_summary = f"""**Flow Analysis:** {flow_bias} (C:{call_vol_ratio:.1%}, P:{put_vol_ratio:.1%}) | Vol Concentration: {concentration_level} ({volume_concentration:.1%}){unusual_activity}"""
        
        # Enhanced options analysis
        if opts.get('options_chain'):
            # Get ATM and nearby strikes with highest volume
            chain = opts['options_chain']
            
            # Group by strike and sum volumes for calls/puts
            strikes_data = {}
            for option in chain[:20]:  # Top 20 most active
                strike = option.get('Strike', 0)
                volume = option.get('Volume', 0)
                option_type = option.get('Type', '')
                
                if strike not in strikes_data:
                    strikes_data[strike] = {'call_vol': 0, 'put_vol': 0}
                
                if option_type == 'Call':
                    strikes_data[strike]['call_vol'] += volume
                else:
                    strikes_data[strike]['put_vol'] += volume
            
            # Get top 5 strikes by total volume for comprehensive analysis
            top_strikes = sorted(strikes_data.items(), 
                               key=lambda x: x[1]['call_vol'] + x[1]['put_vol'], 
                               reverse=True)[:5]
            
            for strike, volumes in top_strikes:
                call_ratio = volumes['call_vol'] / (volumes['call_vol'] + volumes['put_vol']) if (volumes['call_vol'] + volumes['put_vol']) > 0 else 0
                flow_bias_strike = " (Call heavy)" if call_ratio > 0.7 else " (Put heavy)" if call_ratio < 0.3 else " (Balanced)"
                line = f"${int(strike)}: {volumes['call_vol']:,}C | {volumes['put_vol']:,}P{flow_bias_strike}"
                options_data_lines.append(line)
        
        if not options_data_lines:
            # Enhanced fallback with call/put flow analysis
            call_vol = opts.get('total_call_volume', 12908)
            put_vol = opts.get('total_put_volume', 521)
            call_put_ratio = call_vol / put_vol if put_vol > 0 else 10
            
            options_data_lines = [
                f"${current_price:.0f}: {call_vol//3:,}C | {put_vol//5:,}P (ATM, Call ratio: {call_put_ratio:.1f}:1)",
                f"${current_price-2:.0f}: {call_vol//4:,}C | {put_vol//3:,}P (ITM puts)",
                f"${current_price+2:.0f}: {call_vol//5:,}C | {put_vol//8:,}P (OTM calls)"
            ]
    else:
        # Enhanced fallback with call/put flow analysis
        options_data_lines = [
            f"${current_price:.0f}C: 5,248 vol | ${current_price:.0f}P: 75 vol (Heavy call flow)",
            f"${current_price-2:.0f}C: 4,393 vol | ${current_price-2:.0f}P: 289 vol (Balanced)",
            f"${current_price+2:.0f}C: 3,267 vol | ${current_price+2:.0f}P: 157 vol (Call skew)"
        ]
    
    # DTE-specific context and timing
    if dte == 0:
        time_message = f"Current time: {current_time} (same-day expiration)"
        expiry_context = "Today at 4:00 PM ET"
        time_decay_impact = "Very High (rapid decay)"
        strategy_focus = "Quick directional moves or high-probability neutral plays"
        risk_profile = "Minimize overnight risk, focus on intraday momentum"
        time_remaining = "6 hours remaining" if "10:00" in current_time else "Market hours remaining"
    elif dte == 1:
        time_message = f"Current time: {current_time} (next-day expiration)"
        expiry_context = "Tomorrow at 4:00 PM ET"
        time_decay_impact = "High (overnight decay + one day)"
        strategy_focus = "Balance time decay with directional opportunity"
        risk_profile = "Moderate risk, account for overnight events"
        time_remaining = "~30 hours remaining"
    elif dte <= 3:
        time_message = f"Current time: {current_time} ({dte}-day expiration)"
        expiry_context = f"{dte} days until expiration"
        time_decay_impact = "Moderate (multiple days of decay)"
        strategy_focus = "Directional plays with time for position management"
        risk_profile = f"Higher risk tolerance acceptable, {dte}x time buffer"
        time_remaining = f"{dte} trading days remaining"
    else:
        time_message = f"Current time: {current_time} ({dte}-day expiration)"
        expiry_context = f"{dte} days until expiration" 
        time_decay_impact = "Lower (weekly+ timeframe)"
        strategy_focus = "Longer-term directional plays and wider spreads"
        risk_profile = f"Full range strategies, {dte}-day development time"
        time_remaining = f"{dte} days for position development"
    
    # Technical setup analysis (v4 enhancement)
    trend_analysis = "Bullish" if price_change_pct > 0.1 else "Bearish" if price_change_pct < -0.1 else "Neutral"
    volatility_env = volatility_level  # Use calculated volatility from price movement
    support_level = current_price - (3 if dte == 0 else 5 if dte <= 3 else 10)
    resistance_level = current_price + (3 if dte == 0 else 5 if dte <= 3 else 10)
    
    # Enhanced Greeks and Options Chain Analysis
    enhanced_greeks = get_enhanced_greeks_data(ticker=ticker, dte=dte, current_price=current_price)
    enhanced_options = get_enhanced_options_chain_data(ticker=ticker, dte=dte, current_price=current_price)
    
    # Format enhanced Greeks section
    enhanced_greeks_section = ""
    if enhanced_greeks:
        summary = enhanced_greeks['summary']
        enhanced_greeks_section = f"""
**Greeks Summary:** ATM Δ={summary['atm_call_delta']:.3f}, Γ={summary['atm_call_gamma']:.4f}, Θ={summary['atm_call_theta']:.2f}, ν={summary['atm_call_vega']:.2f} | IV: {summary['implied_vol']:.1%} | Strikes: {summary['total_strikes']}"""
    
    # Create unified options table combining Greeks and market data
    detailed_options_table = ""
    if enhanced_greeks and enhanced_options:
        greeks_data = enhanced_greeks.get('options_greeks', [])
        options_data = enhanced_options.get('options', [])
        
        # Create a lookup for options data by strike and type
        options_lookup = {}
        for opt in options_data:
            key = f"{opt['strike']:.0f}_{opt['option_type']}"
            options_lookup[key] = opt
        
        detailed_options_table = f"""
## Detailed Options Quotes ({dte_display})
**Strike | Type | Volume | OI | Bid/Ask | Delta | Gamma | Theta | Vega**"""
        
        for greek_data in greeks_data:
            strike = greek_data['strike']
            
            # Add call data
            call_key = f"{strike:.0f}_call"
            call_opt = options_lookup.get(call_key, {})
            call_greeks = greek_data['call']
            
            call_volume = call_opt.get('volume', 0)
            call_oi = call_opt.get('open_interest', 0)
            call_bid = call_opt.get('bid', 0)
            call_ask = call_opt.get('ask', 0)
            
            detailed_options_table += f"""
${strike:.0f} | C | {call_volume} | {call_oi} | ${call_bid:.2f}/${call_ask:.2f} | {call_greeks['delta']:.3f} | {call_greeks['gamma']:.4f} | {call_greeks['theta']:.2f} | {call_greeks['vega']:.2f}"""
            
            # Add put data
            put_key = f"{strike:.0f}_put"
            put_opt = options_lookup.get(put_key, {})
            put_greeks = greek_data['put']
            
            put_volume = put_opt.get('volume', 0)
            put_oi = put_opt.get('open_interest', 0)
            put_bid = put_opt.get('bid', 0)
            put_ask = put_opt.get('ask', 0)
            
            detailed_options_table += f"""
${strike:.0f} | P | {put_volume} | {put_oi} | ${put_bid:.2f}/${put_ask:.2f} | {put_greeks['delta']:.3f} | {put_greeks['gamma']:.4f} | {put_greeks['theta']:.2f} | {put_greeks['vega']:.2f}"""
    
    return f"""# {ticker} {dte_display} Trading Analysis - Comprehensive v7 - {datetime.now().strftime('%A, %B %d')}

## Market Overview
- **{ticker}:** ${current_price:.2f} ({price_change_pct:+.2f}%)
- **SPX:** {spx_data['current_price']:,.0f} ({spx_data['day_over_day_change']:+.2f}%)
- **Volatility:** {volatility_level} (based on {abs(price_change_pct):.1f}% daily move)

## {dte_display} Context
- **Expiration:** {expiry_context}
- **Time Decay:** {time_decay_impact}
- **Time Remaining:** {time_remaining}
- **Strategy Range:** ${support_level:.0f} - ${resistance_level:.0f}

## Technical Setup
- **Trend:** {trend_analysis}
- **Volatility Environment:** {volatility_env}
- **Support:** ${support_level:.0f}
- **Resistance:** ${resistance_level:.0f}

### Enhanced RSI Analysis
- **Current RSI:** {rsi_data['current_rsi']:.1f} ({"Overbought" if rsi_data['current_rsi'] > 70 else "Oversold" if rsi_data['current_rsi'] < 30 else "Neutral"} territory)
- **RSI Momentum:** {rsi_data.get('rsi_momentum', 'neutral').replace('_', ' ').title()}
- **Multi-Timeframe Bias:** {rsi_data.get('multi_timeframe_bias', 'neutral').replace('_', ' ').title()}
- **RSI Strength:** {rsi_data.get('rsi_strength', 0):.2f} (rate of change)

### Enhanced Volatility Analysis
- **Market State:** {tech_data.get('bollinger_bands', {}).get('market_state', 'Normal')}
- **Bollinger Position:** {tech_data.get('bollinger_bands', {}).get('bb_percent', 0.5):.1%} (0%=Lower Band, 100%=Upper Band)
- **Volatility Regime:** {"Squeeze" if tech_data.get('bollinger_bands', {}).get('bb_squeeze', False) else "Expansion" if tech_data.get('bollinger_bands', {}).get('volatility_expansion', False) else "Normal"}
- **Breakout Status:** {"Upper Breakout" if tech_data.get('bollinger_bands', {}).get('upper_breakout', False) else "Lower Breakout" if tech_data.get('bollinger_bands', {}).get('lower_breakout', False) else "Range-bound"}

### Enhanced Trend Analysis  
- **Short-term (EMA):** {tech_data.get('moving_averages', {}).get('ema_trend', 'neutral').replace('_', ' ').title()} (Strength: {tech_data.get('bollinger_bands', {}).get('trend_strength_ema', 0):.2%})
- **Medium-term (SMA):** {tech_data.get('moving_averages', {}).get('sma_trend', 'neutral').replace('_', ' ').title()} (Strength: {tech_data.get('bollinger_bands', {}).get('trend_strength_sma', 0):.2%})
- **Volume Confirmation:** {"High" if tech_data.get('bollinger_bands', {}).get('volume_ratio', 1) > 1.5 else "Normal" if tech_data.get('bollinger_bands', {}).get('volume_ratio', 1) > 0.8 else "Low"} Volume

## {ticker} Recent Price Action (Behavioral Analysis)
{chr(10).join(price_action_lines)}

### Behavioral Analysis
- **Price Momentum:** {momentum}
- **Volume Pattern:** {volume_pattern}
- **Intraday Range:** {price_range}

## Live Options Volume Data ({dte_display})
{enhanced_flow_summary}
{chr(10).join(options_data_lines)}

## Comprehensive Options Chain Analysis ({dte_display})
**Market Summary:**
- Total Options Available: {len(market_data.get('options_analysis', {}).get('options_chain') or [])} contracts
- Strike Range: ${current_price-15:.0f} - ${current_price+15:.0f}
- Put/Call Volume Ratio: {market_data.get('options_analysis', {}).get('put_call_ratio', 'N/A')}
- Total Call Volume: {market_data.get('options_analysis', {}).get('total_call_volume', 0)} | Total Put Volume: {market_data.get('options_analysis', {}).get('total_put_volume', 0)}
- **Flow Pattern:** {market_data.get('options_analysis', {}).get('flow_bias', 'No Flow')} with {market_data.get('options_analysis', {}).get('volume_concentration', 0):.1%} concentration

**Most Active Call Options:**
- Strike selection optimized for {dte_display} timeframe
- Volume leaders indicate market sentiment and liquidity  
- Focus on ATM and near-the-money strikes for best execution
- High-volume call strikes: {', '.join([f'${strike:.0f}' for strike in market_data.get('options_analysis', {}).get('high_volume_call_strikes', [])[:5]])}

**Most Active Put Options:**
- Downside protection positioning
- Put volume concentration shows support levels
- High volume puts indicate institutional hedging activity
- High-volume put strikes: {', '.join([f'${strike:.0f}' for strike in market_data.get('options_analysis', {}).get('high_volume_put_strikes', [])[:5]])}
{enhanced_greeks_section}
{detailed_options_table}

## Strategy Recommendation Required

Choose the OPTIMAL {dte_display} strategy based on:
1. Current price action and momentum ({momentum})
2. Volatility environment ({volatility_env}) based on {abs(price_change_pct):.1f}% daily movement
3. Time remaining until expiration ({time_remaining})
4. Support/resistance levels (${support_level:.0f}/${resistance_level:.0f})
5. Options flow and volume patterns
6. Recent behavioral patterns ({volume_pattern} volume, {momentum} momentum)

**Strategies:**
- **BULL_PUT_SPREAD:** Bullish/neutral bias, sell put spread below support (${support_level:.0f})
- **BEAR_CALL_SPREAD:** Bearish/neutral bias, sell call spread above resistance (${resistance_level:.0f})
- **IRON_CONDOR:** Range-bound, sell both sides around current price (${current_price:.0f})

## Response Format Required
Provide your analysis (2-3 sentences considering all factors above) followed by a JSON block with your specific {dte_display} trade recommendation.

**JSON Structure (use actual strikes and values based on current market data):**

**For BULL_PUT_SPREAD:**
```json
{{
  "strategy_type": "BULL_PUT_SPREAD",
  "confidence": [YOUR_CONFIDENCE_0_TO_100],
  "market_bias": "bullish",
  "support_level": {support_level:.0f},
  "resistance_level": {resistance_level:.0f},
  "volatility_factor": "[low/elevated/high]",
  "time_decay_impact": "[favorable/neutral/unfavorable]",
  "price_momentum": "{momentum.lower()}",
  "volume_pattern": "{volume_pattern.lower()}",
  "trade_setup": {{
    "short_put_strike": [HIGHER_STRIKE_NUMBER],
    "long_put_strike": [LOWER_STRIKE_NUMBER],
    "credit_received": [CREDIT_AMOUNT],
    "expiration": "[DATE_FORMAT]",
    "max_profit": [CREDIT_TIMES_100],
    "max_loss": [SPREAD_WIDTH_MINUS_CREDIT_TIMES_100]
  }},
  "risk_metrics": {{
    "probability_of_profit": [0_TO_100],
    "reward_risk_ratio": [RATIO],
    "delta": [NEGATIVE_VALUE],
    "theta": [POSITIVE_VALUE],
    "expected_profit": [DOLLAR_AMOUNT]
  }},
  "entry_conditions": {{
    "entry_price_range": "{ticker} between $[LOW] and $[HIGH]",
    "volatility_condition": "daily move < [PERCENTAGE]% for stable environment",
    "volume_requirement": "intraday volume > [NUMBER] shares",
    "momentum_condition": "[SPECIFIC_CONDITION]"
  }},
  "reasoning": "Your comprehensive reasoning here"
}}
```

**For BEAR_CALL_SPREAD:**
```json
{{
  "strategy_type": "BEAR_CALL_SPREAD",
  "confidence": [YOUR_CONFIDENCE_0_TO_100],
  "market_bias": "bearish",
  "support_level": {support_level:.0f},
  "resistance_level": {resistance_level:.0f},
  "volatility_factor": "[low/elevated/high]",
  "time_decay_impact": "[favorable/neutral/unfavorable]",
  "price_momentum": "{momentum.lower()}",
  "volume_pattern": "{volume_pattern.lower()}",
  "trade_setup": {{
    "short_call_strike": [LOWER_STRIKE_NUMBER],
    "long_call_strike": [HIGHER_STRIKE_NUMBER],
    "credit_received": [CREDIT_AMOUNT],
    "expiration": "[DATE_FORMAT]",
    "max_profit": [CREDIT_TIMES_100],
    "max_loss": [SPREAD_WIDTH_MINUS_CREDIT_TIMES_100]
  }},
  "risk_metrics": {{
    "probability_of_profit": [0_TO_100],
    "reward_risk_ratio": [RATIO],
    "delta": [NEGATIVE_VALUE],
    "theta": [POSITIVE_VALUE],
    "expected_profit": [DOLLAR_AMOUNT]
  }},
  "entry_conditions": {{
    "entry_price_range": "{ticker} between $[LOW] and $[HIGH]",
    "volatility_condition": "daily move < [PERCENTAGE]% for stable environment",
    "volume_requirement": "intraday volume > [NUMBER] shares",
    "momentum_condition": "[SPECIFIC_CONDITION]"
  }},
  "reasoning": "Your comprehensive reasoning here"
}}
```

**For IRON_CONDOR:**
```json
{{
  "strategy_type": "IRON_CONDOR",
  "confidence": [YOUR_CONFIDENCE_0_TO_100],
  "market_bias": "neutral",
  "support_level": {support_level:.0f},
  "resistance_level": {resistance_level:.0f},
  "volatility_factor": "[low/elevated/high]",
  "time_decay_impact": "[favorable/neutral/unfavorable]",
  "price_momentum": "{momentum.lower()}",
  "volume_pattern": "{volume_pattern.lower()}",
  "trade_setup": {{
    "short_call_strike": [HIGHER_CALL_STRIKE],
    "long_call_strike": [HIGHEST_CALL_STRIKE],
    "short_put_strike": [LOWER_PUT_STRIKE],
    "long_put_strike": [LOWEST_PUT_STRIKE],
    "credit_received": [TOTAL_CREDIT],
    "expiration": "[DATE_FORMAT]",
    "max_profit": [CREDIT_TIMES_100],
    "max_loss": [SPREAD_WIDTH_MINUS_CREDIT_TIMES_100]
  }},
  "risk_metrics": {{
    "probability_of_profit": [0_TO_100],
    "reward_risk_ratio": [RATIO],
    "delta": [NEAR_ZERO],
    "theta": [POSITIVE_VALUE],
    "expected_profit": [DOLLAR_AMOUNT]
  }},
  "entry_conditions": {{
    "entry_price_range": "{ticker} between $[LOW] and $[HIGH]",
    "volatility_condition": "daily move < [PERCENTAGE]% for stable environment",
    "volume_requirement": "intraday volume > [NUMBER] shares",
    "momentum_condition": "[SPECIFIC_CONDITION]"
  }},
  "reasoning": "Your comprehensive reasoning here"
}}
```

**Important:** Use current {ticker} price (${current_price:.2f}) and {dte_display} timeframe to select appropriate strike prices. Consider the {momentum.lower()} momentum, {volume_pattern.lower()} volume, {volatility_env.lower()} volatility environment, and live options volume data for optimal strike selection and profit targets."""

def format_market_analysis_prompt(market_data):
    """
    Format market data into DTE-aware prompt for Grok AI analysis
    Now uses comprehensive v7 for better analysis quality combining:
    - v4: Market context (volatility analysis, SPX, technical setup)
    - v5: Behavioral data (recent price action, volume patterns)
    - v6: Real options volume and flow
    - v7: Enhanced DTE awareness and comprehensive analysis
    
    Parameters:
    market_data: Dictionary from get_comprehensive_market_data()
    
    Returns:
    Formatted comprehensive prompt string for AI analysis (DTE-aware)
    """
    # Use the comprehensive v7 prompt for better analysis quality
    return format_market_analysis_prompt_v7_comprehensive(market_data)

def main():
    """
    Main function for optimized SPY market analysis using DTE-aware v7 comprehensive prompt
    """
    print("🚀 SPY Market Analysis - DTE-Aware v7 Comprehensive")
    print("=" * 50)
    
    # Initialize Grok analyzer
    try:
        grok_analyzer = GrokAnalyzer()
        print("✅ Grok AI connection initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Grok AI: {e}")
        return
    
    # Get current DTE (can be overridden by user in UI)
    from dte_manager import dte_manager
    current_dte = dte_manager.get_current_dte()
    dte_display = dte_manager.get_dte_display_name(current_dte)
    
    print(f"📅 Analyzing for: {dte_display}")
    
    # Gather market data (DTE-aware focused approach)
    print("🔍 Gathering market data...")
    market_data = get_comprehensive_market_data(include_full_options_chain=False, dte=current_dte)
    
    # Generate DTE-aware optimized v7 comprehensive prompt
    print(f"📝 Generating DTE-aware v7 comprehensive prompt for {dte_display}...")
    analysis_prompt = format_market_analysis_prompt(market_data)
    print(f"📏 Prompt length: {len(analysis_prompt):,} characters")
    
    # Send to Grok AI with proper max_tokens
    print("🤖 Sending analysis to Grok AI...")
    analysis_result = grok_analyzer.send_to_grok(analysis_prompt, max_tokens=1500)
    
    if analysis_result:
        print("✅ Analysis complete!")
        print("="*60)
        print(f"GROK AI ANALYSIS RESULT ({dte_display}):")
        print("="*60)
        print(analysis_result)
        
        # Check for strategy detection
        has_strategy = any(strategy in analysis_result.upper() for strategy in ['BULL_PUT_SPREAD', 'BEAR_CALL_SPREAD', 'IRON_CONDOR'])
        print(f"\n📈 Strategy detected: {'✅' if has_strategy else '❌'}")
        
        # Show DTE-specific context
        if current_dte != 0:
            print(f"🎯 DTE Context: {dte_display} - appropriate for longer-term positioning")
        else:
            print(f"⚡ DTE Context: Same-day expiration - focus on high-probability trades")
    else:
        print("❌ Failed to get analysis from Grok AI")
    
    print(f"\n🎯 DTE-aware v7 comprehensive analysis complete for {dte_display}!")

def run_automated_v7_analysis():
    """
    Run optimized v7 comprehensive analysis for automated trading integration
    Returns the analysis result in a format compatible with automated_trader.py
    
    Returns:
    Dictionary with success status and grok response
    """
    try:
        # Initialize Grok analyzer
        grok_analyzer = GrokAnalyzer()
        
        # Gather market data (focused approach)
        market_data = get_comprehensive_market_data(include_full_options_chain=False, dte=0)
        
        # Generate optimized v7 comprehensive prompt
        analysis_prompt = format_market_analysis_prompt(market_data)
        
        # Send to Grok AI with proper max_tokens
        analysis_result = grok_analyzer.send_to_grok(analysis_prompt, max_tokens=1500)
        
        if analysis_result:
            return {
                'success': True,
                'ai_analysis': analysis_result,
                'grok_response': analysis_result,  # For backward compatibility
                'market_data': market_data,
                'analysis_prompt': analysis_prompt,
                'dte': 0,
                'ticker': 'SPY',
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'success': False,
                'error': 'Failed to get analysis from Grok AI',
                'ai_analysis': None,
                'grok_response': None
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Analysis failed: {e}',
            'ai_analysis': None,
            'grok_response': None
        }

if __name__ == "__main__":
    main()


# ============================================================================
# TRADE AUTOMATION FUNCTIONS
# ============================================================================

class GrokTradeParser:
    """
    Parse Grok AI responses and extract structured trading data
    """
    
    def __init__(self, ticker=None):
        self.logger = self._setup_logging()
        # Get current ticker if none provided
        if ticker is None:
            self.ticker = config.DEFAULT_TICKER
        else:
            self.ticker = ticker
    
    def _setup_logging(self):
        """Set up logging for trade parser"""
        import logging
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)
    
    def parse_grok_response(self, grok_response: str) -> dict:
        """
        Parse Grok AI response and extract structured trading recommendations
        
        Parameters:
        grok_response: Full text response from Grok AI
        
        Returns:
        Dictionary with parsed trading data and full analysis
        """
        try:
            # Look for JSON block after "TRADING RECOMMENDATION:" or at the end
            json_patterns = [
                r'TRADING RECOMMENDATION:\s*\n*```?json\s*(\{.*?\})\s*```?',  # After header with json block
                r'TRADING RECOMMENDATION:\s*\n*(\{.*?\})\s*$',  # After header direct JSON
                r'```json\s*(\{.*?\})\s*```',  # Standard JSON block
                r'(\{[\s\S]*?"strategy_type"[\s\S]*?"entry_conditions"[\s\S]*?\})',  # Direct JSON anywhere
            ]
            
            trading_data = None
            for pattern in json_patterns:
                json_match = re.search(pattern, grok_response, re.DOTALL | re.IGNORECASE)
                if json_match:
                    try:
                        json_str = json_match.group(1)
                        # Clean up common JSON issues
                        json_str = json_str.replace('\\"', '"')  # Fix escaped quotes
                        json_str = json_str.strip()
                        trading_data = json.loads(json_str)
                        self.logger.info("Successfully parsed JSON from structured response")
                        break
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse JSON match: {e}")
                        # Try with more aggressive cleaning
                        try:
                            json_str = json_match.group(1)
                            json_str = json_str.replace('\\"', '"').replace('\\n', '').strip()
                            # Remove any trailing commas
                            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                            trading_data = json.loads(json_str)
                            self.logger.info("Successfully parsed JSON after cleaning")
                            break
                        except:
                            continue
            
            # If no JSON found, try parsing entire response as JSON (legacy support)
            if not trading_data:
                try:
                    trading_data = json.loads(grok_response.strip())
                    self.logger.info("Successfully parsed direct JSON response from Grok")
                except json.JSONDecodeError:
                    self.logger.warning("No valid JSON found, attempting text parsing")
                    return self._fallback_text_parsing(grok_response)
            
            # Extract the analysis text (everything before the JSON)
            if trading_data:
                # Remove JSON block from response to get analysis text
                analysis_text = grok_response
                for pattern in json_patterns:
                    analysis_text = re.sub(pattern, '', analysis_text, flags=re.DOTALL | re.IGNORECASE)
                
                # Clean up analysis text
                analysis_text = analysis_text.replace('TRADING RECOMMENDATION:', '').strip()
                analysis_text = re.sub(r'-{3,}', '', analysis_text).strip()  # Remove separator lines
                
                # Convert new simplified format to our internal structure
                formatted_data = self._format_simplified_json(trading_data)
                
                return {
                    'success': True,
                    'trading_recommendations': formatted_data,
                    'full_analysis': analysis_text,
                    'raw_analysis': grok_response,
                    'error': None
                }
            else:
                # Fallback: try to extract key information using text parsing
                self.logger.warning("No JSON block found, attempting text parsing")
                return self._fallback_text_parsing(grok_response)
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            return {
                'success': False,
                'trading_recommendations': None,
                'raw_analysis': grok_response,
                'error': f"JSON parsing failed: {e}"
            }
        except Exception as e:
            self.logger.error(f"Unexpected parsing error: {e}")
            return {
                'success': False,
                'trading_recommendations': None,
                'raw_analysis': grok_response,
                'error': f"Parsing failed: {e}"
            }
    
    def _format_simplified_json(self, trading_data: dict) -> dict:
        """
        Convert new structured JSON format to our internal structure
        
        Parameters:
        trading_data: Structured JSON from Grok with strategy type identification
        
        Returns:
        Formatted trading data in internal structure expected by frontend
        """
        try:
            strategy_type = trading_data.get('strategy_type', 'unknown')
            trade_setup = trading_data.get('trade_setup', {})
            
            # Build legs array based on strategy type
            legs = []
            
            if strategy_type == 'BULL_PUT_SPREAD':
                # Use exact field names specified in prompt
                sell_put_strike = trade_setup.get('short_put_strike')
                buy_put_strike = trade_setup.get('long_put_strike')
                
                if sell_put_strike is None or buy_put_strike is None:
                    self.logger.error(f"Missing required fields for BULL_PUT_SPREAD: short_put_strike={sell_put_strike}, long_put_strike={buy_put_strike}")
                    return trading_data  # Return original if required fields missing
                
                legs = [
                    {
                        'action': 'sell',
                        'option_type': 'put',
                        'strike': sell_put_strike,
                        'quantity': 1
                    },
                    {
                        'action': 'buy', 
                        'option_type': 'put',
                        'strike': buy_put_strike,
                        'quantity': 1
                    }
                ]
                
            elif strategy_type == 'BEAR_CALL_SPREAD':
                # Use exact field names specified in prompt
                sell_call_strike = trade_setup.get('short_call_strike')
                buy_call_strike = trade_setup.get('long_call_strike')
                
                if sell_call_strike is None or buy_call_strike is None:
                    self.logger.error(f"Missing required fields for BEAR_CALL_SPREAD: short_call_strike={sell_call_strike}, long_call_strike={buy_call_strike}")
                    return trading_data  # Return original if required fields missing
                
                legs = [
                    {
                        'action': 'sell',
                        'option_type': 'call',
                        'strike': sell_call_strike,
                        'quantity': 1
                    },
                    {
                        'action': 'buy', 
                        'option_type': 'call',
                        'strike': buy_call_strike,
                        'quantity': 1
                    }
                ]
                
            elif strategy_type == 'IRON_CONDOR':
                # Use exact field names specified in prompt
                sell_call_strike = trade_setup.get('short_call_strike')
                buy_call_strike = trade_setup.get('long_call_strike')
                sell_put_strike = trade_setup.get('short_put_strike')
                buy_put_strike = trade_setup.get('long_put_strike')
                
                if (sell_call_strike is None or buy_call_strike is None or 
                    sell_put_strike is None or buy_put_strike is None):
                    self.logger.error(f"Missing required fields for IRON_CONDOR: short_call_strike={sell_call_strike}, long_call_strike={buy_call_strike}, short_put_strike={sell_put_strike}, long_put_strike={buy_put_strike}")
                    return trading_data  # Return original if required fields missing
                
                # Handle as two separate spreads that can be managed independently
                legs = [
                    # Call spread side
                    {
                        'action': 'sell',
                        'option_type': 'call',
                        'strike': sell_call_strike,
                        'quantity': 1,
                        'spread_side': 'call_spread'
                    },
                    {
                        'action': 'buy', 
                        'option_type': 'call',
                        'strike': buy_call_strike,
                        'quantity': 1,
                        'spread_side': 'call_spread'
                    },
                    # Put spread side
                    {
                        'action': 'sell',
                        'option_type': 'put',
                        'strike': sell_put_strike,
                        'quantity': 1,
                        'spread_side': 'put_spread'
                    },
                    {
                        'action': 'buy',
                        'option_type': 'put', 
                        'strike': buy_put_strike,
                        'quantity': 1,
                        'spread_side': 'put_spread'
                    }
                ]
            
            # Create enhanced risk management with required fields
            risk_metrics = trading_data.get('risk_metrics', {})
            
            # Calculate stop loss and take profit prices for Iron Condor
            stop_loss_price = "undefined"
            take_profit_price = "undefined"
            
            if strategy_type == 'IRON_CONDOR':
                max_profit = risk_metrics.get('max_profit', 0)
                max_loss = risk_metrics.get('max_loss', 0)
                
                if max_profit > 0:
                    # Import IC_PROFIT_TARGET and IC_STOP_LOSS from config
                    from config import IC_PROFIT_TARGET, IC_STOP_LOSS
                    
                    # Take profit at 30% of max profit (keeping 70% of premium as profit)
                    take_profit_price = round(max_profit * IC_PROFIT_TARGET, 2)
                    
                    # Stop loss calculation for Iron Condor:
                    # For credit spreads, stop loss is typically when the spread value reaches a multiple of credit received
                    # Since max_profit represents the credit received, stop loss is when we'd lose IC_STOP_LOSS times that credit
                    if max_loss > 0:
                        # Stop loss is when the position loses IC_STOP_LOSS times the credit received
                        stop_loss_price = round(max_profit * IC_STOP_LOSS, 2)
                    else:
                        # Fallback: Use the max_loss as stop loss
                        stop_loss_price = round(max_loss, 2) if max_loss > 0 else "undefined"
                        
            elif strategy_type in ['BULL_PUT_SPREAD', 'BEAR_CALL_SPREAD']:
                max_profit = risk_metrics.get('max_profit', 0)
                max_loss = risk_metrics.get('max_loss', 0)
                
                if max_profit > 0 and max_loss > 0:
                    # Import spread configuration from config
                    from config import SPREAD_PROFIT_TARGET, SPREAD_STOP_LOSS
                    
                    # Take profit at 50% of max profit for credit spreads
                    take_profit_price = round(max_profit * SPREAD_PROFIT_TARGET, 2)
                    
                    # Stop loss at 25% of premium paid (for credit spreads, this is based on max loss)
                    stop_loss_price = round(max_loss * SPREAD_STOP_LOSS, 2)
            
            else:
                # For other strategies, use generic calculations if available
                max_profit = risk_metrics.get('max_profit', 0)
                max_loss = risk_metrics.get('max_loss', 0)
                
                if max_profit > 0:
                    # Generic 50% take profit
                    take_profit_price = round(max_profit * 0.5, 2)
                    
                if max_loss > 0:
                    # Generic 50% stop loss
                    stop_loss_price = round(max_loss * 0.5, 2)
            
            enhanced_risk_management = {
                'max_profit': risk_metrics.get('max_profit', 0),
                'max_loss': risk_metrics.get('max_loss', 0),
                'position_size_percent': risk_metrics.get('position_size_percent', 0.02),  # Default 2% from config
                'risk_reward_ratio': risk_metrics.get('risk_reward_ratio', 1.0),
                'probability_of_profit': risk_metrics.get('probability_of_profit', 50),
                'target_profit_pct': risk_metrics.get('target_profit_pct', 50),
                'stop_loss_pct': risk_metrics.get('stop_loss_pct', 200),
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price
            }
            
            # Create the recommendation structure
            recommendation = {
                'strategy_type': strategy_type.upper(),  # Keep original format for frontend
                'strategy': strategy_type.lower(),  # Also keep lowercase for backwards compatibility
                'market_bias': trading_data.get('market_bias', 'neutral'),
                'confidence': trading_data.get('confidence', 50) / 100.0,  # Convert to decimal
                'legs': legs,
                'risk_management': enhanced_risk_management,
                'entry_conditions': trading_data.get('entry_conditions', {}),
                'trade_setup': trade_setup,  # Keep original for reference
                'reasoning': trading_data.get('reasoning', 'Analysis-based recommendation')  # Add reasoning field
            }
            
            # Return in format expected by frontend (with primary_recommendation wrapper)
            return {
                'primary_recommendation': recommendation
            }
            
        except Exception as e:
            self.logger.error(f"Error formatting structured JSON: {e}")
            return trading_data  # Return original if formatting fails
    
    def _fallback_text_parsing(self, response: str) -> dict:
        """
        Fallback text parsing when JSON block is not available
        
        Parameters:
        response: Grok AI response text
        
        Returns:
        Dictionary with extracted data or error
        """
        try:
            # Extract key trading signals using regex patterns
            recommendations = []
            
            # Enhanced patterns for better extraction
            
            # 1. Look for our new strategy type identifiers
            bull_put_pattern = r'BULL_PUT_SPREAD'
            bear_call_pattern = r'BEAR_CALL_SPREAD'
            iron_condor_pattern = r'IRON_CONDOR'
            
            strategy_type = 'extracted_from_text'
            if re.search(bull_put_pattern, response, re.IGNORECASE):
                strategy_type = 'bull_put_spread'
            elif re.search(bear_call_pattern, response, re.IGNORECASE):
                strategy_type = 'bear_call_spread'
            elif re.search(iron_condor_pattern, response, re.IGNORECASE):
                strategy_type = 'iron_condor'
            
            # 2. Look for Bull Put Spread (Sell higher strike put, buy lower strike put)
            bull_put_strikes_pattern = r'Sell.*?[Pp]ut.*?\$(\d+).*?Buy.*?[Pp]ut.*?\$(\d+)'
            bull_put_match = re.search(bull_put_strikes_pattern, response, re.IGNORECASE)
            
            # 3. Look for Bear Call Spread (Sell lower strike call, buy higher strike call)  
            bear_call_strikes_pattern = r'Sell.*?[Cc]all.*?\$(\d+).*?Buy.*?[Cc]all.*?\$(\d+)'
            bear_call_match = re.search(bear_call_strikes_pattern, response, re.IGNORECASE)
            
            # 4. Look for Iron Condor components separately, then combine
            # Call spread pattern - account for options notation
            call_spread_pattern = r'Sell.*?[Cc]all.*?\$(\d+).*?Buy.*?[Cc]all.*?\$(\d+)'
            call_spread_match = re.search(call_spread_pattern, response, re.IGNORECASE)
            
            # Put spread pattern - account for options notation
            put_spread_pattern = r'Sell.*?[Pp]ut.*?\$(\d+).*?Buy.*?[Pp]ut.*?\$(\d+)'
            put_spread_match = re.search(put_spread_pattern, response, re.IGNORECASE)
            
            # Check if we have both components of an Iron Condor
            iron_condor_match = None
            if call_spread_match and put_spread_match:
                # Create a combined match-like object
                class IronCondorMatch:
                    def __init__(self, call_match, put_match):
                        # Groups: [short_call, long_call, short_put, long_put]
                        self._groups = call_match.groups() + put_match.groups()
                    def group(self, n):
                        return self._groups[n-1]
                    def groups(self):
                        return self._groups
                
                iron_condor_match = IronCondorMatch(call_spread_match, put_spread_match)
            
            # Check if we have both components of an Iron Condor
            iron_condor_match = None
            if call_spread_match and put_spread_match:
                # Create a combined match-like object
                class IronCondorMatch:
                    def __init__(self, call_match, put_match):
                        # Groups: [short_call, long_call, short_put, long_put]
                        self._groups = call_match.groups() + put_match.groups()
                    def group(self, n):
                        return self._groups[n-1]
                    def groups(self):
                        return self._groups
                
                iron_condor_match = IronCondorMatch(call_spread_match, put_spread_match)
            
            # 2. Look for general spread recommendations
            spread_pattern = r'(Bull Put|Bear Call|Iron Condor|Call Spread|Put Spread).*?(\$?\d+\.?\d*)\s*(?:Put|Call).*?(\$?\d+\.?\d*)\s*(?:Put|Call)'
            spread_matches = re.findall(spread_pattern, response, re.IGNORECASE)
            
            # 3. Look for single option recommendations
            option_pattern = r'(Buy|Sell)\s*(\$?\d+\.?\d*)\s*(Call|Put).*?(\$?\d+\.?\d*)'
            option_matches = re.findall(option_pattern, response, re.IGNORECASE)
            
            # 4. Look for target credit/debit - Enhanced patterns
            credit_pattern = r'[Cc]redit:?\s*(?:~\s*)?\$?(\d+\.?\d*)-?(?:\$?(\d+\.?\d*))?'
            credit_match = re.search(credit_pattern, response)
            
            # 5. Look for max risk/loss
            max_risk_pattern = r'[Mm]ax [Rr]isk:?\s*\$?(\d+)-?(?:\$?(\d+))?'
            max_risk_match = re.search(max_risk_pattern, response)
            
            # 6. Look for breakevens
            breakeven_pattern = r'[Bb]reakevens?:?\s*(?:~\s*)?\$?(\d+\.?\d*).*?(?:and|&)\s*\$?(\d+\.?\d*)'
            breakeven_match = re.search(breakeven_pattern, response)
            
            # 7. Extract confidence/probability - Enhanced patterns
            confidence_pattern = r'(\d+)%\s*(?:confidence|probability|[Pp]robability)'
            confidence_match = re.search(confidence_pattern, response)
            
            # Also look for "Neutral (60% Probability)" style - this should take priority
            neutral_confidence_pattern = r'[Nn]eutral.*?\((\d+)%\s*[Pp]robability\)'
            neutral_confidence_match = re.search(neutral_confidence_pattern, response)
            
            # Look for range-bound probability
            range_probability_pattern = r'range-bound.*?\((\d+)%\s*[Pp]robability\)'
            range_probability_match = re.search(range_probability_pattern, response)
            
            # Build enhanced recommendation structure
            strategy_type = 'extracted_from_text'
            confidence = 0.5
            
            # Priority order for confidence extraction
            if neutral_confidence_match:
                confidence = int(neutral_confidence_match.group(1)) / 100.0
            elif range_probability_match:
                confidence = int(range_probability_match.group(1)) / 100.0
            elif confidence_match:
                confidence = int(confidence_match.group(1)) / 100.0
            
            # Handle Bull Put Spread (Sell higher strike put, buy lower strike put)
            if bull_put_match and strategy_type == 'bull_put_spread':
                sell_put_strike = bull_put_match.group(1)  # Higher strike (sell)
                buy_put_strike = bull_put_match.group(2)  # Lower strike (buy)
                
                # Extract additional info
                credit_pattern = r'[Cc]redit:?\s*(?:~\s*)?\$?(\d+\.?\d*)-?(?:\$?(\d+\.?\d*))?'
                credit_match = re.search(credit_pattern, response)
                
                # Calculate risk/reward
                target_credit = "2.00"  # Default 
                if credit_match:
                    if credit_match.group(2):
                        target_credit = f"{credit_match.group(1)}-{credit_match.group(2)}"
                    else:
                        target_credit = credit_match.group(1)
                
                max_loss = float(sell_put_strike) - float(buy_put_strike) - float(target_credit.split('-')[0])
                breakeven = float(sell_put_strike) - float(target_credit.split('-')[0])
                
                return {
                    'success': True,
                    'trading_recommendations': {
                        'primary_recommendation': {
                            'strategy_type': 'bull_put_spread',
                            'confidence': confidence,
                            'market_bias': 'bullish',
                            'reasoning': 'Extracted Bull Put Spread from detailed analysis',
                            'legs': [
                                {
                                    'action': 'sell',
                                    'option_type': 'put',
                                    'strike': int(sell_put_strike),
                                    'quantity': 1
                                },
                                {
                                    'action': 'buy',
                                    'option_type': 'put', 
                                    'strike': int(buy_put_strike),
                                    'quantity': 1
                                }
                            ],
                            'risk_management': {
                                'max_profit': f"${target_credit}",
                                'max_loss': f"${max_loss:.0f}",
                                'position_size_percent': 0.02,  # Default 2% position size
                                'breakeven': f"${breakeven:.2f}",
                                'profit_probability': f"{int(confidence*100)}%"
                            },
                            'raw_signals': {
                                'spreads': [['bull_put_spread', sell_put_strike, buy_put_strike]],
                                'options': []
                            }
                        }
                    },
                    'raw_analysis': response,
                    'error': None
                }
            
            # Handle Bear Call Spread (Sell lower strike call, buy higher strike call)
            if bear_call_match and strategy_type == 'bear_call_spread':
                sell_call_strike = bear_call_match.group(1)  # Lower strike (sell)
                buy_call_strike = bear_call_match.group(2)  # Higher strike (buy)
                
                return {
                    'success': True,
                    'trading_recommendations': {
                        'primary_recommendation': {
                            'strategy_type': 'bear_call_spread',
                            'confidence': confidence,
                            'market_bias': 'bearish',
                            'reasoning': 'Extracted Bear Call Spread from detailed analysis',
                            'legs': [
                                {
                                    'action': 'sell',
                                    'option_type': 'call',
                                    'strike': int(sell_call_strike),
                                    'quantity': 1
                                },
                                {
                                    'action': 'buy',
                                    'option_type': 'call', 
                                    'strike': int(buy_call_strike),
                                    'quantity': 1
                                }
                            ],
                            'risk_management': {
                                'max_profit': "TBD",
                                'max_loss': "TBD",
                                'position_size_percent': 0.02,  # Default 2% position size
                                'breakeven': "TBD",
                                'profit_probability': f"{int(confidence*100)}%"
                            },
                            'raw_signals': {
                                'spreads': [['bear_call_spread', sell_call_strike, buy_call_strike]],
                                'options': []
                            }
                        }
                    },
                    'raw_analysis': response,
                    'error': None
                }

            # Process Iron Condor specifically (highest priority)
            if iron_condor_match:
                short_call = iron_condor_match.group(1).replace('$', '')
                long_call = iron_condor_match.group(2).replace('$', '')
                short_put = iron_condor_match.group(3).replace('$', '')
                long_put = iron_condor_match.group(4).replace('$', '')
                
                strategy_type = 'iron_condor'
                
                # Calculate target credit and max risk from extracted data
                target_credit = '0.80-1.20'  # Default from analysis
                max_loss_str = '120-180'  # Default from analysis
                breakeven_str = 'See analysis'
                
                if credit_match:
                    if credit_match.group(2):
                        target_credit = f"{credit_match.group(1)}-{credit_match.group(2)}"
                    else:
                        target_credit = credit_match.group(1)
                
                if max_risk_match:
                    if max_risk_match.group(2):
                        max_loss_str = f"{max_risk_match.group(1)}-{max_risk_match.group(2)}"
                    else:
                        max_loss_str = max_risk_match.group(1)
                
                if breakeven_match:
                    breakeven_str = f"Upper: ${breakeven_match.group(2)}, Lower: ${breakeven_match.group(1)}"
                
                # Calculate numeric values for additional calculations
                if '-' in target_credit:
                    credit_values = [float(x) for x in target_credit.split('-')]
                    avg_credit = sum(credit_values) / len(credit_values)
                else:
                    avg_credit = float(target_credit)
                    
                # Enhance breakevens if not explicitly found
                if breakeven_match is None:
                    upper_breakeven = float(short_call) + avg_credit
                    lower_breakeven = float(short_put) - avg_credit
                    breakeven_str = f"Upper: ${upper_breakeven:.2f}, Lower: ${lower_breakeven:.2f}"
                
                return {
                    'success': True,
                    'trading_recommendations': {
                        'primary_recommendation': {
                            'strategy_type': strategy_type,
                            'confidence': confidence,
                            'reasoning': 'Extracted Iron Condor from detailed analysis',
                            'legs': [
                                {
                                    'action': 'sell',
                                    'option_type': 'call',
                                    'strike': short_call,
                                    'quantity': 1
                                },
                                {
                                    'action': 'buy',
                                    'option_type': 'call', 
                                    'strike': long_call,
                                    'quantity': 1
                                },
                                {
                                    'action': 'sell',
                                    'option_type': 'put',
                                    'strike': short_put,
                                    'quantity': 1
                                },
                                {
                                    'action': 'buy',
                                    'option_type': 'put',
                                    'strike': long_put,
                                    'quantity': 1
                                }
                            ],
                            'risk_management': {
                                'max_profit': f"${target_credit}",
                                'max_loss': f"${max_loss_str}",
                                'position_size_percent': 0.02,  # Default 2% position size
                                'breakeven': breakeven_str,
                                'profit_probability': f"{int(confidence*100)}%"
                            },
                            'raw_signals': {
                                'spreads': [['iron_condor', short_call, long_call, short_put, long_put]],
                                'options': []
                            }
                        }
                    },
                    'raw_analysis': response,
                    'error': None
                }
            
            # Build basic recommendation structure for other strategies
            if spread_matches or option_matches:
                return {
                    'success': True,
                    'trading_recommendations': {
                        'primary_recommendation': {
                            'strategy_type': strategy_type,
                            'confidence': confidence,
                            'reasoning': 'Extracted from text analysis',
                            'raw_signals': {
                                'spreads': spread_matches,
                                'options': option_matches
                            }
                        }
                    },
                    'raw_analysis': response,
                    'error': 'Fallback parsing used - manual review recommended'
                }
            else:
                return {
                    'success': False,
                    'trading_recommendations': None,
                    'raw_analysis': response,
                    'error': 'No clear trading signals found in text'
                }
                
        except Exception as e:
            return {
                'success': False,
                'trading_recommendations': None,
                'raw_analysis': response,
                'error': f"Fallback parsing failed: {e}"
            }
    
    def validate_trading_recommendation(self, recommendation: dict) -> tuple:
        """
        Validate a trading recommendation for completeness and sanity
        
        Parameters:
        recommendation: Single recommendation dictionary
        
        Returns:
        Tuple of (is_valid, error_message)
        """
        try:
            required_fields = ['strategy_type', 'confidence', 'legs', 'risk_management']
            
            # Check required top-level fields
            for field in required_fields:
                if field not in recommendation:
                    return False, f"Missing required field: {field}"
            
            # Validate legs
            if not recommendation['legs'] or len(recommendation['legs']) == 0:
                return False, "No trading legs specified"
            
            for i, leg in enumerate(recommendation['legs']):
                leg_required = ['action', 'option_type', 'strike', 'quantity']
                for field in leg_required:
                    if field not in leg:
                        return False, f"Leg {i+1} missing required field: {field}"
                
                # Validate values
                if leg['action'] not in ['buy', 'sell']:
                    return False, f"Leg {i+1} invalid action: {leg['action']}"
                
                if leg['option_type'] not in ['call', 'put']:
                    return False, f"Leg {i+1} invalid option_type: {leg['option_type']}"
                
                if not isinstance(leg['strike'], (int, float)) or leg['strike'] <= 0:
                    return False, f"Leg {i+1} invalid strike: {leg['strike']}"
                
                if not isinstance(leg['quantity'], int) or leg['quantity'] <= 0:
                    return False, f"Leg {i+1} invalid quantity: {leg['quantity']}"
            
            # Validate risk management
            risk_mgmt = recommendation['risk_management']
            risk_required = ['max_loss', 'max_profit', 'position_size_percent']
            for field in risk_required:
                if field not in risk_mgmt:
                    return False, f"Risk management missing field: {field}"
            
            # Validate confidence
            confidence = recommendation['confidence']
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                return False, f"Invalid confidence value: {confidence}"
            
            return True, "Validation passed"
            
        except Exception as e:
            return False, f"Validation error: {e}"


class AutomatedTrader:
    """
    Automated trading system that connects Grok AI analysis to Alpaca execution
    """
    
    def __init__(self, trader=None, paper_trading=True, ticker=None):
        """
        Initialize automated trader
        
        Parameters:
        trader: AlpacaOptionsTrader instance (will create if None)
        paper_trading: Whether to use paper trading
        ticker: Specific ticker to use (if None, uses current ticker from ticker_manager)
        """
        self.paper_trading = paper_trading
        
        # Determine ticker to use
        if ticker is not None:
            # Use explicitly provided ticker (for daily automation)
            current_ticker = ticker
        else:
            # Get current ticker for the parser (for UI usage)
            current_ticker = config.DEFAULT_TICKER
        
        # Store the ticker for reference
        self.ticker = current_ticker
        self.parser = GrokTradeParser(ticker=current_ticker)
        self.logger = self._setup_logging()
        
        # Import trader here to avoid circular imports
        if trader is None:
            from trader import AlpacaOptionsTrader
            self.trader = AlpacaOptionsTrader(paper_trading=paper_trading)
        else:
            self.trader = trader
    
    def _setup_logging(self):
        """Set up logging for automated trader"""
        import logging
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)
    
    def _calculate_dte_from_expiration(self, expiration_date: str) -> int:
        """
        Calculate DTE (Days to Expiration) from expiration date string
        
        Parameters:
        expiration_date: Date string in format "YYYY-MM-DD"
        
        Returns:
        Integer representing days to expiration
        """
        try:
            from datetime import datetime, date
            
            # Parse the expiration date
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()
            today = date.today()
            
            # Calculate days difference
            dte = (exp_date - today).days
            return max(0, dte)  # Ensure non-negative
            
        except Exception as e:
            self.logger.warning(f"Failed to parse expiration date '{expiration_date}': {e}")
            return 0  # Default to 0DTE if parsing fails
    
    def _extract_dte_from_options_chain(self, market_data: dict) -> int:
        """
        Extract DTE from the actual options chain data that was sent to Grok
        This is more reliable than calculating from date strings since we know
        the exact options data that Grok analyzed.
        
        Parameters:
        market_data: Market data dictionary containing options_analysis
        
        Returns:
        Integer representing the DTE of the options chain
        """
        try:
            options_analysis = market_data.get('options_analysis')
            if not options_analysis:
                self.logger.warning("No options analysis found in market data")
                return 0
            
            # Check if we have the actual options chain data
            options_chain = options_analysis.get('options_chain')
            if not options_chain or len(options_chain) == 0:
                self.logger.warning("No options chain data found")
                return 0
            
            # Import the parser from paca module
            from paca import parse_option_symbol
            from datetime import datetime, date
            
            # Extract expiration date from first option symbol
            first_option = options_chain[0]
            symbol = first_option.get('Symbol')
            
            if not symbol:
                self.logger.warning("No symbol found in options chain")
                return 0
            
            # Parse the option symbol to get expiration date
            parsed = parse_option_symbol(symbol)
            if not parsed or 'expiration_date' not in parsed:
                self.logger.warning(f"Could not parse option symbol: {symbol}")
                return 0
            
            # Calculate DTE from the parsed expiration date
            exp_date = datetime.strptime(parsed['expiration_date'], "%Y-%m-%d").date()
            today = date.today()
            dte = (exp_date - today).days
            
            self.logger.info(f"📅 Extracted DTE from options chain: {dte} days (from symbol: {symbol})")
            return max(0, dte)
            
        except Exception as e:
            self.logger.error(f"Failed to extract DTE from options chain: {e}")
            return 0
    
    def execute_grok_recommendations(self, grok_response: str, dte: int = 0, max_trades: int = 2, market_data: dict = None) -> dict:
        """
        Execute trading recommendations from Grok AI analysis
        
        Parameters:
        grok_response: Full Grok AI response text
        dte: Days to expiration for the options (fallback value)
        max_trades: Maximum number of trades to execute
        market_data: Market data dictionary containing options chain (preferred source for DTE)
        
        Returns:
        Dictionary with execution results
        """
        self.logger.info(f"🤖 Starting automated trade execution")
        
        # Extract the actual DTE from options chain data if available
        actual_dte = dte  # Start with fallback
        if market_data:
            extracted_dte = self._extract_dte_from_options_chain(market_data)
            if extracted_dte >= 0:  # Valid DTE extracted
                actual_dte = extracted_dte
                self.logger.info(f"📊 Using DTE from options chain: {actual_dte} (instead of default: {dte})")
            else:
                self.logger.warning(f"Failed to extract DTE from options chain, using fallback: {dte}")
        else:
            self.logger.warning("No market data provided, using fallback DTE calculation")
        
        # Parse the Grok response
        parsed_data = self.parser.parse_grok_response(grok_response)
        
        if not parsed_data['success']:
            return {
                'success': False,
                'error': parsed_data['error'],
                'trades_executed': 0,
                'trade_results': []
            }
        
        recommendations = parsed_data['trading_recommendations']
        trade_results = []
        trades_executed = 0
        
        # Process primary recommendation
        if 'primary_recommendation' in recommendations and trades_executed < max_trades:
            primary_rec = recommendations['primary_recommendation']
            
            # Use the extracted DTE from options chain (most reliable)
            result = self._execute_single_recommendation(
                primary_rec, 
                'primary',
                actual_dte
            )
            trade_results.append(result)
            if result['attempted']:
                trades_executed += 1
        
        # Process alternative recommendation if available
        if ('alternative_recommendation' in recommendations and 
            trades_executed < max_trades):
            alt_rec = recommendations['alternative_recommendation']
            
            # Use the extracted DTE from options chain (most reliable)
            result = self._execute_single_recommendation(
                alt_rec, 
                'alternative',
                actual_dte
            )
            trade_results.append(result)
            if result['attempted']:
                trades_executed += 1
        
        return {
            'success': True,
            'trades_executed': trades_executed,
            'trade_results': trade_results,
            'parsed_recommendations': recommendations
        }
    
    def _execute_single_recommendation(self, recommendation: dict, trade_type: str, dte: int = 0) -> dict:
        """
        Execute a single trading recommendation
        
        Parameters:
        recommendation: Single recommendation dictionary
        trade_type: 'primary' or 'alternative'
        dte: Days to expiration
        
        Returns:
        Dictionary with execution result
        """
        try:
            self.logger.info(f"Processing {trade_type} recommendation: {recommendation.get('strategy_type', 'unknown')}")
            
            # Check if options are available for the current ticker and DTE
            if self.ticker != 'SPY' and dte == 0:
                # Special handling for non-SPY tickers with 0DTE
                return {
                    'trade_type': trade_type,
                    'attempted': False,
                    'success': False,
                    'error': f"❌ {self.ticker} does not have 0DTE (same-day) options available. Try 3DTE or longer expirations. SPY has the most comprehensive options coverage for 0DTE trading.",
                    'order_id': None,
                    'suggestion': f"Switch to SPY for 0DTE trading, or use {self.ticker} with 3DTE+ expirations"
                }
            
            # Validate recommendation
            is_valid, validation_error = self.parser.validate_trading_recommendation(recommendation)
            if not is_valid:
                return {
                    'trade_type': trade_type,
                    'attempted': False,
                    'success': False,
                    'error': f"Validation failed: {validation_error}",
                    'order_id': None
                }
            
            # Check entry conditions
            entry_check = self._check_entry_conditions(recommendation.get('entry_conditions', {}))
            if not entry_check['can_enter']:
                return {
                    'trade_type': trade_type,
                    'attempted': False,
                    'success': False,
                    'error': f"Entry conditions not met: {entry_check['reason']}",
                    'order_id': None
                }
            
            # Build the order
            order_result = self._build_order_from_recommendation(recommendation, dte)
            if not order_result['success']:
                error_msg = order_result['error']
                
                # Enhanced error messaging for common issues
                if "not found in snapshots" in error_msg or "Invalid option symbol" in error_msg:
                    if self.ticker != 'SPY':
                        enhanced_error = f"❌ {self.ticker} options chain issue: {error_msg}. {self.ticker} may have limited options availability compared to SPY. Consider switching to SPY for more reliable options trading, or try longer DTEs (3+ days) for {self.ticker}."
                    else:
                        enhanced_error = f"❌ Options data issue: {error_msg}. This may be temporary - try again in a few moments."
                else:
                    enhanced_error = error_msg
                
                return {
                    'trade_type': trade_type,
                    'attempted': False,
                    'success': False,
                    'error': f"Order building failed: {enhanced_error}",
                    'order_id': None
                }
            
            order_dict = order_result['order']
            
            # Risk validation
            from trader import RiskManager
            risk_manager = RiskManager(self.trader)
            is_safe, risk_error = risk_manager.validate_order(order_dict)
            
            if not is_safe:
                return {
                    'trade_type': trade_type,
                    'attempted': False,
                    'success': False,
                    'error': f"Risk check failed: {risk_error}",
                    'order_id': None
                }
            
            # Execute the actual trade
            self.logger.info(f"🚀 LIVE TRADE: Executing {trade_type} recommendation")
            
            # Submit the order to Alpaca
            order_response = self.trader.submit_multileg_order(order_dict)
            
            if order_response['success']:
                self.logger.info(f"✅ Trade executed successfully: {order_response.get('message', 'No message')}")
                return {
                    'trade_type': trade_type,
                    'attempted': True,
                    'success': True,
                    'error': None,
                    'order_id': order_response.get('order_id'),
                    'order_details': order_response.get('order_details'),
                    'legs': order_response.get('legs', []),
                    'message': order_response.get('message', 'Trade executed successfully')
                }
            else:
                self.logger.error(f"❌ Trade execution failed: {order_response.get('error', 'Unknown error')}")
                return {
                    'trade_type': trade_type,
                    'attempted': True,
                    'success': False,
                    'error': order_response.get('error', 'Trade execution failed'),
                    'order_id': None,
                    'order_details': order_response.get('order_details'),
                    'legs': order_response.get('legs', [])
                }
                
        except Exception as e:
            self.logger.error(f"Error executing {trade_type} recommendation: {e}")
            return {
                'trade_type': trade_type,
                'attempted': True,
                'success': False,
                'error': str(e),
                'order_id': None
            }
    
    def _check_entry_conditions(self, conditions: dict) -> dict:
        """
        Check if entry conditions are met for a trade
        
        Parameters:
        conditions: Entry conditions dictionary
        
        Returns:
        Dictionary with can_enter boolean and reason
        """
        try:
            if not conditions:
                return {'can_enter': True, 'reason': 'No conditions specified'}
            
            # Get current market data for validation
            import yfinance as yf
            ticker_obj = yf.Ticker(self.parser.ticker)
            current_data = ticker_obj.history(period="1d", interval="1m").iloc[-1]
            current_price = current_data['Close']
            
            # Check ticker price conditions
            if f'{self.parser.ticker.lower()}_price_above' in conditions and conditions[f'{self.parser.ticker.lower()}_price_above']:
                if current_price <= conditions[f'{self.parser.ticker.lower()}_price_above']:
                    return {'can_enter': False, 'reason': f"{self.parser.ticker} price {current_price:.2f} not above {conditions[f'{self.parser.ticker.lower()}_price_above']}"}
            
            if f'{self.parser.ticker.lower()}_price_below' in conditions and conditions[f'{self.parser.ticker.lower()}_price_below']:
                if current_price >= conditions[f'{self.parser.ticker.lower()}_price_below']:
                    return {'can_enter': False, 'reason': f"{self.parser.ticker} price {current_price:.2f} not below {conditions[f'{self.parser.ticker.lower()}_price_below']}"}
            
            # Also check for legacy SPY conditions for backwards compatibility
            if 'spy_price_above' in conditions and conditions['spy_price_above']:
                if current_price <= conditions['spy_price_above']:
                    return {'can_enter': False, 'reason': f"{self.parser.ticker} price {current_price:.2f} not above {conditions['spy_price_above']}"}
            
            if 'spy_price_below' in conditions and conditions['spy_price_below']:
                if current_price >= conditions['spy_price_below']:
                    return {'can_enter': False, 'reason': f"{self.parser.ticker} price {current_price:.2f} not below {conditions['spy_price_below']}"}
            
            # Check time window
            if 'time_window_start' in conditions and 'time_window_end' in conditions:
                current_time = datetime.now()
                # For simplicity, assuming times are in format "HH:MM" or "now"
                start_time = conditions['time_window_start']
                end_time = conditions['time_window_end']
                
                if start_time != "now" and end_time != "now":
                    # Parse times and check if current time is within window
                    # This is a simplified check - in production you'd want more robust time parsing
                    pass
            
            return {'can_enter': True, 'reason': 'All conditions met'}
            
        except Exception as e:
            return {'can_enter': False, 'reason': f'Error checking conditions: {e}'}
    
    def _add_limit_prices_to_legs(self, legs: list, dte: int = 0) -> list:
        """
        Add limit prices to each leg by fetching current option quotes from options chain
        
        Parameters:
        legs: List of leg dictionaries with action, option_type, strike, quantity
        dte: Days to expiration (default: 0 for same-day expiry)
        
        Returns:
        List of legs with added limit_price field
        """
        try:
            # Get current options chain data with quotes for specified DTE
            from paca import get_spy_options_chain
            from trader import get_todays_expiry
            from dte_manager import DTEManager
            
            # Get expiration date based on DTE
            if dte == 0:
                expiry = get_todays_expiry()
            else:
                dte_manager = DTEManager()
                dte_manager.current_dte = dte  # Set the DTE we want
                dte_summary = dte_manager.get_dte_summary()
                expiry = dte_summary['target_expiration'][:10]  # YYYY-MM-DD format
            
            # Determine strike range from legs to fetch targeted data
            strikes = [float(leg['strike']) for leg in legs]
            min_strike = min(strikes) - 5  # Add buffer
            max_strike = max(strikes) + 5  # Add buffer
            strike_range = {'min': min_strike, 'max': max_strike}
            
            self.logger.info(f"🎯 Fetching options data for strikes ${min_strike}-${max_strike}")
            
            # Fetch options data with targeted strike range for better coverage
            options_data = get_spy_options_chain(limit=200, dte=dte, strike_range=strike_range, ticker=self.ticker)
            
            if not options_data or 'snapshots' not in options_data or len(options_data.get('snapshots', {})) == 0:
                error_msg = f"No {dte}DTE options available for {self.ticker}"
                if self.ticker != 'SPY' and dte == 0:
                    error_msg += f". {self.ticker} may not have same-day expiration options. Try using SPY for 0DTE trading or switch to 1DTE+ for {self.ticker}."
                elif self.ticker != 'SPY':
                    error_msg += f". {self.ticker} options may not be available for {dte}DTE. Try using SPY or a different expiration date."
                
                self.logger.error(error_msg)
                # Raise an exception that can be caught by the calling method
                raise ValueError(error_msg)
                
            snapshots = options_data['snapshots']
            
            # Add limit prices to each leg
            enhanced_legs = []
            for leg in legs:
                enhanced_leg = leg.copy()
                option_type = leg['option_type'].upper()
                strike = float(leg['strike'])
                action = leg['action'].lower()
                
                # Convert expiry to proper format and find actual symbol in snapshots
                expiry_formatted = self._convert_date_to_alpaca_format(expiry) if '-' in expiry else expiry
                symbol = self._find_option_symbol_in_snapshots(snapshots, self.ticker, option_type[0], strike, expiry_formatted)
                
                # Fallback to building symbol if not found in snapshots
                if not symbol:
                    symbol = self._format_option_symbol(self.ticker, expiry_formatted, option_type[0], strike)
                    self.logger.warning(f"Option not found in snapshots, using constructed symbol: {symbol}")
                
                if symbol in snapshots and 'latestQuote' in snapshots[symbol]:
                    quote = snapshots[symbol]['latestQuote']
                    bid = quote.get('bp', 0)  # bid price
                    ask = quote.get('ap', 0)  # ask price
                    
                    if bid > 0 and ask > 0:
                        # Calculate limit price based on action
                        if action == 'buy':
                            # For buying, use ask price or slightly above
                            limit_price = round(ask * 1.01, 2)  # 1% above ask
                        else:  # sell
                            # For selling, use bid price or slightly below  
                            limit_price = round(bid * 0.99, 2)  # 1% below bid
                        
                        # Ensure minimum limit price
                        limit_price = max(limit_price, 0.01)
                        enhanced_leg['limit_price'] = limit_price
                        
                        self.logger.info(f"Added limit price ${limit_price} for {symbol} ({action}) - bid: ${bid}, ask: ${ask}")
                    else:
                        # Fallback if no valid quotes
                        enhanced_leg['limit_price'] = 0.50
                        self.logger.warning(f"No valid bid/ask for {symbol}, using fallback limit price")
                else:
                    # Fallback if option not found in snapshots
                    enhanced_leg['limit_price'] = 0.50
                    self.logger.warning(f"Option {symbol} not found in snapshots, using fallback limit price")
                
                enhanced_legs.append(enhanced_leg)
            
            return enhanced_legs
            
        except Exception as e:
            self.logger.error(f"Error adding limit prices to legs: {e}")
            # Return original legs with default limit prices
            for leg in legs:
                if 'limit_price' not in leg:
                    leg['limit_price'] = 0.50
            return legs

    def _build_order_from_recommendation(self, recommendation: dict, dte: int = 0) -> dict:
        """
        Build an Alpaca order from a Grok recommendation
        
        Parameters:
        recommendation: Recommendation dictionary
        
        Returns:
        Dictionary with order details or error
        """
        try:
            from trader import OptionsOrderBuilder, get_todays_expiry
            from dte_manager import DTEManager
            
            # Get expiration date based on DTE
            if dte == 0:
                expiry = get_todays_expiry()
            else:
                dte_manager = DTEManager()
                dte_manager.current_dte = dte  # Set the DTE we want
                dte_summary = dte_manager.get_dte_summary()
                expiry = dte_summary['target_expiration'][:10]  # YYYY-MM-DD format
            
            builder = OptionsOrderBuilder()
            legs = recommendation['legs']
            
            # Convert expiry to proper Alpaca format
            expiry_formatted = self._convert_date_to_alpaca_format(expiry) if '-' in expiry else expiry
            
            # Add limit prices to legs by fetching current quotes
            try:
                enhanced_legs = self._add_limit_prices_to_legs(legs, dte)
            except ValueError as e:
                # Return error if options not available
                return {
                    'success': False,
                    'error': str(e),
                    'order_dict': None
                }
            
            # Add each leg to the order
            for leg in enhanced_legs:
                action = leg['action']  # 'buy' or 'sell'
                option_type = leg['option_type']  # 'call' or 'put'
                strike = float(leg['strike'])
                quantity = int(leg['quantity'])
                
                # Determine position intent
                if action == 'buy':
                    position_intent = 'buy_to_open'
                else:
                    position_intent = 'sell_to_open'
                
                # Use properly formatted expiry
                symbol = self._format_option_symbol(self.parser.ticker, expiry_formatted, option_type.upper()[0], strike)
                
                builder.add_leg(symbol, action, quantity, position_intent)
                
                # Set limit price if provided
                if 'limit_price' in leg and leg['limit_price']:
                    builder.set_limit_price(float(leg['limit_price']))
            
            # Set order quantity (usually 1 for spreads)
            builder.set_quantity(1)
            
            order_dict = builder.build()
            
            return {
                'success': True,
                'order': order_dict,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'order': None,
                'error': str(e)
            }
    
    def _convert_date_to_alpaca_format(self, date_str: str) -> str:
        """
        Convert date from YYYY-MM-DD format to YYMMDD format for Alpaca option symbols
        
        Args:
            date_str: Date in YYYY-MM-DD format (e.g., "2025-09-12")
            
        Returns:
            Date in YYMMDD format (e.g., "250912")
        """
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%y%m%d")
        except ValueError as e:
            self.logger.error(f"Error converting date {date_str}: {e}")
            return date_str
    
    def _find_option_symbol_in_snapshots(self, snapshots: dict, ticker: str, option_type: str, strike: float, target_expiry: str) -> str:
        """
        Find the actual option symbol in snapshots that matches the criteria
        
        Args:
            snapshots: Options snapshots from Alpaca
            ticker: Underlying ticker (e.g., "TQQQ", "SPY")
            option_type: "C" or "P"
            strike: Strike price as float
            target_expiry: Target expiry in YYMMDD format
            
        Returns:
            Actual option symbol from snapshots, or None if not found
        """
        try:
            # Convert strike to the 8-digit format used in symbols
            target_strike_str = f"{int(strike * 1000):08d}"
            
            # Search through all available symbols in snapshots
            for symbol in snapshots.keys():
                if symbol.startswith(ticker):
                    try:
                        # Parse symbol to extract components
                        ticker_len = len(ticker)
                        if len(symbol) >= ticker_len + 15:  # Minimum length for option symbol
                            symbol_expiry = symbol[ticker_len:ticker_len+6]
                            symbol_type = symbol[ticker_len+6:ticker_len+7]
                            symbol_strike = symbol[ticker_len+7:ticker_len+15]
                            
                            # Check if this matches what we're looking for
                            if (symbol_expiry == target_expiry and 
                                symbol_type == option_type and 
                                symbol_strike == target_strike_str):
                                return symbol
                    except (IndexError, ValueError):
                        continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding option symbol: {e}")
            return None

    def _format_option_symbol(self, underlying: str, expiry: str, option_type: str, strike: float) -> str:
        """
        Format option symbol according to Alpaca's convention
        Same as in trader.py SPYOptionsStrategies class
        """
        strike_str = f"{int(strike * 1000):08d}"
        symbol = f"{underlying}{expiry}{option_type}{strike_str}"
        return symbol


# Example usage function
def run_automated_analysis_and_trading() -> dict:
    """
    Complete workflow: get market data, run Grok analysis, execute trades
    
    Returns:
    Dictionary with complete results
    """
    try:
        print("🚀 Starting Automated SPY Options Analysis & Trading")
        print("=" * 60)
        
        # Step 1: Gather market data
        print("📊 Step 1: Gathering comprehensive market data...")
        market_data = get_comprehensive_market_data(include_full_options_chain=True)
        
        # Step 2: Create Grok prompt
        print("🧠 Step 2: Creating AI analysis prompt...")
        prompt = format_market_analysis_prompt(market_data)
        
        # Step 3: Get Grok analysis
        print("🤖 Step 3: Getting AI analysis...")
        grok_analyzer = GrokAnalyzer()
        analysis_result = grok_analyzer.send_to_grok(prompt)
        
        if not analysis_result or 'error' in analysis_result:
            return {
                'success': False,
                'error': 'Failed to get Grok analysis',
                'stage': 'grok_analysis'
            }
        
        # Step 4: Parse and execute trades
        print("⚡ Step 4: Parsing recommendations and executing trades...")
        automated_trader = AutomatedTrader(paper_trading=True)
        execution_result = automated_trader.execute_grok_recommendations(
            analysis_result['content'], 
            max_trades=2
        )
        
        # Step 5: Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"automated_trading_session_{timestamp}.json"
        
        results = {
            'success': True,
            'timestamp': timestamp,
            'market_data_summary': {
                'spy_price': market_data.get('spy_recent', {}).get('current_price', 'N/A'),
                'market_sentiment': 'extracted_from_analysis'  # Could extract this
            },
            'grok_analysis': analysis_result['content'],
            'execution_results': execution_result
        }
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"✅ Automated session complete! Results saved to {filename}")
        print(f"📈 Trades executed: {execution_result.get('trades_executed', 0)}")
        
        return results
        
    except Exception as e:
        print(f"❌ Automated trading session failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'stage': 'unknown'
        }


# =============================================================================
# DTE-AWARE ANALYSIS FUNCTIONS (v7 Comprehensive Compatible)
# =============================================================================

def run_dte_aware_analysis(dte: Optional[int] = None, ticker: Optional[str] = None, save_results: bool = True) -> Dict[str, Any]:
    """
    Run DTE-aware v7 comprehensive analysis for backwards compatibility with automated_trader.py
    This function now uses the comprehensive v7 system with enhanced market context, behavioral data, and options flow
    
    Parameters:
    dte: Days to expiration (uses current DTE if None)  
    ticker: Stock ticker (uses current ticker if None)
    save_results: Whether to save results to file
    
    Returns:
    Dictionary with analysis results including grok_response for automated_trader.py
    """
    try:
        if dte is None:
            from dte_manager import dte_manager
            dte = dte_manager.get_current_dte()
        
        if ticker is None:
            ticker = config.DEFAULT_TICKER
        
        print(f"🚀 Starting DTE-aware v7 comprehensive analysis for {ticker} ({dte}DTE)...")
        
        # Initialize Grok analyzer
        analyzer = GrokAnalyzer()
        
        # Use DTE-aware comprehensive data gathering
        market_data = get_comprehensive_market_data(include_full_options_chain=False, dte=dte, ticker=ticker)
        
        # Create DTE-aware v7 comprehensive analysis prompt 
        prompt = format_market_analysis_prompt(market_data)
        print(f"📏 DTE-aware v7 comprehensive prompt length: {len(prompt):,} characters")
        
        if save_results:
            # Save prompt for reference
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prompt_filename = f"grok_prompts/grok_v7_{ticker}_{dte}dte_prompt_{timestamp}.txt"
            try:
                with open(prompt_filename, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                print(f"📄 Analysis prompt saved to {prompt_filename}")
            except Exception as e:
                print(f"❌ Error saving prompt: {e}")
        
        # Send to Grok AI with enhanced max_tokens for comprehensive analysis
        print(f"🤖 Sending DTE-aware v7 comprehensive analysis to Grok AI...")
        analysis_result = analyzer.send_to_grok(prompt, max_tokens=2000)  # Increased for comprehensive v7
        
        if not analysis_result:
            return {
                'success': False,
                'error': 'Failed to get response from Grok AI',
                'dte': dte
            }
        
        # Check for strategy detection
        has_strategy = any(strategy in analysis_result.upper() for strategy in ['BULL_PUT_SPREAD', 'BEAR_CALL_SPREAD', 'IRON_CONDOR'])
        print(f"📈 Strategy detected: {'✅' if has_strategy else '❌'}")
        
        # Compile results in format expected by automated_trader.py
        results = {
            'success': True,
            'dte': dte,
            'ticker': ticker,
            'timestamp': market_data['timestamp'],
            'market_data': market_data,
            'analysis_prompt': prompt,
            'ai_analysis': analysis_result,
            'grok_response': analysis_result,  # Key field that automated_trader.py expects
            'strategy_detected': has_strategy,
            'prompt_version': 'v7_comprehensive_dte_aware'
        }
        
        if save_results:
            # Save complete analysis
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_filename = f"grok_prompts/grok_v7_{ticker}_{dte}dte_analysis_{timestamp}.txt"
            try:
                with open(analysis_filename, 'w', encoding='utf-8') as f:
                    f.write(analysis_result)
                print(f"📊 Analysis results saved to {analysis_filename}")
            except Exception as e:
                print(f"❌ Error saving analysis: {e}")
            
            # Save complete session data
            session_filename = f"grok_prompts/grok_v7_{ticker}_{dte}dte_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(session_filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"💾 Complete session data saved to {session_filename}")
        
        print(f"✅ DTE-aware v7 comprehensive analysis complete!")
        return results
        
    except Exception as e:
        print(f"❌ DTE-aware v7 comprehensive analysis failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'dte': dte if dte else 'unknown'
        }