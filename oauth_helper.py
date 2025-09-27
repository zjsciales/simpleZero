"""
Helper function to ensure the correct URL is used when exchanging OAuth tokens
based on the callback path.
"""

import config

def adjust_oauth_url_for_path(path):
    """
    Temporarily adjusts the OAuth base URL based on the callback path
    
    Args:
        path (str): The callback path
        
    Returns:
        str: The previous base URL (to restore later)
    """
    # Store current setting
    previous_url = config.TT_OAUTH_BASE_URL
    
    # Production callback paths
    production_paths = ['/zscialesProd', '/ttProd', '/zscialespersonal', '/tt']
    
    # Sandbox callback paths
    sandbox_paths = ['/oauth/sandbox/callback', '/ttSandbox']
    
    if path in production_paths:
        # Set to production URL
        config.TT_OAUTH_BASE_URL = config.TT_API_BASE_URL
        print(f"🔧 Setting OAuth URL for production: {config.TT_OAUTH_BASE_URL}")
    elif path in sandbox_paths:
        # Set to sandbox URL
        config.TT_OAUTH_BASE_URL = config.TT_SANDBOX_BASE_URL
        print(f"🔧 Setting OAuth URL for sandbox: {config.TT_OAUTH_BASE_URL}")
    else:
        print(f"⚠️ Unknown callback path: {path}, not adjusting OAuth URL")
    
    return previous_url