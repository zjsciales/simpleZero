"""
Unified OAuth helper for environment-based authentication.
This module provides simplified OAuth URL handling using environment-based configuration.
"""

import config

def get_oauth_base_url():
    """
    Get the OAuth base URL for the current environment
    
    Returns:
        str: OAuth base URL for current environment
    """
    oauth_url = config.TT_OAUTH_BASE_URL
    print(f"🔧 Using OAuth URL for {config.ENVIRONMENT_NAME}: {oauth_url}")
    return oauth_url

def validate_callback_path(path):
    """
    Validate that the callback path matches the expected unified callback
    
    Args:
        path (str): The callback path to validate
        
    Returns:
        bool: True if path is valid for current environment
    """
    expected_path = '/oauth/callback'
    is_valid = path == expected_path
    
    if is_valid:
        print(f"✅ Valid callback path for {config.ENVIRONMENT_NAME}: {path}")
    else:
        print(f"⚠️ Invalid callback path for {config.ENVIRONMENT_NAME}: {path} (expected: {expected_path})")
    
    return is_valid