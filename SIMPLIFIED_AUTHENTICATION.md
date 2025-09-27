# Simplified Authentication System

## Overview

This document explains the new simplified authentication system for the SPY Options Trading Dashboard. The system now follows a "environment-determines-API" model:

- **Local/Development** environment always uses **TastyTrade Sandbox API**
- **Production/Railway** environment always uses **TastyTrade Production API**

This eliminates the need for runtime toggling between sandbox and production modes, reducing complexity and potential for errors.

> **Note:** The system maintains backward compatibility with existing routes but uses environment-based authentication internally.

## Key Changes

1. **Environment Detection**
   - Uses `IS_PRODUCTION` flag determined by:
     - `RAILWAY_ENVIRONMENT` presence
     - `ENVIRONMENT=production` setting
     - `PORT` environment variable (set by Railway)
   - No more runtime toggling with `set_sandbox_mode`

2. **Unified Login Flow**
   - Single `/login` endpoint that automatically uses the appropriate API
   - Backward compatible with old `/prod_login` and `/sandbox_login` routes
   - User is visibly informed which environment they're using

3. **Token Storage**
   - Production tokens stored in `session['prod_access_token']`
   - Sandbox tokens stored in `session['sandbox_access_token']`
   - Code automatically selects the right token based on environment

4. **OpenID Integration**
   - OpenID scope included in all OAuth requests
   - Enables future integration with standard OpenID Connect for user management

## Implementation Details

### Environment Detection

```python
# In config.py
IS_PRODUCTION = (
    os.getenv('RAILWAY_ENVIRONMENT') is not None or  # Railway deployment
    os.getenv('ENVIRONMENT') == 'production' or      # Explicit production setting
    os.getenv('PORT') is not None                    # Railway sets PORT
)

# Based on environment, we select API endpoints
if IS_PRODUCTION:
    # Production settings
    TT_OAUTH_BASE_URL = TT_PROD_BASE_URL
    TT_TRADING_BASE_URL = TT_PROD_BASE_URL
    TRADING_MODE = "PRODUCTION"
else:
    # Development settings
    TT_OAUTH_BASE_URL = TT_SANDBOX_BASE_URL
    TT_TRADING_BASE_URL = TT_SANDBOX_BASE_URL
    TRADING_MODE = "SANDBOX"
```

### Login Flow

```python
@app.route('/login')
def login():
    """Environment-based login with appropriate API"""
    is_production = config.IS_PRODUCTION
    
    # Get the appropriate auth URL based on environment
    if is_production:
        auth_url = get_oauth_authorization_url(is_sandbox=False)  # Production
    else:
        auth_url = get_oauth_authorization_url(is_sandbox=True)   # Sandbox
        
    return redirect(auth_url)
```

### Token Storage and Verification

```python
# Get the appropriate token based on environment
is_production = config.IS_PRODUCTION

if is_production:
    token = session.get('prod_access_token')
else:
    token = session.get('sandbox_access_token')
```

## User Interface

- The login screen dynamically shows which environment is being used
- A persistent banner at the top of the dashboard indicates whether the user is connected to SANDBOX or PRODUCTION API
- Color coding (green for sandbox, red for production) provides additional visual distinction

## Future Enhancements

1. **Full OpenID Connect Integration**
   - User profile data from TastyTrade
   - Standard authentication flows
   - Session management

2. **Persistent User Accounts**
   - Associate data with specific users
   - User preferences and settings

3. **Multi-Account Support**
   - Support for multiple TastyTrade accounts per user
   - Account switching within the interface

## Migration Notes

This change maintains backward compatibility with existing routes and session storage, while simplifying the overall authentication flow. Previously saved tokens will continue to work, and old routes will redirect to the new unified system.

### Compatibility Routes

The following legacy routes are maintained for backward compatibility:

- `/prod_login` - Redirects to the main login using production mode
- `/sandbox_login` - Redirects to the main login using sandbox mode
- `/sandbox-auth` - Legacy route that redirects to `/sandbox_login`
- `/login?sandbox=true` - Legacy parameter support that redirects to sandbox login

These routes ensure that existing bookmarks and links continue to work, but they all use the new environment-based authentication system internally.