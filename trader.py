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
from tt import get_authenticated_headers
import config

def get_current_account_number():
    """Get account number from TastyTrade API - Environment Aware"""
    try:
        # First check if we have an account number configured for current environment
        if config.TT_ACCOUNT_NUMBER:
            print(f"🏦 Using configured account number: {config.TT_ACCOUNT_NUMBER} ({config.ENVIRONMENT_NAME})")
            return config.TT_ACCOUNT_NUMBER
            
        # If not configured, try to fetch from API using unified environment API
        trading_api = TastyTradeAPI()
        headers = trading_api.get_trading_headers()
        
        if not headers:
            print("❌ Failed to get authenticated headers for account lookup")
            return None
            
        # Make API call to get accounts using the trading environment context
        accounts_url = f"{trading_api.base_url}/accounts"
        
        response = requests.get(accounts_url, headers=headers)
        if response.status_code == 200:
            accounts_data = response.json()
            if accounts_data and 'data' in accounts_data and accounts_data['data']:
                account_number = accounts_data['data'][0]['account']['account-number']
                print(f"🏦 Fetched account number from API: {account_number} ({config.TRADING_MODE})")
                return account_number
        
        print(f"❌ Failed to fetch account number from API. Status: {response.status_code}")
        return None
        
    except Exception as e:
        print(f"❌ Error getting account number: {e}")
        return None

class TradingEnvironmentManager:
    """Manages unified environment context for all operations"""
    
    @staticmethod
    def get_environment_context():
        """Get context for current environment (Local=Sandbox, Railway=Production)"""
        return {
            'base_url': config.TT_BASE_URL,
            'api_key': config.TT_API_KEY,
            'api_secret': config.TT_API_SECRET,
            'account_number': config.TT_ACCOUNT_NUMBER,
            'username': config.TT_USERNAME,
            'password': config.TT_PASSWORD,
            'environment': config.ENVIRONMENT_NAME
        }
    
    @staticmethod
    def log_environment_info():
        """Log the current unified environment configuration"""
        ctx = TradingEnvironmentManager.get_environment_context()
        
        logger.info("🏗️ Unified Environment Configuration:")
        logger.info(f"🎯 All Operations: {ctx['base_url']} ({ctx['environment']})")
        logger.info(f"🔄 Architecture: Unified {ctx['environment']} Environment")
        
        return ctx

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
    underlying_symbol: str  # Add missing field
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
                
                underlying_symbol=trade_data.get('underlying', 'SPY'),  # Add underlying symbol
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
    
    @staticmethod
    def build_spread_order_from_parsed_trade(parsed_trade: Dict) -> Optional[SpreadOrder]:
        """
        Build a SpreadOrder from parsed trade data (from database)
        
        Args:
            parsed_trade: Dictionary containing parsed trade data
            
        Returns:
            SpreadOrder object or None if build fails
        """
        try:
            strategy_type = parsed_trade.get('strategy_type', '')
            underlying = parsed_trade.get('underlying', 'SPY')
            expiration = parsed_trade.get('expiration', '')
            short_strike = parsed_trade.get('short_strike', 0.0)
            long_strike = parsed_trade.get('long_strike', 0.0)
            credit_received = parsed_trade.get('credit_received', 0.0)
            
            if not all([strategy_type, expiration, short_strike, long_strike]):
                logger.error("Missing required trade data for order building")
                return None
            
            legs = []
            
            if strategy_type == 'BULL_PUT_SPREAD':
                # Bull Put Spread: Sell higher strike put, Buy lower strike put
                short_symbol = OptionsSymbolBuilder.build_options_symbol(
                    underlying, expiration, 'P', short_strike
                )
                long_symbol = OptionsSymbolBuilder.build_options_symbol(
                    underlying, expiration, 'P', long_strike
                )
                
                legs.append(OptionsLeg(
                    instrument_type="Equity Option",
                    symbol=short_symbol,
                    quantity=1,
                    action="Sell to Open"
                ))
                legs.append(OptionsLeg(
                    instrument_type="Equity Option", 
                    symbol=long_symbol,
                    quantity=1,
                    action="Buy to Open"
                ))
                
            elif strategy_type == 'BEAR_CALL_SPREAD':
                # Bear Call Spread: Sell lower strike call, Buy higher strike call
                short_symbol = OptionsSymbolBuilder.build_options_symbol(
                    underlying, expiration, 'C', short_strike
                )
                long_symbol = OptionsSymbolBuilder.build_options_symbol(
                    underlying, expiration, 'C', long_strike
                )
                
                legs.append(OptionsLeg(
                    instrument_type="Equity Option",
                    symbol=short_symbol,
                    quantity=1,
                    action="Sell to Open"
                ))
                legs.append(OptionsLeg(
                    instrument_type="Equity Option",
                    symbol=long_symbol,
                    quantity=1,
                    action="Buy to Open"
                ))
            else:
                logger.error(f"Unsupported strategy type: {strategy_type}")
                return None
            
            return SpreadOrder(
                underlying_symbol=underlying,
                legs=legs,
                price=credit_received if credit_received > 0 else None,
                price_effect="Credit" if credit_received > 0 else "Debit"
            )
            
        except Exception as e:
            logger.error(f"Failed to build spread order: {e}")
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
    """TastyTrade API integration using unified environment configuration"""
    
    def __init__(self):
        # Use unified configuration for current environment
        self.base_url = config.TT_BASE_URL
        self.api_key = config.TT_API_KEY
        self.api_secret = config.TT_API_SECRET
        self.account_number = config.TT_ACCOUNT_NUMBER
        self.environment = config.ENVIRONMENT_NAME
        
        # Set trading mode based on environment
        self.trading_mode = "SANDBOX" if not config.IS_PRODUCTION else "PRODUCTION"
        
        # Session token for current environment
        self.trading_token = None
        
        logger.info(f"🎯 TastyTrade API initialized in {self.environment} mode")
        logger.info(f"🔗 Base URL: {self.base_url}")
        logger.info(f"🎯 Trading Mode: {self.trading_mode}")
        
    def get_trading_headers(self) -> Dict[str, str]:
        """Get authenticated headers for TRADING API requests"""
        if not self.trading_token:
            self.trading_token = self._authenticate_trading()
        
        if self.trading_token:
            return {
                'Authorization': f'Bearer {self.trading_token}',
                'Content-Type': 'application/json'
            }
        return {}
    
    def _authenticate_trading(self) -> Optional[str]:
        """Authenticate specifically for trading operations"""
        try:
            if self.trading_mode == "SANDBOX":
                # Sandbox: Use OAuth token from Flask session (unified token storage)
                logger.info("🔐 Getting OAuth token for TastyTrade Sandbox trading...")
                
                # Try to get access token from Flask session (unified storage)
                try:
                    from flask import session
                    access_token = session.get('access_token')
                    if access_token:
                        logger.info("✅ Found OAuth token in Flask session for sandbox trading")
                        return access_token
                    else:
                        logger.error("❌ No OAuth token in Flask session - user needs to authenticate via OAuth")
                        return None
                except (ImportError, RuntimeError):
                    logger.error("❌ Not running in Flask context or Flask not available")
                    return None
                    
            else:
                # Production: Use existing production authentication from tt.py
                # This leverages the same OAuth flow as data gathering
                headers = get_authenticated_headers()
                if headers and 'Authorization' in headers:
                    # Extract token from existing authentication
                    auth_header = headers['Authorization']
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]  # Remove 'Bearer ' prefix
                        logger.info("✅ Using existing production token for trading")
                        return token
                
                logger.error("❌ No valid production token available for trading")
                return None
                
        except Exception as e:
            logger.error(f"❌ Trading authentication error: {e}")
            return None
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get order status via REST API (fallback for websocket issues)
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Order data or None if failed
        """
        try:
            headers = self.get_trading_headers()
            account_number = self.get_account_number()
            
            if not headers or not account_number:
                logger.error("❌ Cannot check order status - missing auth or account")
                return None
            
            # Get order status from TastyTrade API
            url = f"{self.base_url}/accounts/{account_number}/orders/{order_id}"
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                order_data = response.json()
                logger.info(f"📊 Order {order_id} status: {order_data.get('data', {}).get('status', 'Unknown')}")
                return order_data.get('data')
            else:
                logger.error(f"❌ Failed to get order status: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error checking order status: {e}")
            return None
    
    def get_account_number(self) -> str:
        """Get account number for trading operations"""
        if self.trading_mode == "SANDBOX":
            # Use predefined sandbox account
            return self.account_number
        else:
            # Production: Get from existing authentication
            if not self.account_number:
                self.account_number = get_current_account_number()
            return self.account_number
    
    def submit_spread_order(self, spread_order: SpreadOrder) -> Optional[Dict]:
        """
        Submit a complex spread order to TastyTrade (using trading-specific auth)
        
        Args:
            spread_order: SpreadOrder object
            
        Returns:
            Order response data or None if failed
        """
        try:
            # Use trading-specific authentication
            headers = self.get_trading_headers()
            account_number = self.get_account_number()
            
            if not headers or not account_number:
                logger.error("Missing trading authentication or account number")
                return None
            
            logger.info(f"🎯 Submitting spread order in {self.trading_mode} mode")
            logger.info(f"📊 Account: {account_number}")
            logger.info(f"🔗 URL: {self.base_url}")
            
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
            
            logger.info(f"📋 Order payload: {json.dumps(payload, indent=2)}")
            
            # Submit order to trading environment
            url = f"{self.base_url}/accounts/{account_number}/orders"
            response = requests.post(url, headers=headers, json=payload)
            
            logger.info(f"📡 Trading API response: {response.status_code}")
            
            if response.status_code == 201:
                order_data = response.json()
                order_id = order_data.get('data', {}).get('order', {}).get('id')
                logger.info(f"✅ Successfully submitted spread order (ID: {order_id}) in {self.trading_mode}")
                return order_data
            else:
                logger.error(f"❌ Failed to submit order: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting spread order: {e}")
            import traceback
            traceback.print_exc()
            return None

def test_unified_environment_system():
    """Test the unified environment system and order submission"""
    
    print("🏗️ Testing Unified Environment Architecture")
    print("=" * 60)
    print(f"🌍 Environment: {config.ENVIRONMENT_NAME}")
    print(f"🎯 Unified API: {config.TT_BASE_URL}")
    print()
    
    # Test Grok parsing
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
            
            # Build the spread order
            print(f"\n🔧 Building Bull Put Spread Order for {config.TRADING_MODE}...")
            print("=" * 50)
            
            builder = SpreadTradeBuilder()
            spread_order = builder.build_bull_put_spread(signal)
            
            print(f"Underlying: {spread_order.underlying_symbol}")
            print(f"Price Effect: {spread_order.price_effect}")
            print(f"Credit: ${spread_order.price}")
            print("Legs:")
            for i, leg in enumerate(spread_order.legs, 1):
                print(f"  Leg {i}: {leg.action} {leg.quantity} {leg.symbol}")
            
            # Test trading API initialization
            print(f"\n🎯 Testing Trading API ({config.TRADING_MODE})...")
            print("=" * 50)
            
            trading_api = TastyTradeAPI()
            
            # Test authentication
            headers = trading_api.get_trading_headers()
            account = trading_api.get_account_number()
            
            print(f"Authentication: {'✅ Success' if headers else '❌ Failed'}")
            print(f"Account Number: {account if account else 'Not available'}")
            
            # Test order submission (dry run if no auth)
            if headers and account:
                print(f"\n🚀 Testing Order Submission to {config.TRADING_MODE}...")
                print("⚠️  This will submit a REAL order to the trading environment!")
                print("Type 'YES' to continue or anything else to skip:")
                
                user_input = input().strip()
                if user_input == 'YES':
                    result = trading_api.submit_spread_order(spread_order)
                    if result:
                        print("✅ Order submitted successfully!")
                        print(f"📋 Order details: {json.dumps(result, indent=2)}")
                    else:
                        print("❌ Order submission failed")
                else:
                    print("⏭️  Order submission skipped")
            else:
                print("⚠️  Cannot test order submission - authentication failed")
            
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
        import traceback
        traceback.print_exc()

def test_grok_parsing():
    """Legacy test function - use test_unified_environment_system() instead"""
    test_unified_environment_system()

if __name__ == "__main__":
    # Run the comprehensive unified environment test
    test_unified_environment_system()
