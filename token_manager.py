"""
Unified token management for environment-based authentication.
This module manages tokens for the current environment (Local=Sandbox, Railway=Production).

Railway Compatibility:
- Uses Flask session for web requests 
- Falls back to database storage for automation/background processes
- Tokens persist across Railway deployments via SQLite database
"""

from flask import session, has_request_context
import logging
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for token scope validation to reduce repeated logging
_scope_cache = {}

def set_tokens(access_token, refresh_token=None):
    """
    Safely store tokens in Flask session and database for the current environment
    Railway compatible: persists tokens across deployments via database storage
    
    Args:
        access_token (str): Access token for current environment
        refresh_token (str, optional): Refresh token for current environment
        
    Returns:
        bool: Success status
    """
    try:
        # Verify token scopes first
        token_scopes = ''
        if access_token:
            has_required_scopes, scopes = verify_token_scopes(access_token)
            if not has_required_scopes:
                logger.warning(f"⚠️ {config.ENVIRONMENT_NAME} token is missing required scopes (read/trade)!")
                logger.warning("⚠️ Trading operations may fail with this token.")
                # Continue anyway, but warn user
                
            # Store scope information
            token_scopes = ' '.join(scopes) if scopes else ''
            
            # Store in Flask session if we're in a request context
            if has_request_context():
                session['token_scopes'] = token_scopes
                session['access_token'] = access_token
        
        if refresh_token and has_request_context():
            session['refresh_token'] = refresh_token
            
        # Always store in database for Railway persistence and automation access
        try:
            from db_storage import store_tokens
            store_tokens(
                environment=config.ENVIRONMENT_NAME,
                access_token=access_token,
                refresh_token=refresh_token,
                token_scopes=token_scopes
            )
        except Exception as db_error:
            logger.warning(f"⚠️ Could not store tokens in database: {db_error}")
            # Continue with session storage only
            
        # Update TT module
        try:
            from tt import set_access_token, set_refresh_token
            set_access_token(access_token)
            if refresh_token:
                set_refresh_token(refresh_token)
        except ImportError:
            logger.warning(f"⚠️ Could not update TT module with new {config.ENVIRONMENT_NAME} tokens")
            
        logger.info(f"✅ {config.ENVIRONMENT_NAME} tokens updated successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error setting {config.ENVIRONMENT_NAME} tokens: {e}")
        return False

def get_tokens():
    """
    Get current tokens from session or database for the current environment
    Railway compatible: tries Flask session first, falls back to database storage
    
    Returns:
        tuple: (access_token, refresh_token) - either may be None
    """
    # Try Flask session first (for web requests)
    if has_request_context():
        try:
            access_token = session.get('access_token')
            refresh_token = session.get('refresh_token')
            if access_token:  # Return session tokens if available
                return access_token, refresh_token
        except Exception as e:
            logger.debug(f"Session access failed: {e}")
    
    # Fall back to database storage (for automation/background processes)
    try:
        from db_storage import get_stored_tokens
        return get_stored_tokens(config.ENVIRONMENT_NAME)
    except Exception as e:
        logger.warning(f"⚠️ Could not retrieve tokens from database: {e}")
        return None, None

def validate_token(access_token=None):
    """
    Verify if the current environment token is valid by making a simple API call
    
    Args:
        access_token (str, optional): Token to validate, or use from session if None
        
    Returns:
        bool: True if token is valid
    """
    if not access_token:
        access_token = get_tokens()[0]
        
    if not access_token:
        logger.warning(f"⚠️ No {config.ENVIRONMENT_NAME} token available to validate")
        return False
        
    try:
        # Use TT module for validation since it now uses unified config
        from tt import set_access_token, validate_access_token
        set_access_token(access_token)
        is_valid = validate_access_token()
        logger.info(f"🔍 {config.ENVIRONMENT_NAME} token validation: {'✅ Valid' if is_valid else '❌ Invalid'}")
        return is_valid
    except Exception as e:
        logger.error(f"❌ Error validating {config.ENVIRONMENT_NAME} token: {e}")
        return False
        
def get_token_status():
    """
    Get comprehensive token status for the current environment
    
    Returns:
        dict: Token status information
    """
    token, refresh_token = get_tokens()
    
    # Check token
    valid = False
    scopes = []
    if token:
        has_scopes, scopes = verify_token_scopes(token)
        valid = has_scopes
        
    return {
        'environment': config.ENVIRONMENT_NAME,
        'has_token': bool(token),
        'has_refresh_token': bool(refresh_token),
        'has_required_scopes': valid,
        'scopes': scopes
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
        
        # Check cache first to reduce repeated validations
        token_hash = hash(token[:50])  # Use first 50 chars to create cache key
        if token_hash in _scope_cache:
            cached_result = _scope_cache[token_hash]
            return cached_result['has_scopes'], cached_result['scopes']
        
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
            
            # Only log on first validation or when scopes change
            logger.info(f"🔍 Token scopes validated: {scopes} (read: {has_read}, trade: {has_trade})")
            
            # Cache the result
            result = has_read and has_trade
            _scope_cache[token_hash] = {
                'has_scopes': result,
                'scopes': scopes
            }
            
            return result, scopes
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
            
            # Check if this is the current session token
            if token == session.get('access_token'):
                scope_str = session.get('token_scopes', '')
                scopes = scope_str.split() if scope_str else []
                has_read = 'read' in scopes
                has_trade = 'trade' in scopes
                logger.info(f"🔍 Using session scopes for {config.ENVIRONMENT_NAME} token: {scopes}")
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