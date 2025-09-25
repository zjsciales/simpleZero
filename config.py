"""
Configuration settings for the SPY Options Trading System
=========================================================

This file contains all configuration parameters for the trading system,
including API credentials, trading parameters, and risk management settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# ENVIRONMENT DETECTION
# =============================================================================

# Detect environment - Railway sets RAILWAY_ENVIRONMENT, we can also check other indicators
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')  # Set explicitly or default to development
IS_PRODUCTION = (
    os.getenv('RAILWAY_ENVIRONMENT') is not None or  # Railway deployment
    os.getenv('ENVIRONMENT') == 'production' or       # Explicit production setting
    os.getenv('PORT') is not None                     # Railway sets PORT
)

# =============================================================================
# ENVIRONMENT-SPECIFIC SETTINGS
# =============================================================================

# Check if we're using production TastyTrade credentials
USING_PRODUCTION_TT_CREDS = (
    os.getenv('TT_API_KEY') and 
    os.getenv('TT_API_KEY') != 'your_tastytrade_api_key' and
    os.getenv('TT_API_BASE_URL', '').startswith('https://api.tastyworks.com')
)

if IS_PRODUCTION:
    # Production settings (Railway/algaebot.com)
    BASE_URL = "https://algaebot.com"
    TT_REDIRECT_URI = f"{BASE_URL}/ttProd"  # Production callback URL for TastyTrade Prod
    TT_SANDBOX_REDIRECT_URI = os.getenv('TT_REDIRECT_URI', f"{BASE_URL}/ttSandbox")  # Sandbox callback
    FLASK_ENV = "production"
    DEBUG = False
    PORT = int(os.getenv('PORT', 5000))  # Railway assigns PORT
else:
    # Development settings (localhost)
    BASE_URL = "https://127.0.0.1:5001"
    TT_REDIRECT_URI = f"{BASE_URL}/zscialesProd"  # Development callback URL for TastyTrade Prod
    TT_SANDBOX_REDIRECT_URI = f"{BASE_URL}/oauth/sandbox/callback"  # New sandbox callback URI
    FLASK_ENV = "development"
    DEBUG = True
    PORT = 5001

print(f"🌍 Environment: {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'}")
print(f"🔗 Base URL: {BASE_URL}")
print(f"🔄 TT Redirect URI (Production): {TT_REDIRECT_URI}")
print(f"🔄 TT Sandbox Redirect URI: {TT_SANDBOX_REDIRECT_URI}")

# =============================================================================
# TASTYTRADE DUAL ENVIRONMENT CONFIGURATION
# =============================================================================

# Data Gathering: Always use Production TastyTrade for quality market data
TT_DATA_API_KEY = os.getenv('TT_API_KEY')
TT_DATA_API_SECRET = os.getenv('TT_API_SECRET') 
TT_DATA_BASE_URL = os.getenv('TT_API_BASE_URL', 'https://api.tastyworks.com')

# Trading Execution: Environment-dependent
if IS_PRODUCTION:
    # Production deployment: Use real TastyTrade for actual trading
    TT_TRADING_API_KEY = os.getenv('TT_API_KEY')
    TT_TRADING_API_SECRET = os.getenv('TT_API_SECRET')
    TT_TRADING_BASE_URL = os.getenv('TT_API_BASE_URL', 'https://api.tastyworks.com')
    TT_TRADING_ACCOUNT_NUMBER = None  # Will be fetched dynamically in production
    TT_TRADING_USERNAME = None
    TT_TRADING_PASSWORD = None
    TRADING_MODE = "PRODUCTION"
else:
    # Development/Local: Use Sandbox for safe testing
    TT_TRADING_API_KEY = os.getenv('TT_API_KEY_SANDBOX')
    TT_TRADING_API_SECRET = os.getenv('TT_API_SECRET_SANDBOX')
    TT_TRADING_BASE_URL = os.getenv('TT_SANDBOX_BASE_URL', 'https://api.cert.tastyworks.com')
    TT_TRADING_ACCOUNT_NUMBER = os.getenv('TT_ACCOUNT_NUMBER_SANDBOX')
    TT_TRADING_USERNAME = os.getenv('TT_USERNAME_SANDBOX')
    TT_TRADING_PASSWORD = os.getenv('TT_PASSWORD_SANDBOX')
    TRADING_MODE = "SANDBOX"

print(f"📊 Data API: {TT_DATA_BASE_URL} (Production for quality data)")
print(f"🎯 Trading API: {TT_TRADING_BASE_URL} ({TRADING_MODE})")

# =============================================================================
# API CREDENTIALS
# =============================================================================

# TastyTrade (tt) API
TT_API_KEY = os.getenv('TT_API_KEY')
TT_API_SECRET = os.getenv('TT_API_SECRET')
TT_API_BASE_URL = os.getenv('TT_API_BASE_URL', 'https://api.tastyworks.com')  # Production endpoint
TT_SANDBOX_BASE_URL = "https://api.cert.tastyworks.com"  # Sandbox endpoint


# X.AI (Grok) API
XAI_API_KEY = os.getenv('XAI_API_KEY')
XAI_BASE_URL = "https://api.x.ai/v1/chat/completions"

# Polygon.io API (for market data)
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

# =============================================================================
# TRADING PARAMETERS
# =============================================================================

# Paper Trading Settings
PAPER_TRADING = True  # Set to False for live trading (BE VERY CAREFUL)

# Position Sizing
MAX_POSITION_SIZE = 10          # Maximum contracts per position
MAX_CONCURRENT_POSITIONS = 5    # Maximum number of open positions
DEFAULT_QUANTITY = 1            # Default number of contracts per trade

# Risk Management
MAX_DAILY_LOSS = 1000          # Maximum daily loss in dollars
MAX_PORTFOLIO_RISK = 0.05      # Maximum 5% of portfolio at risk
RISK_PER_TRADE = 0.02          # 2% risk per individual trade
STOP_LOSS_PERCENTAGE = 2    # Stop loss at 200% of premium received or paid

# Profit Taking
PROFIT_TARGET_PERCENTAGE = 0.85  # Take profits at 85% gain
TRAILING_STOP_PERCENTAGE = 0.30  # 30% trailing stop

# Time-based Risk Management
MAX_HOLD_TIME_0DTE = 4         # Maximum hours to hold 0DTE options
MIN_TIME_TO_EXPIRY = 0.5       # Minimum hours before expiry to hold positions
CLOSE_BEFORE_EXPIRY = 15       # Minutes before expiry to close all positions

# DTE (Days to Expiration) Configuration
DEFAULT_DTE = 0                # Default to 0DTE trading
MAX_DTE_OPTIONS = 10           # Maximum days to expiration offered
AVAILABLE_DTE_OPTIONS = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10]  # Available DTE selections

# DTE-specific Risk Management
DTE_RISK_MULTIPLIERS = {
    0: 1.0,    # 0DTE: Base risk parameters
    1: 1.2,    # 1DTE: 20% higher risk tolerance
    2: 1.5,    # 2DTE: 50% higher risk tolerance
    3: 1.8,    # 3DTE: 80% higher risk tolerance
    5: 2.2,    # 5DTE: 120% higher risk tolerance
    7: 2.5,    # 7DTE: 150% higher risk tolerance
    10: 3.0    # 10DTE: 200% higher risk tolerance
}

# =============================================================================
# TICKER CONFIGURATION
# =============================================================================

# Available tickers for trading
AVAILABLE_TICKERS = ["SPY", "TQQQ"]
DEFAULT_TICKER = "SPY"

# Ticker-specific configurations
TICKER_CONFIGS = {
    "SPY": {
        "name": "SPDR S&P 500 ETF",
        "description": "S&P 500 Index ETF - Broad market exposure",
        "sector": "Broad Market",
        "typical_range_percent": 5,  # Typical daily range for strike selection
        "min_strike_increment": 1,   # Minimum strike price increment
        "high_volume_threshold": 1000,  # High volume threshold for options
        "tight_spread_threshold": 0.05,  # Tight spread threshold (5%)
        "expiration_schedule": "daily",  # SPY has daily expirations
        "supports_0dte": True,  # SPY supports same-day (0DTE) options
        "expiration_days": [0, 1, 2, 3, 4, 5, 6],  # All days of week (Mon=0, Sun=6)
    },
    "TQQQ": {
        "name": "ProShares UltraPro QQQ",
        "description": "3x leveraged Nasdaq-100 ETF - High volatility tech exposure", 
        "sector": "Technology (3x Leveraged)",
        "typical_range_percent": 8,  # Higher range due to 3x leverage
        "min_strike_increment": 0.5, # Smaller increment due to lower price
        "high_volume_threshold": 500,   # Lower threshold due to smaller market
        "tight_spread_threshold": 0.08,  # Wider acceptable spread due to volatility
        "expiration_schedule": "weekly",  # TQQQ has weekly expirations only
        "supports_0dte": False,  # Fallback assumption; live discovery may find 0DTE on Fridays
        "expiration_days": [4],  # Only Fridays (Fri=4)
    }
}

# =============================================================================
# MARKET DATA PARAMETERS
# =============================================================================

# Market data timeframes
INTRADAY_INTERVAL = "1m"       # 1-minute bars for real-time analysis
DAILY_INTERVAL = "1d"          # Daily bars for technical analysis
ANALYSIS_PERIOD = "60d"        # 60 days for RSI and technical indicators

# DTE-specific Market Data Configuration
DTE_DATA_CONFIGS = {
    0: {
        'period': '1d',
        'interval': '1m',
        'analysis_period': '5d',
        'data_points': 30  # Last 30 minutes
    },
    1: {
        'period': '2d', 
        'interval': '5m',
        'analysis_period': '10d',
        'data_points': 48  # Last 4 hours
    },
    2: {
        'period': '5d',
        'interval': '15m',  # Keep 15m (supported)
        'analysis_period': '15d',
        'data_points': 32  # Last 8 hours
    },
    3: {
        'period': '5d',
        'interval': '30m',  # Keep 30m (supported)
        'analysis_period': '20d', 
        'data_points': 24  # Last 12 hours
    },
    5: {
        'period': '1mo',
        'interval': '1h',  # Keep 1h (supported)
        'analysis_period': '30d',
        'data_points': 24  # Last 24 hours
    },
    7: {
        'period': '1mo',
        'interval': '1h',  # Changed from '2h' to '1h' (yfinance supported)
        'analysis_period': '45d',
        'data_points': 48  # Increased to account for hourly data
    },
    10: {
        'period': '2mo',
        'interval': '1d',
        'analysis_period': '60d',
        'data_points': 10  # Last 10 days
    }
}

# Technical Analysis Parameters
RSI_PERIOD = 14                # RSI calculation period
BB_PERIOD = 20                 # Bollinger Bands period
BB_STD_DEV = 2                 # Bollinger Bands standard deviations
SMA_SHORT = 20                 # Short-term moving average
SMA_LONG = 50                  # Long-term moving average
EMA_SHORT = 10                 # Short-term exponential moving average
EMA_LONG = 20                  # Long-term exponential moving average

# =============================================================================
# OPTIONS TRADING PARAMETERS
# =============================================================================

# Strike Selection
ATM_RANGE = 2.0               # Range around ATM for strike selection
MAX_STRIKE_DISTANCE = 10.0    # Maximum distance from current price
MIN_STRIKE_DISTANCE = 0.5     # Minimum distance from current price

# Spread Parameters
MAX_SPREAD_WIDTH = 5.0        # Maximum width for vertical spreads
MIN_SPREAD_WIDTH = 1.0        # Minimum width for vertical spreads
PREFERRED_SPREAD_WIDTH = 2.0  # Preferred spread width

# Option Filtering
MIN_VOLUME = 100              # Minimum daily volume for option selection
MIN_OPEN_INTEREST = 500       # Minimum open interest
MAX_BID_ASK_SPREAD = 0.10     # Maximum bid-ask spread (absolute)
MAX_BID_ASK_SPREAD_PCT = 0.15 # Maximum bid-ask spread (percentage)

# Iron Condor Parameters
IC_WING_WIDTH = 5.0           # Width of each wing in iron condor
IC_CENTER_BUFFER = 10.0       # Buffer from current price to short strikes

# =============================================================================
# TRADING SCHEDULE
# =============================================================================

# Market Hours (Eastern Time)
MARKET_OPEN = "09:30"         # Market open time
MARKET_CLOSE = "16:00"        # Market close time
EARLY_ENTRY = "09:35"         # Earliest entry time (avoid opening volatility)
LATE_ENTRY = "15:30"          # Latest entry time for 0DTE
POSITION_CLOSE = "13:30"      # Close all positions at 1:30 PM to avoid afternoon volatility

# Trading Days
TRADING_DAYS = [0, 1, 2, 3, 4]  # Monday=0, Friday=4 (no weekends)

# =============================================================================
# NOTIFICATION SETTINGS
# =============================================================================

# Logging
LOG_LEVEL = "INFO"            # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "spy_trading.log"  # Log file name
MAX_LOG_SIZE = 10             # MB before log rotation

# Alert Thresholds
LOSS_ALERT_THRESHOLD = 500    # Alert when loss exceeds this amount
PROFIT_ALERT_THRESHOLD = 500  # Alert when profit exceeds this amount
POSITION_ALERT_THRESHOLD = 0.75  # Alert when position reaches 75% of target

# =============================================================================
# STRATEGY PARAMETERS
# =============================================================================

# 0DTE Scalping
SCALP_PROFIT_TARGET = 0.25    # 25 cents profit target
SCALP_STOP_LOSS = 0.15        # 15 cents stop loss
SCALP_MAX_HOLD_TIME = 2       # Maximum 2 hours hold time

# Vertical Spreads
SPREAD_PROFIT_TARGET = 0.50   # 50% of maximum spread profit
SPREAD_STOP_LOSS = 0.25       # 25% of premium paid

# Iron Condor
IC_PROFIT_TARGET = 0.30       # 30% of maximum condor profit
IC_STOP_LOSS = 2.0            # 2x premium received
IC_ADJUSTMENT_TRIGGER = 0.15  # Adjust when short strike is 15 cents ITM

# =============================================================================
# MARKET CONDITION PARAMETERS
# =============================================================================

# Volatility Thresholds
LOW_VIX_THRESHOLD = 15        # Below this is low volatility
HIGH_VIX_THRESHOLD = 25       # Above this is high volatility

# Trend Identification
TREND_STRENGTH_THRESHOLD = 0.5  # Minimum strength for trend identification
SIDEWAYS_RANGE_THRESHOLD = 0.5  # Maximum range for sideways market

# RSI Thresholds
RSI_OVERSOLD = 30             # RSI oversold level
RSI_OVERBOUGHT = 70           # RSI overbought level
RSI_EXTREME_OVERSOLD = 20     # Extreme oversold level
RSI_EXTREME_OVERBOUGHT = 80   # Extreme overbought level

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_market_hours():
    """Get market open and close times"""
    return {
        'open': MARKET_OPEN,
        'close': MARKET_CLOSE,
        'early_entry': EARLY_ENTRY,
        'late_entry': LATE_ENTRY,
        'position_close': POSITION_CLOSE
    }

def get_risk_parameters():
    """Get risk management parameters"""
    return {
        'max_daily_loss': MAX_DAILY_LOSS,
        'max_portfolio_risk': MAX_PORTFOLIO_RISK,
        'risk_per_trade': RISK_PER_TRADE,
        'stop_loss_pct': STOP_LOSS_PERCENTAGE,
        'profit_target_pct': PROFIT_TARGET_PERCENTAGE
    }

def get_technical_parameters():
    """Get technical analysis parameters"""
    return {
        'rsi_period': RSI_PERIOD,
        'bb_period': BB_PERIOD,
        'bb_std_dev': BB_STD_DEV,
        'sma_short': SMA_SHORT,
        'sma_long': SMA_LONG,
        'ema_short': EMA_SHORT,
        'ema_long': EMA_LONG
    }

def get_options_parameters():
    """Get options trading parameters"""
    return {
        'min_volume': MIN_VOLUME,
        'min_open_interest': MIN_OPEN_INTEREST,
        'max_bid_ask_spread': MAX_BID_ASK_SPREAD,
        'max_spread_width': MAX_SPREAD_WIDTH,
        'preferred_spread_width': PREFERRED_SPREAD_WIDTH
    }

def validate_config():
    """
    Validate configuration settings
    
    Returns:
    Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check API keys
    if not TT_API_KEY:
        errors.append("TT_API_KEY not found in environment variables")
    if not TT_API_SECRET:
        errors.append("TT_API_SECRET not found in environment variables")
    if not XAI_API_KEY:
        errors.append("XAI_API_KEY not found in environment variables")
    
    # Check risk parameters
    if MAX_DAILY_LOSS <= 0:
        errors.append("MAX_DAILY_LOSS must be positive")
    if RISK_PER_TRADE <= 0 or RISK_PER_TRADE > 1:
        errors.append("RISK_PER_TRADE must be between 0 and 1")
    
    # Check position limits
    if MAX_POSITION_SIZE <= 0:
        errors.append("MAX_POSITION_SIZE must be positive")
    if MAX_CONCURRENT_POSITIONS <= 0:
        errors.append("MAX_CONCURRENT_POSITIONS must be positive")
    
    # Check spread parameters
    if MIN_SPREAD_WIDTH >= MAX_SPREAD_WIDTH:
        errors.append("MIN_SPREAD_WIDTH must be less than MAX_SPREAD_WIDTH")
    
    return len(errors) == 0, errors

# Print configuration status when imported
if __name__ == "__main__":
    print("SPY Options Trading Configuration")
    print("=" * 40)
    print(f"Paper Trading: {PAPER_TRADING}")
    print(f"Default Ticker: {DEFAULT_TICKER}")
    print(f"Available Tickers: {', '.join(AVAILABLE_TICKERS)}")
    print(f"Max Daily Loss: ${MAX_DAILY_LOSS}")
    print(f"Max Position Size: {MAX_POSITION_SIZE}")
    print(f"Risk Per Trade: {RISK_PER_TRADE:.1%}")
    
    is_valid, errors = validate_config()
    if is_valid:
        print("✅ Configuration validation passed")
    else:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
