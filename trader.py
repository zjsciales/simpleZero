"""
Automated Options Trading System
================================

This module handles automated trading based on Grok AI analysis, including:
- Parsing Grok JSON responses
- Creating complex options spreads
- Managing OTOCO (One-Triggers-One-Cancels-Other) orders
- WebSocket monitoring for real-time order updates
- Risk management and position tracking
"""

import json
import asyncio
import websockets
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import requests

# Import our TastyTrade integration
from tt import get_authenticated_headers, get_current_account_number
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyType(Enum):
    """Supported strategy types from Grok AI"""
    BULL_PUT_SPREAD = "BULL_PUT_SPREAD"
    BEAR_CALL_SPREAD = "BEAR_CALL_SPREAD"
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"

class OrderStatus(Enum):
    """Order status tracking"""
    PENDING = "PENDING"
    ROUTED = "ROUTED"
    LIVE = "LIVE"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class GrokTradeSignal:
    """Parsed Grok AI trade signal"""
    strategy_type: StrategyType
    confidence: int
    market_bias: str
    support_level: float
    resistance_level: float
    volatility_factor: str
    
    # Trade setup details
    short_strike: float
    long_strike: float
    credit_received: float
    expiration: str
    max_profit: float
    max_loss: float
    
    # Risk metrics
    probability_of_profit: float
    reward_risk_ratio: float
    delta: float
    theta: float
    expected_profit: float
    
    # Entry conditions
    entry_conditions: Dict[str, Any]
    reasoning: str

@dataclass
class OptionsLeg:
    """Individual options leg for complex orders"""
    symbol: str  # Full options symbol (e.g., "SPY  250923P00664000")
    action: str  # "Buy to Open", "Sell to Open", etc.
    quantity: int
    instrument_type: str = "Equity Option"

@dataclass
class SpreadOrder:
    """Complex options spread order"""
    underlying_symbol: str
    legs: List[OptionsLeg]
    order_type: str = "Limit"
    time_in_force: str = "Day"
    price: float = None
    price_effect: str = "Credit"  # or "Debit"

class GrokResponseParser:
    """Parse Grok AI JSON responses into trade signals"""
    
    @staticmethod
    def parse_grok_response(grok_response: str) -> Optional[GrokTradeSignal]:
        """
        Parse Grok AI response text and extract JSON trade signal
        
        Args:
            grok_response: Raw text response from Grok AI
            
        Returns:
            GrokTradeSignal object or None if parsing fails
        """
        try:
            # Extract JSON from the response text
            json_start = grok_response.find('{')
            json_end = grok_response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error("No JSON found in Grok response")
                return None
            
            json_str = grok_response[json_start:json_end]
            trade_data = json.loads(json_str)
            
            # Parse the trade setup
            trade_setup = trade_data.get('trade_setup', {})
            risk_metrics = trade_data.get('risk_metrics', {})
            entry_conditions = trade_data.get('entry_conditions', {})
            
            return GrokTradeSignal(
                strategy_type=StrategyType(trade_data.get('strategy_type')),
                confidence=trade_data.get('confidence', 0),
                market_bias=trade_data.get('market_bias', ''),
                support_level=trade_data.get('support_level', 0.0),
                resistance_level=trade_data.get('resistance_level', 0.0),
                volatility_factor=trade_data.get('volatility_factor', ''),
                
                short_strike=trade_setup.get('short_put_strike', 0.0),
                long_strike=trade_setup.get('long_put_strike', 0.0),
                credit_received=trade_setup.get('credit_received', 0.0),
                expiration=trade_setup.get('expiration', ''),
                max_profit=trade_setup.get('max_profit', 0.0),
                max_loss=trade_setup.get('max_loss', 0.0),
                
                probability_of_profit=risk_metrics.get('probability_of_profit', 0.0),
                reward_risk_ratio=risk_metrics.get('reward_risk_ratio', 0.0),
                delta=risk_metrics.get('delta', 0.0),
                theta=risk_metrics.get('theta', 0.0),
                expected_profit=risk_metrics.get('expected_profit', 0.0),
                
                entry_conditions=entry_conditions,
                reasoning=trade_data.get('reasoning', '')
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse Grok response: {e}")
            return None

class OptionsSymbolBuilder:
    """Build TastyTrade options symbols from strike/expiration data"""
    
    @staticmethod
    def build_options_symbol(underlying: str, expiration: str, option_type: str, strike: float) -> str:
        """
        Build TastyTrade options symbol format
        
        Args:
            underlying: Underlying symbol (e.g., "SPY")
            expiration: Expiration date (e.g., "2025-09-23")
            option_type: "P" for Put, "C" for Call
            strike: Strike price (e.g., 664.0)
            
        Returns:
            Full options symbol (e.g., "SPY  250923P00664000")
        """
        try:
            # Parse expiration date
            exp_date = datetime.strptime(expiration, "%Y-%m-%d")
            
            # Format date as YYMMDD
            date_str = exp_date.strftime("%y%m%d")
            
            # Format strike price (8 digits with 3 decimal places, but no decimal point)
            strike_str = f"{int(strike * 1000):08d}"
            
            # Build symbol: UNDERLYING + spaces + YYMMDD + P/C + 8-digit strike
            symbol = f"{underlying:<6}{date_str}{option_type}{strike_str}"
            
            return symbol
            
        except Exception as e:
            logger.error(f"Failed to build options symbol: {e}")
            return ""

class SpreadTradeBuilder:
    """Build complex spread trades from Grok signals"""
    
    @staticmethod
    def build_bull_put_spread(signal: GrokTradeSignal, underlying: str = "SPY") -> SpreadOrder:
        """
        Build a Bull Put Spread order from Grok signal
        
        Args:
            signal: Parsed Grok trade signal
            underlying: Underlying symbol
            
        Returns:
            SpreadOrder for bull put spread
        """
        symbol_builder = OptionsSymbolBuilder()
        
        # Build option symbols
        short_put_symbol = symbol_builder.build_options_symbol(
            underlying, signal.expiration, "P", signal.short_strike
        )
        long_put_symbol = symbol_builder.build_options_symbol(
            underlying, signal.expiration, "P", signal.long_strike
        )
        
        # Create legs for bull put spread
        legs = [
            OptionsLeg(
                symbol=short_put_symbol,
                action="Sell to Open",
                quantity=1
            ),
            OptionsLeg(
                symbol=long_put_symbol,
                action="Buy to Open", 
                quantity=1
            )
        ]
        
        return SpreadOrder(
            underlying_symbol=underlying,
            legs=legs,
            price=signal.credit_received,
            price_effect="Credit"
        )

class TastyTradeAPI:
    """TastyTrade API integration for order management"""
    
    def __init__(self):
        self.base_url = "https://api.tastyworks.com"
        self.account_number = None
        
    def get_headers(self) -> Dict[str, str]:
        """Get authenticated headers for API requests"""
        return get_authenticated_headers()
    
    def get_account_number(self) -> str:
        """Get current account number"""
        if not self.account_number:
            self.account_number = get_current_account_number()
        return self.account_number
    
    def submit_spread_order(self, spread_order: SpreadOrder) -> Optional[Dict]:
        """
        Submit a complex spread order to TastyTrade
        
        Args:
            spread_order: SpreadOrder object
            
        Returns:
            Order response data or None if failed
        """
        try:
            headers = self.get_headers()
            account_number = self.get_account_number()
            
            if not headers or not account_number:
                logger.error("Missing authentication or account number")
                return None
            
            # Build order payload
            payload = {
                "time-in-force": spread_order.time_in_force,
                "order-type": spread_order.order_type,
                "price-effect": spread_order.price_effect,
                "legs": []
            }
            
            # Add price if specified
            if spread_order.price:
                payload["price"] = spread_order.price
            
            # Add legs
            for leg in spread_order.legs:
                payload["legs"].append({
                    "instrument-type": leg.instrument_type,
                    "symbol": leg.symbol,
                    "quantity": leg.quantity,
                    "action": leg.action
                })
            
            # Submit order
            url = f"{self.base_url}/accounts/{account_number}/orders"
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 201:
                logger.info(f"✅ Successfully submitted spread order")
                return response.json()
            else:
                logger.error(f"❌ Failed to submit order: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting spread order: {e}")
            return None

def test_grok_parsing():
    """Test function to parse the example Grok response"""
    
    # Load the example response
    try:
        with open('/Users/zach/Documents/GitHub/simpleZero/example_grok_response.txt', 'r') as f:
            example_response = f.read()
        
        print("📋 Testing Grok Response Parser...")
        print("=" * 50)
        
        # Parse the response
        parser = GrokResponseParser()
        signal = parser.parse_grok_response(example_response)
        
        if signal:
            print("✅ Successfully parsed Grok response!")
            print(f"Strategy: {signal.strategy_type.value}")
            print(f"Confidence: {signal.confidence}%")
            print(f"Market Bias: {signal.market_bias}")
            print(f"Short Strike: ${signal.short_strike}")
            print(f"Long Strike: ${signal.long_strike}")
            print(f"Credit Received: ${signal.credit_received}")
            print(f"Max Profit: ${signal.max_profit}")
            print(f"Max Loss: ${signal.max_loss}")
            print(f"Probability of Profit: {signal.probability_of_profit}%")
            
            # Build the spread order
            print("\n🔧 Building Bull Put Spread Order...")
            print("=" * 50)
            
            builder = SpreadTradeBuilder()
            spread_order = builder.build_bull_put_spread(signal)
            
            print(f"Underlying: {spread_order.underlying_symbol}")
            print(f"Price Effect: {spread_order.price_effect}")
            print(f"Credit: ${spread_order.price}")
            print("Legs:")
            for i, leg in enumerate(spread_order.legs, 1):
                print(f"  Leg {i}: {leg.action} {leg.quantity} {leg.symbol}")
            
            # Test symbol building
            print("\n🔗 Testing Options Symbol Builder...")
            print("=" * 50)
            
            symbol_builder = OptionsSymbolBuilder()
            test_symbol = symbol_builder.build_options_symbol("SPY", "2025-09-23", "P", 664.0)
            print(f"Example Symbol: {test_symbol}")
            
        else:
            print("❌ Failed to parse Grok response")
            
    except FileNotFoundError:
        print("❌ Example response file not found")
    except Exception as e:
        print(f"❌ Error during testing: {e}")

if __name__ == "__main__":
    # Run the test
    test_grok_parsing()
