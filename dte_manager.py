"""
DTE (Days to Expiration) Manager
================================

This module handles flexible DTE configuration for options trading,
allowing traders with smaller accounts to trade longer-dated options
to avoid PDT restrictions while maintaining appropriate risk management.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.data.requests import OptionChainRequest
from config import (
    DEFAULT_DTE, MAX_DTE_OPTIONS, AVAILABLE_DTE_OPTIONS,
    DTE_RISK_MULTIPLIERS, DTE_DATA_CONFIGS
)

class DTEManager:
    """
    Manages Days to Expiration (DTE) configuration and validation
    """
    
    def __init__(self, client: TradingClient = None):
        """
        Initialize DTE Manager
        
        Parameters:
        client: Alpaca TradingClient instance (optional)
        """
        self.client = client
        self.logger = self._setup_logging()
        self.current_dte = DEFAULT_DTE
        
    def _setup_logging(self):
        """Set up logging for DTE manager"""
        logger = logging.getLogger(f"{__name__}.DTEManager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
"""
DTE (Days to Expiration) Manager
================================

This module handles flexible DTE configuration for options trading,
allowing traders with smaller accounts to trade longer-dated options
to avoid PDT restrictions while maintaining appropriate risk management.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.data.requests import OptionChainRequest
from config import (
    DEFAULT_DTE, MAX_DTE_OPTIONS, AVAILABLE_DTE_OPTIONS,
    DTE_RISK_MULTIPLIERS, DTE_DATA_CONFIGS
)

class DTEManager:
    """
    Manages Days to Expiration (DTE) configuration and validation
    """
    
    def __init__(self, client: TradingClient = None):
        """
        Initialize DTE Manager
        
        Parameters:
        client: Alpaca TradingClient instance (optional)
        """
        self.client = client
        self.logger = self._setup_logging()
        self.current_dte = DEFAULT_DTE
        
        # Ticker-aware DTE caching
        self._dte_cache = {}  # Format: {ticker: {date: [dte_list], timestamp: datetime}}
        
    def _setup_logging(self):
        """Set up logging for DTE manager"""
        logger = logging.getLogger(f"{__name__}.DTEManager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _get_cache_key(self, ticker: str) -> str:
        """Generate cache key for ticker and current date"""
        return f"{ticker}_{datetime.now().strftime('%Y-%m-%d')}"
    
    def _is_cache_valid(self, ticker: str, max_age_hours: int = 6) -> bool:
        """Check if cached DTEs for ticker are still valid"""
        cache_key = self._get_cache_key(ticker)
        
        if cache_key not in self._dte_cache:
            return False
        
        cache_time = self._dte_cache[cache_key].get('timestamp')
        if not cache_time:
            return False
        
        # Check if cache is still fresh
        age = datetime.now() - cache_time
        return age.total_seconds() < (max_age_hours * 3600)
    
    def _cache_dtes(self, ticker: str, dte_list: List[int]):
        """Cache DTE list for a ticker"""
        cache_key = self._get_cache_key(ticker)
        self._dte_cache[cache_key] = {
            'dte_list': dte_list,
            'timestamp': datetime.now()
        }
        self.logger.info(f"Cached {len(dte_list)} DTEs for {ticker}")
    
    def _get_cached_dtes(self, ticker: str) -> Optional[List[int]]:
        """Get cached DTEs for a ticker if valid"""
        if self._is_cache_valid(ticker):
            cache_key = self._get_cache_key(ticker)
            cached_data = self._dte_cache[cache_key]
            self.logger.info(f"Using cached DTEs for {ticker}: {cached_data['dte_list']}")
            return cached_data['dte_list']
        return None
    
    def get_available_dtes(self, ticker: str = None, live_discovery: bool = False, force_refresh: bool = False) -> List[int]:
        """
        Get list of available DTE options for a specific ticker
        
        Parameters:
        ticker: Ticker symbol (uses current ticker if None)
        live_discovery: If True, query Alpaca to discover actual available DTEs
        force_refresh: If True, ignore cache and fetch fresh data
        
        Returns:
        List of available DTE values
        """
        # Import here to avoid circular imports
        from ticker_manager import get_current_ticker
        
        if ticker is None:
            ticker = get_current_ticker()
        
        # Check cache first (unless force refresh or not using live discovery)
        if live_discovery and not force_refresh:
            cached_dtes = self._get_cached_dtes(ticker)
            if cached_dtes is not None:
                return cached_dtes
        
        if live_discovery:
            try:
                from paca import get_available_dte_options
                
                self.logger.info(f"🔍 Discovering available DTEs for {ticker} via Alpaca API...")
                discovered_dtes = get_available_dte_options(ticker=ticker, max_dte=MAX_DTE_OPTIONS)
                
                if discovered_dtes:
                    self.logger.info(f"✅ Live discovery found DTEs for {ticker}: {discovered_dtes}")
                    
                    # Cache the results
                    self._cache_dtes(ticker, discovered_dtes)
                    
                    # Filter to only include DTEs we support
                    valid_dtes = [dte for dte in discovered_dtes if dte in AVAILABLE_DTE_OPTIONS]
                    return valid_dtes if valid_dtes else discovered_dtes  # Return all if none match our config
                else:
                    self.logger.error(f"❌ Live discovery returned no DTEs for {ticker}")
                    raise Exception(f"No options contracts found for {ticker}")
            except Exception as e:
                self.logger.error(f"❌ Live discovery failed for {ticker}: {str(e)}")
                raise e  # Re-raise to let caller handle the failure
        
        # If live_discovery=False, still return static list for backwards compatibility
        self.logger.warning(f"⚠️  Using static DTE list for {ticker} (live_discovery=False)")
        return AVAILABLE_DTE_OPTIONS.copy()
    
    def validate_dte(self, dte: int) -> bool:
        """
        Validate if a DTE value is allowed
        
        Parameters:
        dte: Days to expiration
        
        Returns:
        True if valid, False otherwise
        """
        return dte in AVAILABLE_DTE_OPTIONS and 0 <= dte <= MAX_DTE_OPTIONS
    
    def set_dte(self, dte: int) -> bool:
        """
        Set the current DTE for trading
        
        Parameters:
        dte: Days to expiration
        
        Returns:
        True if successfully set, False otherwise
        """
        if self.validate_dte(dte):
            self.current_dte = dte
            self.logger.info(f"📅 DTE set to {dte} days")
            return True
        else:
            self.logger.error(f"❌ Invalid DTE: {dte}. Must be one of {AVAILABLE_DTE_OPTIONS}")
            return False
    
    def get_current_dte(self) -> int:
        """
        Get current DTE setting
        
        Returns:
        Current DTE value
        """
        return self.current_dte
    
    def get_dte_config(self, dte: Optional[int] = None) -> Dict:
        """
        Get configuration for specific DTE
        
        Parameters:
        dte: Days to expiration (uses current if None)
        
        Returns:
        Configuration dictionary for the DTE
        """
        if dte is None:
            dte = self.current_dte
            
        if dte not in DTE_DATA_CONFIGS:
            self.logger.warning(f"⚠️ No config for DTE {dte}, using 0DTE config")
            dte = 0
            
        return DTE_DATA_CONFIGS[dte].copy()
    
    def get_risk_multiplier(self, dte: Optional[int] = None) -> float:
        """
        Get risk multiplier for specific DTE
        
        Parameters:
        dte: Days to expiration (uses current if None)
        
        Returns:
        Risk multiplier for the DTE
        """
        if dte is None:
            dte = self.current_dte
            
        return DTE_RISK_MULTIPLIERS.get(dte, 1.0)
    
    def calculate_target_expiration_date(self, dte: Optional[int] = None) -> datetime:
        """
        Calculate target expiration date based on DTE
        
        Parameters:
        dte: Days to expiration (uses current if None)
        
        Returns:
        Target expiration datetime
        """
        if dte is None:
            dte = self.current_dte
            
        # Simple calculation: today + dte days
        # No more complex Friday logic since we use live Alpaca discovery
        target_date = datetime.now().date() + timedelta(days=dte)
        
        return datetime.combine(target_date, datetime.min.time())
    
    def get_valid_expiration_dates(self, symbol: str = "SPY") -> List[Tuple[datetime, int]]:
        """
        Get valid expiration dates from Alpaca for the symbol
        
        Parameters:
        symbol: Options symbol (default SPY)
        
        Returns:
        List of tuples (expiration_date, actual_dte)
        """
        if not self.client:
            self.logger.warning("⚠️ No Alpaca client provided, cannot fetch real expiration dates")
            return []
        
        try:
            # This is a placeholder - Alpaca's option chain API structure may differ
            # You'll need to adapt this based on Alpaca's actual API response
            today = datetime.now().date()
            valid_dates = []
            
            for dte in AVAILABLE_DTE_OPTIONS:
                target_date = self.calculate_target_expiration_date(dte)
                actual_dte = (target_date.date() - today).days
                valid_dates.append((target_date, actual_dte))
            
            return valid_dates
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching expiration dates: {e}")
            return []
    
    def get_dte_display_name(self, dte: Optional[int] = None) -> str:
        """
        Get display-friendly name for DTE with expiration date
        
        Parameters:
        dte: Days to expiration (uses current if None)
        
        Returns:
        Display name for the DTE with expiration date (e.g., "0DTE (MON 08-19-25)")
        """
        if dte is None:
            dte = self.current_dte
            
        # Calculate expiration date
        try:
            today = datetime.now()
            expiry_date = today + timedelta(days=dte)
            
            # Format: DAY MM-DD-YY
            day_name = expiry_date.strftime('%a').upper()  # MON, TUE, etc.
            date_str = expiry_date.strftime('%m-%d-%y')     # 08-19-25
            
            if dte == 0:
                return f"0DTE ({day_name} {date_str})"
            elif dte == 1:
                return f"1DTE ({day_name} {date_str})"
            else:
                return f"{dte}DTE ({day_name} {date_str})"
                
        except Exception as e:
            # Fallback to simple names if date calculation fails
            self.logger.warning(f"Could not calculate expiry date for DTE {dte}: {e}")
            if dte == 0:
                return "0DTE (Same Day)"
            elif dte == 1:
                return "1DTE (Next Day)"
            else:
                return f"{dte}DTE ({dte} Days)"
    
    def get_dte_summary(self) -> Dict:
        """
        Get comprehensive summary of current DTE configuration
        
        Returns:
        Dictionary with current DTE configuration details
        """
        config = self.get_dte_config()
        risk_multiplier = self.get_risk_multiplier()
        target_expiration = self.calculate_target_expiration_date()
        
        return {
            'current_dte': self.current_dte,
            'display_name': self.get_dte_display_name(),
            'target_expiration': target_expiration.isoformat(),
            'risk_multiplier': risk_multiplier,
            'data_config': config,
            'available_options': self.get_available_dtes()
        }
    
    def is_pdt_friendly(self, dte: Optional[int] = None) -> bool:
        """
        Check if current DTE configuration is PDT-friendly
        
        Parameters:
        dte: Days to expiration (uses current if None)
        
        Returns:
        True if configuration helps avoid PDT restrictions
        """
        if dte is None:
            dte = self.current_dte
            
        # 0DTE and 1DTE are more likely to trigger PDT issues
        # Longer DTEs give more flexibility for position management
        return dte >= 2
    
    def get_strategy_recommendations(self, dte: Optional[int] = None) -> Dict:
        """
        Get strategy recommendations based on DTE
        
        Parameters:
        dte: Days to expiration (uses current if None)
        
        Returns:
        Dictionary with strategy recommendations
        """
        if dte is None:
            dte = self.current_dte
            
        strategies = {
            0: {
                'preferred_strategies': ['Iron Condor', 'Call/Put Spreads', 'Straddles'],
                'risk_level': 'High',
                'time_decay': 'Very Fast',
                'monitoring_frequency': 'Every 5-15 minutes',
                'notes': 'High gamma risk, requires active monitoring'
            },
            1: {
                'preferred_strategies': ['Call/Put Spreads', 'Iron Condor'],
                'risk_level': 'Medium-High', 
                'time_decay': 'Fast',
                'monitoring_frequency': 'Every 15-30 minutes',
                'notes': 'Good balance of premium and risk'
            },
            2: {
                'preferred_strategies': ['Vertical Spreads', 'Iron Butterfly'],
                'risk_level': 'Medium',
                'time_decay': 'Moderate',
                'monitoring_frequency': 'Every 30-60 minutes',
                'notes': 'PDT-friendly, moderate time decay'
            },
            3: {
                'preferred_strategies': ['Vertical Spreads', 'Calendar Spreads'],
                'risk_level': 'Medium',
                'time_decay': 'Moderate',
                'monitoring_frequency': 'Every 1-2 hours',
                'notes': 'Good for swing trading approaches'
            },
            5: {
                'preferred_strategies': ['Vertical Spreads', 'Diagonal Spreads'],
                'risk_level': 'Medium-Low',
                'time_decay': 'Slow',
                'monitoring_frequency': 'Every 2-4 hours',
                'notes': 'Weekly expiration, lower gamma risk'
            },
            7: {
                'preferred_strategies': ['Vertical Spreads', 'Calendar Spreads'],
                'risk_level': 'Medium-Low',
                'time_decay': 'Slow',
                'monitoring_frequency': 'Twice daily',
                'notes': 'Weekly expiration, trend-following friendly'
            },
            10: {
                'preferred_strategies': ['Vertical Spreads', 'Covered Calls'],
                'risk_level': 'Low-Medium',
                'time_decay': 'Very Slow',
                'monitoring_frequency': 'Daily',
                'notes': 'Lower risk, more directional plays'
            }
        }
        
        return strategies.get(dte, strategies[0])

    def validate_ticker_expiration(self, ticker: str, dte: int) -> Dict[str, any]:
        """
        Validate if a ticker supports the requested DTE/expiration
        
        Parameters:
        ticker: Stock ticker (e.g., 'SPY', 'TQQQ')
        dte: Days to expiration
        
        Returns:
        Dict with validation results
        """
        # Import here to avoid global import issues
        from config import TICKER_CONFIGS
        from datetime import datetime, timedelta
        
        # Get ticker configuration
        ticker_config = TICKER_CONFIGS.get(ticker, {})
        
        if not ticker_config:
            return {
                'valid': False,
                'error': f"Ticker {ticker} not supported",
                'suggestion': f"Supported tickers: {', '.join(TICKER_CONFIGS.keys())}"
            }
        
        # Get actual available DTEs from Alpaca (check reality first, not static config)
        try:
            available_dtes = self.get_available_dtes(ticker=ticker, live_discovery=True)
            
            if dte in available_dtes:
                # Calculate the target date for display
                target_date = self.calculate_target_expiration_date(dte)
                target_weekday = target_date.weekday()
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                
                return {
                    'valid': True,
                    'target_date': target_date.strftime('%Y-%m-%d'),
                    'target_weekday': day_names[target_weekday],
                    'schedule': ticker_config.get('expiration_schedule', 'unknown'),
                    'dte': dte,
                    'source': 'alpaca_live_discovery'
                }
            else:
                # DTE not available, provide suggestions
                valid_suggestions = available_dtes[:5]  # First 5 available DTEs
                schedule = ticker_config.get('expiration_schedule', 'unknown')
                
                return {
                    'valid': False,
                    'error': f"{ticker} does not have {dte}DTE options available in Alpaca",
                    'suggestion': f"{ticker} currently has {schedule} options available. Try DTEs: {valid_suggestions}",
                    'valid_dtes': valid_suggestions,
                    'schedule': schedule,
                    'source': 'alpaca_live_discovery'
                }
                
        except Exception as e:
            # Don't fall back - return clear error about validation failure
            self.logger.error(f"❌ Alpaca discovery failed for {ticker}: {str(e)}")
            return {
                'valid': False,
                'error': f"Unable to validate {ticker} {dte}DTE options - Alpaca API discovery failed",
                'technical_error': str(e),
                'suggestion': f"Check Alpaca API connectivity and try again. If this persists, contact support.",
                'source': 'validation_failed'
            }

    def suggest_valid_dte_for_ticker(self, ticker: str, max_dte: int = 14) -> List[Dict]:
        """
        Suggest valid DTEs for a ticker using live Alpaca discovery
        
        Parameters:
        ticker: Stock ticker
        max_dte: Maximum DTE to check (not used with live discovery)
        
        Returns:
        List of valid DTE options with details
        """
        try:
            # Get actual available DTEs from Alpaca
            available_dtes = self.get_available_dtes(ticker=ticker, live_discovery=True)
            
            valid_options = []
            for dte in available_dtes:
                # Calculate target date for display
                target_date = self.calculate_target_expiration_date(dte)
                target_weekday = target_date.weekday()
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                
                valid_options.append({
                    'dte': dte,
                    'target_date': target_date.strftime('%Y-%m-%d'),
                    'weekday': day_names[target_weekday],
                    'display_name': f"{dte}DTE ({day_names[target_weekday][:3]} {target_date.strftime('%Y-%m-%d')})",
                    'source': 'alpaca_live_discovery'
                })
            
            return valid_options
            
        except Exception as e:
            # Fall back to validation-based approach
            self.logger.warning(f"Live discovery failed for {ticker}, falling back to validation approach: {e}")
            
            valid_options = []
            for dte in range(0, max_dte + 1):
                validation = self.validate_ticker_expiration(ticker, dte)
                if validation['valid']:
                    valid_options.append({
                        'dte': dte,
                        'target_date': validation['target_date'],
                        'weekday': validation['target_weekday'],
                        'display_name': f"{dte}DTE ({validation['target_weekday'][:3]} {validation['target_date']})",
                        'source': 'fallback_validation'
                    })
            
            return valid_options


# Global DTE manager instance
dte_manager = DTEManager()


def get_current_dte() -> int:
    """Get current DTE setting"""
    return dte_manager.get_current_dte()


def set_trading_dte(dte: int) -> bool:
    """Set trading DTE"""
    return dte_manager.set_dte(dte)


def get_dte_data_config(dte: Optional[int] = None) -> Dict:
    """Get data configuration for DTE"""
    return dte_manager.get_dte_config(dte)


def get_dte_risk_multiplier(dte: Optional[int] = None) -> float:
    """Get risk multiplier for DTE"""
    return dte_manager.get_risk_multiplier(dte)
