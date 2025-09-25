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
# TastyTrade imports (replacement for Alpaca)
try:
    from tt import TastyTradeSession  # Use TastyTrade session for options data
except ImportError:
    TastyTradeSession = None
from config import (
    DEFAULT_DTE, MAX_DTE_OPTIONS, AVAILABLE_DTE_OPTIONS,
    DTE_RISK_MULTIPLIERS, DTE_DATA_CONFIGS
)

class DTEManager:
    """
    Manages Days to Expiration (DTE) configuration and validation
    """
    
    def __init__(self, session: TastyTradeSession = None):
        """
        Initialize DTE Manager
        
        Parameters:
        session: TastyTrade session instance (optional, replaces Alpaca client)
        """
        self.session = session
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

    def get_valid_dte_options(self, ticker: str = "SPY", 
                             max_dte: int = None,
                             live_discovery: bool = False) -> List[int]:
        """
        Get valid DTE options for trading
        
        Parameters:
        ticker: Stock symbol (default: SPY)
        max_dte: Maximum DTE to consider (default: from config)
        live_discovery: If True, query TastyTrade to discover actual available DTEs
        
        Returns:
        List of valid DTE options
        """
        if max_dte is None:
            max_dte = MAX_DTE_OPTIONS
        
        # Start with configured DTE options
        valid_dtes = [dte for dte in AVAILABLE_DTE_OPTIONS if dte <= max_dte]
        
        if live_discovery and self.session:
            try:
                # Try to get actual available expiration dates from TastyTrade
                # This replaces the Alpaca API calls
                from tt import get_options_chain
                self.logger.info(f"🔍 Discovering available DTEs for {ticker} via TastyTrade API...")
                
                # Get options chain to find available expiration dates
                chain_data = get_options_chain(ticker, session=self.session)
                if chain_data and 'expirations' in chain_data:
                    actual_dtes = self._calculate_dtes_from_expirations(chain_data['expirations'])
                    # Filter to only include DTEs that are in our configured range
                    valid_actual_dtes = [dte for dte in actual_dtes if dte in AVAILABLE_DTE_OPTIONS and dte <= max_dte]
                    
                    if valid_actual_dtes:
                        valid_dtes = valid_actual_dtes
                        self.logger.info(f"✅ Found {len(valid_dtes)} valid DTEs from TastyTrade: {valid_dtes}")
                    else:
                        self.logger.warning("⚠️ No valid DTEs found from TastyTrade, using configured defaults")
                else:
                    self.logger.warning("⚠️ No expiration data from TastyTrade, using configured defaults")
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Live DTE discovery failed: {e}, using configured defaults")
        
        return sorted(valid_dtes)

    def _calculate_dtes_from_expirations(self, expirations: List[str]) -> List[int]:
        """
        Calculate DTEs from expiration date strings
        
        Parameters:
        expirations: List of expiration date strings
        
        Returns:
        List of DTE integers
        """
        today = datetime.now().date()
        dtes = []
        
        for exp_str in expirations:
            try:
                # Parse expiration date (assuming YYYY-MM-DD format)
                exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
                dte = (exp_date - today).days
                if dte >= 0:  # Only future expirations
                    dtes.append(dte)
            except Exception as e:
                self.logger.warning(f"⚠️ Could not parse expiration date {exp_str}: {e}")
                continue
        
        return dtes

    def is_valid_dte(self, dte: int, ticker: str = "SPY") -> bool:
        """
        Check if a DTE value is valid for trading
        
        Parameters:
        dte: Days to expiration to validate
        ticker: Stock symbol (for future symbol-specific rules)
        
        Returns:
        True if DTE is valid, False otherwise
        """
        valid_dtes = self.get_valid_dte_options(ticker)
        return dte in valid_dtes

    def get_recommended_dte(self, account_size: float, risk_tolerance: str = "medium") -> int:
        """
        Get recommended DTE based on account size and risk tolerance
        
        Parameters:
        account_size: Account size in USD
        risk_tolerance: "low", "medium", or "high"
        
        Returns:
        Recommended DTE value
        """
        # Account size thresholds for DTE recommendations
        if account_size < 5000:
            # Small accounts - use longer DTEs to avoid PDT restrictions
            base_dte = 14
        elif account_size < 25000:
            # Medium accounts - balanced approach
            base_dte = 7
        else:
            # Large accounts - can trade any DTE
            base_dte = DEFAULT_DTE
        
        # Adjust based on risk tolerance
        risk_adjustments = {
            "low": 7,      # Add more time for safety
            "medium": 0,   # Use base recommendation
            "high": -3     # Shorter DTE for more aggressive trading
        }
        
        recommended_dte = base_dte + risk_adjustments.get(risk_tolerance, 0)
        
        # Ensure the recommendation is in our valid options
        valid_dtes = self.get_valid_dte_options()
        
        # Find the closest valid DTE
        if recommended_dte in valid_dtes:
            return recommended_dte
        
        # Find closest valid DTE
        closest_dte = min(valid_dtes, key=lambda x: abs(x - recommended_dte))
        self.logger.info(f"📊 Adjusted recommended DTE from {recommended_dte} to {closest_dte} (closest valid option)")
        
        return closest_dte

    def set_current_dte(self, dte: int, ticker: str = "SPY") -> bool:
        """
        Set the current DTE for trading
        
        Parameters:
        dte: Days to expiration to set
        ticker: Stock symbol to validate against
        
        Returns:
        True if DTE was set successfully, False if invalid
        """
        if self.is_valid_dte(dte, ticker):
            old_dte = self.current_dte
            self.current_dte = dte
            self.logger.info(f"✅ DTE changed from {old_dte} to {dte}")
            return True
        else:
            valid_options = self.get_valid_dte_options(ticker)
            self.logger.error(f"❌ Invalid DTE {dte}. Valid options: {valid_options}")
            return False

    def get_current_dte(self) -> int:
        """Get the current DTE setting"""
        return self.current_dte

    def get_dte_multiplier(self, dte: int) -> float:
        """
        Get risk multiplier for a given DTE
        
        Parameters:
        dte: Days to expiration
        
        Returns:
        Risk multiplier (higher DTE = higher multiplier for larger positions)
        """
        return DTE_RISK_MULTIPLIERS.get(dte, 1.0)

    def get_dte_data_config(self, dte: int) -> Dict:
        """
        Get data configuration (period, interval) for a given DTE
        
        Parameters:
        dte: Days to expiration
        
        Returns:
        Dictionary with 'period' and 'interval' keys
        """
        return DTE_DATA_CONFIGS.get(dte, {"period": "1d", "interval": "1m"})

    def get_next_friday_dte(self) -> int:
        """
        Calculate DTE for next Friday (common expiration day)
        
        Returns:
        DTE for next Friday
        """
        today = datetime.now().date()
        days_until_friday = (4 - today.weekday()) % 7  # Friday is day 4
        if days_until_friday == 0:  # Today is Friday
            days_until_friday = 7  # Next Friday
        
        next_friday = today + timedelta(days=days_until_friday)
        return (next_friday - today).days

    def get_available_expiration_dates(self, ticker: str = "SPY") -> List[datetime]:
        """
        Get valid expiration dates from TastyTrade for the symbol
        
        Parameters:
        ticker: Stock symbol
        
        Returns:
        List of available expiration dates
        """
        if not self.session:
            self.logger.warning("⚠️ No TastyTrade session provided, cannot fetch real expiration dates")
            return []
        
        try:
            # This is a placeholder - TastyTrade's option chain API structure may differ
            # You'll need to adapt this based on TastyTrade's actual API response
            from tt import get_options_chain
            chain_data = get_options_chain(ticker, session=self.session)
            
            if chain_data and 'expirations' in chain_data:
                dates = []
                for exp_str in chain_data['expirations']:
                    try:
                        exp_date = datetime.strptime(exp_str, '%Y-%m-%d')
                        dates.append(exp_date)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Could not parse expiration date {exp_str}: {e}")
                        continue
                return sorted(dates)
            else:
                self.logger.warning("⚠️ No expiration data in TastyTrade response")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error fetching expiration dates from TastyTrade: {e}")
            return []

    def validate_dte_for_account(self, dte: int, account_value: float, 
                               position_size: float) -> Dict[str, any]:
        """
        Validate if a DTE is appropriate for account size and position
        
        Parameters:
        dte: Days to expiration
        account_value: Total account value
        position_size: Size of the position being considered
        
        Returns:
        Dictionary with validation results
        """
        result = {
            "is_valid": True,
            "warnings": [],
            "recommendations": [],
            "risk_level": "medium"
        }
        
        # Calculate position as percentage of account
        position_pct = (position_size / account_value) * 100 if account_value > 0 else 0
        
        # DTE-specific validations
        if dte == 0:
            if account_value < 25000:
                result["warnings"].append("0DTE trading with account < $25k may trigger PDT restrictions")
                result["risk_level"] = "high"
            if position_pct > 5:
                result["warnings"].append("0DTE position > 5% of account is very risky")
                result["risk_level"] = "very_high"
        
        elif dte <= 3:
            if position_pct > 10:
                result["warnings"].append("Short DTE position > 10% of account increases risk")
                result["risk_level"] = "high"
        
        elif dte >= 14:
            if position_pct < 2:
                result["recommendations"].append("Consider larger position size for longer DTE")
            
        # General recommendations
        if account_value < 5000 and dte < 7:
            result["recommendations"].append("Consider longer DTE (≥7 days) for smaller accounts")
        
        # Set overall validity
        if result["risk_level"] in ["very_high"]:
            result["is_valid"] = False
        
        return result

    def get_dte_summary(self) -> Dict[str, any]:
        """
        Get summary of current DTE configuration
        
        Returns:
        Dictionary with DTE configuration summary
        """
        return {
            "current_dte": self.current_dte,
            "available_dtes": AVAILABLE_DTE_OPTIONS,
            "max_dte": MAX_DTE_OPTIONS,
            "default_dte": DEFAULT_DTE,
            "risk_multipliers": DTE_RISK_MULTIPLIERS,
            "data_configs": DTE_DATA_CONFIGS,
            "has_tastytrade_session": self.session is not None
        }

def get_recommended_dte_for_market_conditions(volatility: float = None, 
                                            market_trend: str = "neutral") -> int:
    """
    Get recommended DTE based on current market conditions
    
    Parameters:
    volatility: Market volatility (VIX level)
    market_trend: "bullish", "bearish", or "neutral"
    
    Returns:
    Recommended DTE based on market conditions
    """
    base_dte = DEFAULT_DTE
    
    # Volatility adjustments
    if volatility is not None:
        if volatility > 30:  # High volatility
            base_dte += 3  # Use longer DTE in volatile markets
        elif volatility < 15:  # Low volatility
            base_dte = max(0, base_dte - 2)  # Can use shorter DTE in calm markets
    
    # Trend adjustments
    if market_trend == "bearish":
        base_dte += 2  # Be more conservative in bear markets
    elif market_trend == "bullish":
        base_dte = max(0, base_dte - 1)  # Can be more aggressive in bull markets
    
    # Ensure result is in valid options
    valid_dtes = AVAILABLE_DTE_OPTIONS
    if base_dte in valid_dtes:
        return base_dte
    
    # Find closest valid DTE
    return min(valid_dtes, key=lambda x: abs(x - base_dte))

def create_dte_manager(session: TastyTradeSession = None) -> DTEManager:
    """
    Factory function to create DTEManager instance
    
    Parameters:
    session: TastyTrade session instance
    
    Returns:
    Configured DTEManager instance
    """
    manager = DTEManager(session=session)
    
    # Get actual available DTEs from TastyTrade (check reality first, not static config)
    try:
        available_dtes = manager.get_valid_dte_options(live_discovery=True)
        logging.info(f"📊 DTE Manager initialized with {len(available_dtes)} available DTEs: {available_dtes}")
    except Exception as e:
        logging.warning(f"⚠️ Could not verify available DTEs from TastyTrade: {e}")
        logging.info(f"📊 DTE Manager initialized with default configuration")
    
    return manager

# Backward compatibility functions (with TastyTrade replacements)
def get_available_dte_options(ticker: str = "SPY", session: TastyTradeSession = None) -> List[int]:
    """Backward compatibility function - get available DTEs"""
    manager = DTEManager(session=session)
    return manager.get_valid_dte_options(ticker, live_discovery=True)

def validate_dte(dte: int, ticker: str = "SPY") -> bool:
    """Backward compatibility function - validate DTE"""
    manager = DTEManager()
    return manager.is_valid_dte(dte, ticker)

def get_current_dte() -> int:
    """Get current DTE as standalone function for backward compatibility"""
    manager = create_dte_manager()
    return manager.get_current_dte()

if __name__ == "__main__":
    # Test the DTE manager
    print("🧪 Testing DTE Manager...")
    
    manager = create_dte_manager()
    
    print(f"📊 Current DTE: {manager.get_current_dte()}")
    print(f"📊 Available DTEs: {manager.get_valid_dte_options()}")
    print(f"📊 Recommended DTE for $10k account: {manager.get_recommended_dte(10000)}")
    print(f"📊 Next Friday DTE: {manager.get_next_friday_dte()}")
    
    # Test market conditions
    print(f"📊 Recommended DTE for high volatility: {get_recommended_dte_for_market_conditions(35, 'bearish')}")
    print(f"📊 Recommended DTE for low volatility: {get_recommended_dte_for_market_conditions(12, 'bullish')}")
    
    print("✅ DTE Manager tests completed!")