"""
Trade Integration Module for SimpleZero
======================================

This module connects Grok AI responses with the trader module and database storage.
It processes JSON trade recommendations from Grok, parses them into trade signals,
and stores both the raw responses and parsed trades in the database for persistence.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import db_storage
from trader import GrokResponseParser, GrokTradeSignal, StrategyType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_grok_response(grok_response: str, ticker: str = None, dte: int = None, 
                          user_id: str = None, session_id: str = None) -> Dict[str, Any]:
    """
    Process a Grok AI response - parse it, store it, and prepare it for trading.
    
    This is the main integration function between Grok AI and the trading system.
    It handles parsing the response, storing both the raw response and parsed trade
    in the database, and returning everything needed for trade execution.
    
    Args:
        grok_response: Raw response from Grok AI
        ticker: The ticker symbol (e.g., 'SPY')
        dte: Days to expiration
        user_id: User ID for database storage
        session_id: Session ID for database storage (fallback if no user_id)
        
    Returns:
        Dict containing:
            success: Whether processing was successful
            raw_response: The original Grok response
            parsed_trade: The parsed trade signal (if parsing succeeded)
            error: Error message (if any)
    """
    try:
        # 1. Parse the Grok response
        parser = GrokResponseParser()
        trade_signal = parser.parse_grok_response(grok_response)
        
        timestamp = datetime.now().isoformat()
        
        # 2. Store the raw Grok response
        raw_response_data = {
            'timestamp': timestamp,
            'ticker': ticker,
            'dte': dte,
            'response': grok_response
        }
        
        db_storage.store_data(
            data_type='grok_raw_response',
            data=raw_response_data,
            user_id=user_id,
            session_id=session_id,
            ticker=ticker,
            dte=dte
        )
        
        # 3. If parsing succeeded, store the parsed trade
        if trade_signal:
            # Convert the trade signal to a dict for storage
            trade_dict = {
                'timestamp': timestamp,
                'ticker': ticker or trade_signal.underlying_symbol,
                'dte': dte,
                'strategy_type': trade_signal.strategy_type.value if hasattr(trade_signal.strategy_type, 'value') else str(trade_signal.strategy_type),
                'confidence': trade_signal.confidence,
                'market_bias': trade_signal.market_bias,
                'support_level': trade_signal.support_level,
                'resistance_level': trade_signal.resistance_level,
                'volatility_factor': trade_signal.volatility_factor,
                'underlying_symbol': trade_signal.underlying_symbol,
                'short_strike': trade_signal.short_strike,
                'long_strike': trade_signal.long_strike,
                'credit_received': trade_signal.credit_received,
                'expiration': trade_signal.expiration,
                'max_profit': trade_signal.max_profit,
                'max_loss': trade_signal.max_loss,
                'probability_of_profit': trade_signal.probability_of_profit,
                'reward_risk_ratio': trade_signal.reward_risk_ratio,
                'delta': trade_signal.delta,
                'theta': trade_signal.theta,
                'expected_profit': trade_signal.expected_profit,
                'entry_conditions': trade_signal.entry_conditions,
                'reasoning': trade_signal.reasoning
            }
            
            db_storage.store_data(
                data_type='parsed_trade',
                data=trade_dict,
                user_id=user_id,
                session_id=session_id,
                ticker=ticker or trade_signal.underlying_symbol,
                dte=dte
            )
            
            return {
                'success': True,
                'raw_response': grok_response,
                'parsed_trade': trade_dict
            }
        else:
            logger.warning("⚠️ Failed to parse trade signal from Grok response")
            return {
                'success': False,
                'raw_response': grok_response,
                'parsed_trade': None,
                'error': 'Failed to parse trade signal from Grok response'
            }
    
    except Exception as e:
        logger.error(f"❌ Error processing Grok response: {e}")
        return {
            'success': False,
            'raw_response': grok_response,
            'parsed_trade': None,
            'error': str(e)
        }

def get_latest_trade_recommendation(user_id: str = None, session_id: str = None) -> Dict[str, Any]:
    """
    Get the latest trade recommendation from the database
    
    Args:
        user_id: User ID
        session_id: Session ID (fallback if no user_id)
        
    Returns:
        Dict containing:
            raw_response: The raw Grok response
            parsed_trade: The parsed trade signal
            success: Whether both were found
    """
    try:
        # Get the latest raw response
        raw_response = db_storage.get_latest_data('grok_raw_response', user_id=user_id, session_id=session_id)
        
        # Get the latest parsed trade
        parsed_trade = db_storage.get_latest_data('parsed_trade', user_id=user_id, session_id=session_id)
        
        return {
            'raw_response': raw_response,
            'parsed_trade': parsed_trade,
            'success': bool(raw_response and parsed_trade)
        }
    
    except Exception as e:
        logger.error(f"❌ Error getting latest trade recommendation: {e}")
        return {
            'success': False,
            'error': str(e)
        }