"""
Helper functions for managing dual authentication tokens (Production + Sandbox).
This module abstracts token operations to ensure they are properly set across different modules.
"""

from flask import session
import logging
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def set_production_tokens(access_token, refresh_token=None):
    """
    Safely store production tokens in Flask session and update all modules
    
    Args:
        access_token (str): Production access token
        refresh_token (str, optional): Production refresh token
        
    Returns:
        bool: Success status
    """
    try:
        # First verify token scopes
        if access_token:
            # New: Verify token has required scopes
            has_required_scopes, scopes = verify_token_scopes(access_token)
            if not has_required_scopes:
                logger.warning("⚠️ Production token is missing required scopes (read/trade)!")
                logger.warning("⚠️ Trading operations may fail with this token.")
                # Continue anyway, but warn user
                
            # Store scope information
            session['prod_token_scopes'] = ' '.join(scopes) if scopes else ''
                
            # Store in Flask session
            session['prod_access_token'] = access_token
            # For backward compatibility
            session['access_token'] = access_token
        
        if refresh_token:
            session['prod_refresh_token'] = refresh_token
            # For backward compatibility
            session['refresh_token'] = refresh_token
            
        # Update TT module
        try:
            from tt import set_access_token, set_refresh_token
            set_access_token(access_token)
            if refresh_token:
                set_refresh_token(refresh_token)
        except ImportError:
            logger.warning("⚠️ Could not update TT module with new production tokens")
            
        logger.info("✅ Production tokens updated successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error setting production tokens: {e}")
        return False

def set_sandbox_tokens(access_token, refresh_token=None):
    """
    Safely store sandbox tokens in Flask session
    
    Args:
        access_token (str): Sandbox access token
        refresh_token (str, optional): Sandbox refresh token
        
    Returns:
        bool: Success status
    """
    try:
        # First verify token scopes
        if access_token:
            # New: Verify token has required scopes
            has_required_scopes, scopes = verify_token_scopes(access_token)
            if not has_required_scopes:
                logger.warning("⚠️ Sandbox token is missing required scopes (read/trade)!")
                logger.warning("⚠️ Trading operations may fail with this token.")
                # Continue anyway, but warn user
            
            # Store in Flask session
            session['sandbox_access_token'] = access_token
            
            # Store scope information
            session['sandbox_token_scopes'] = ' '.join(scopes) if scopes else ''
        
        if refresh_token:
            session['sandbox_refresh_token'] = refresh_token
            
        # Update trader module if needed
        # No direct update to trader.py needed since it fetches from session directly
            
        logger.info("✅ Sandbox tokens updated successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error setting sandbox tokens: {e}")
        return False

def get_production_tokens():
    """
    Get current production tokens from session
    
    Returns:
        tuple: (access_token, refresh_token) - either may be None
    """
    access_token = session.get('prod_access_token') or session.get('access_token')
    refresh_token = session.get('prod_refresh_token') or session.get('refresh_token')
    return access_token, refresh_token

def get_sandbox_tokens():
    """
    Get current sandbox tokens from session
    
    Returns:
        tuple: (access_token, refresh_token) - either may be None
    """
    return session.get('sandbox_access_token'), session.get('sandbox_refresh_token')

def validate_production_token(access_token=None):
    """
    Verify if a production token is valid by making a simple API call
    
    Args:
        access_token (str, optional): Token to validate, or use from session if None
        
    Returns:
        bool: True if token is valid
    """
    if not access_token:
        access_token = get_production_tokens()[0]
        
    if not access_token:
        logger.warning("⚠️ No production token available to validate")
        return False
        
    try:
        # Temporarily ensure we're in production mode
        previous_mode = config.USE_SANDBOX_MODE
        config.set_sandbox_mode(False)
        
        try:
            # Use TT module for validation
            from tt import set_access_token, validate_access_token
            set_access_token(access_token)
            is_valid = validate_access_token()
            logger.info(f"🔍 Production token validation: {'✅ Valid' if is_valid else '❌ Invalid'}")
            return is_valid
        finally:
            # Restore previous sandbox mode
            config.set_sandbox_mode(previous_mode)
    except Exception as e:
        logger.error(f"❌ Error validating production token: {e}")
        return False

def validate_sandbox_token(access_token=None):
    """
    Verify if a sandbox token is valid by making a simple API call
    
    Args:
        access_token (str, optional): Token to validate, or use from session if None
        
    Returns:
        bool: True if token is valid
    """
    if not access_token:
        access_token = get_sandbox_tokens()[0]
        
    if not access_token:
        logger.warning("⚠️ No sandbox token available to validate")
        return False
        
    try:
        # Temporarily ensure we're in sandbox mode
        previous_mode = config.USE_SANDBOX_MODE
        config.set_sandbox_mode(True)
        
        try:
            # Use trader module for validation
            from trader import TastyTradeAPI
            api = TastyTradeAPI()
            api.trading_token = access_token
            
            # Try to get accounts as a validation
            accounts = api.get_accounts()
            is_valid = len(accounts) > 0
            
            logger.info(f"🔍 Sandbox token validation: {'✅ Valid' if is_valid else '❌ Invalid'}")
            return is_valid
        finally:
            # Restore previous sandbox mode
            config.set_sandbox_mode(previous_mode)
    except Exception as e:
        logger.error(f"❌ Error validating sandbox token: {e}")
        return False
        
def get_token_status():
    """
    Get comprehensive token status for both environments
    
    Returns:
        dict: Token status information
    """
    prod_token, prod_refresh = get_production_tokens()
    sandbox_token, sandbox_refresh = get_sandbox_tokens()
    
    # Check production token
    prod_valid = False
    prod_scopes = []
    if prod_token:
        prod_has_scopes, prod_scopes = verify_token_scopes(prod_token)
        prod_valid = prod_has_scopes
        
    # Check sandbox token
    sandbox_valid = False
    sandbox_scopes = []
    if sandbox_token:
        sandbox_has_scopes, sandbox_scopes = verify_token_scopes(sandbox_token)
        sandbox_valid = sandbox_has_scopes
        
    return {
        'production': {
            'has_token': bool(prod_token),
            'has_refresh_token': bool(prod_refresh),
            'has_required_scopes': prod_valid,
            'scopes': prod_scopes
        },
        'sandbox': {
            'has_token': bool(sandbox_token),
            'has_refresh_token': bool(sandbox_refresh),
            'has_required_scopes': sandbox_valid,
            'scopes': sandbox_scopes
        }
    }

def verify_token_scopes(token):
    """
    Verify that a token has the required scopes for trading
    
    Args:
        token (str): OAuth token to verify
        
    Returns:
        tuple: (has_required_scopes, scopes_list)
    """
    try:
        # Handle empty or None token
        if not token:
            logger.warning("⚠️ No token provided for scope verification")
            return False, []
        
        # First try to decode as JWT using PyJWT library
        try:
            import jwt
            
            # Decode token without verification (we just need the payload)
            token_data = jwt.decode(token, options={"verify_signature": False})
            
            # Extract scope information
            scope_str = token_data.get('scope', '')
            # Handle both space-separated string and array formats
            if isinstance(scope_str, list):
                scopes = scope_str
            else:
                scopes = scope_str.split()
            
            # Check for required scopes
            has_read = 'read' in scopes
            has_trade = 'trade' in scopes
            has_openid = 'openid' in scopes
            
            logger.info(f"🔍 Token scopes (JWT): {scopes}")
            logger.info(f"✅ Has read scope: {has_read}")
            logger.info(f"✅ Has trade scope: {has_trade}")
            logger.info(f"✅ Has openid scope: {has_openid}")
            
            return has_read and has_trade, scopes
        except ImportError:
            logger.warning("⚠️ PyJWT not available, falling back to manual JWT decoding")
            # Fall back to manual decoding if PyJWT is not available
            import base64
            import json
            
            # JWT tokens have three parts separated by dots
            if '.' in token and len(token.split('.')) == 3:
                # Get the payload part (second part)
                payload = token.split('.')[1]
                
                # Add padding if needed
                padding = len(payload) % 4
                if padding:
                    payload += '=' * (4 - padding)
                
                # Decode base64
                try:
                    decoded = base64.b64decode(payload).decode('utf-8')
                    token_data = json.loads(decoded)
                    
                    # Extract scope information
                    scope_str = token_data.get('scope', '')
                    # Handle both space-separated string and array formats
                    if isinstance(scope_str, list):
                        scopes = scope_str
                    else:
                        scopes = scope_str.split()
                    
                    # Check for required scopes
                    has_read = 'read' in scopes
                    has_trade = 'trade' in scopes
                    has_openid = 'openid' in scopes
                    
                    logger.info(f"🔍 Token scopes (manual): {scopes}")
                    logger.info(f"✅ Has read scope: {has_read}")
                    logger.info(f"✅ Has trade scope: {has_trade}")
                    logger.info(f"✅ Has openid scope: {has_openid}")
                    
                    return has_read and has_trade, scopes
                except Exception as decode_error:
                    logger.warning(f"⚠️ Base64 decode failed: {decode_error}")
            else:
                logger.warning("⚠️ Token does not appear to be in JWT format")
        except Exception as jwt_error:
            logger.warning(f"⚠️ JWT parsing failed: {jwt_error}")
        
        # As a fallback, check if we have stored scopes in the session
        try:
            from flask import session
            
            # For sandbox tokens
            if token == session.get('sandbox_access_token'):
                scope_str = session.get('sandbox_token_scopes', '')
                scopes = scope_str.split() if scope_str else []
                has_read = 'read' in scopes
                has_trade = 'trade' in scopes
                logger.info(f"🔍 Using session scopes for sandbox token: {scopes}")
                return has_read and has_trade, scopes
                
            # For production tokens
            if token == session.get('prod_access_token') or token == session.get('access_token'):
                scope_str = session.get('prod_token_scopes', '')
                scopes = scope_str.split() if scope_str else []
                has_read = 'read' in scopes
                has_trade = 'trade' in scopes
                logger.info(f"🔍 Using session scopes for prod token: {scopes}")
                return has_read and has_trade, scopes
                
        except (ImportError, RuntimeError) as session_error:
            logger.warning(f"⚠️ Could not access session for scope verification: {session_error}")
        
        # Final fallback - assume token has permission if in correct format
        if token and token.startswith('ey') and '.' in token and len(token.split('.')) == 3:
            logger.warning("⚠️ Could not verify token scopes - assuming valid token has trading permission")
            return True, ['assumed_read', 'assumed_trade', 'assumed_openid']
        
        # Default assumption - can't verify scopes
        logger.warning("⚠️ Could not verify token scopes - token format invalid")
        return False, []
    except Exception as e:
        logger.error(f"❌ Error verifying token scopes: {e}")
        return False, []