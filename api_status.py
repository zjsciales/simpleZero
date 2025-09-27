"""
Helper functions for checking API status without modifying the environment.
"""

import config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_production_api_status(skip_api_check=False):
    """
    Check if the production API is authenticated and working.
    Does not modify the environment.
    
    Args:
        skip_api_check (bool): If True, skips the actual API call and just returns if there's a token
        
    Returns:
        tuple: (has_token, is_authenticated, is_working)
    """
    from flask import session
    
    # Check if we have a production token in session
    prod_token = session.get('prod_access_token') or session.get('access_token')
    has_prod_token = bool(prod_token)
    
    if not has_prod_token or skip_api_check:
        return (has_prod_token, False, False)
    
    # Try to authenticate with Production API
    try:
        # Import modules directly to avoid environment issues
        import tt_data
        client = tt_data.TastyTradeMarketData(use_production=True)
        prod_api_authenticated = client.authenticate()
        
        if prod_api_authenticated:
            # Try a simple API call
            test_data = client.get_market_data_clean('SPY')
            prod_api_working = test_data is not None
            return (True, True, prod_api_working)
        else:
            return (True, False, False)
    except Exception as e:
        logger.error(f"Production API check failed: {e}")
        return (True, False, False)

def check_sandbox_api_status(skip_api_check=False):
    """
    Check if the sandbox API is authenticated and working.
    Does not modify the environment.
    
    Args:
        skip_api_check (bool): If True, skips the actual API call and just returns if there's a token
        
    Returns:
        tuple: (has_token, is_authenticated, is_working)
    """
    from flask import session
    
    # Check if we have a sandbox token in session
    sandbox_token = session.get('sandbox_access_token')
    has_sandbox_token = bool(sandbox_token)
    
    if not has_sandbox_token or skip_api_check:
        return (has_sandbox_token, False, False)
    
    # Try to authenticate with Sandbox API
    try:
        # Import modules directly to avoid environment issues
        import tt_data
        client = tt_data.TastyTradeMarketData(use_sandbox=True)
        sandbox_api_authenticated = client.authenticate()
        
        if sandbox_api_authenticated:
            # Try a simple API call
            test_data = client.get_market_data_clean('SPY')
            sandbox_api_working = test_data is not None
            return (True, True, sandbox_api_working)
        else:
            return (True, False, False)
    except Exception as e:
        logger.error(f"Sandbox API check failed: {e}")
        return (True, False, False)

def get_current_environment_status(skip_api_check=False):
    """
    Get the status of the current environment (production or sandbox)
    
    Args:
        skip_api_check (bool): If True, skips actual API calls
        
    Returns:
        dict: Status information for the current environment
    """
    is_production = config.IS_PRODUCTION
    
    if is_production:
        has_token, is_authenticated, is_working = check_production_api_status(skip_api_check)
        env_name = "PRODUCTION"
    else:
        has_token, is_authenticated, is_working = check_sandbox_api_status(skip_api_check)
        env_name = "SANDBOX"
    
    return {
        'environment': env_name,
        'is_production': is_production,
        'has_token': has_token,
        'is_authenticated': is_authenticated,
        'is_working': is_working
    }

def get_api_status(skip_api_check=False):
    """
    Get the status of both production and sandbox APIs.
    
    Args:
        skip_api_check (bool): If True, skips actual API calls
        
    Returns:
        dict: Status information for both environments
    """
    # Check production API
    prod_has_token, prod_is_authenticated, prod_is_working = check_production_api_status(skip_api_check)
    
    # Check sandbox API
    sandbox_has_token, sandbox_is_authenticated, sandbox_is_working = check_sandbox_api_status(skip_api_check)
    
    # Get current environment info
    is_production = config.IS_PRODUCTION
    current_env = "PRODUCTION" if is_production else "SANDBOX"
    
    return {
        'current_environment': current_env,
        'is_production': is_production,
        'production': {
            'has_token': prod_has_token,
            'is_authenticated': prod_is_authenticated,
            'is_working': prod_is_working
        },
        'sandbox': {
            'has_token': sandbox_has_token,
            'is_authenticated': sandbox_is_authenticated, 
            'is_working': sandbox_is_working
        }
    }