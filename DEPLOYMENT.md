# Railway Deployment Guide for simpleZero

## 🚀 Environment Detection & Configuration

The app now automatically detects whether it's running in production (Railway) or development (localhost) and configures itself appropriately.

### Environment Detection Logic

The app detects production environment when:
- `RAILWAY_ENVIRONMENT` is set (Railway sets this automatically)
- `ENVIRONMENT` is explicitly set to "production"
- `PORT` environment variable is present (Railway assigns this)

### Environment-Specific Settings

#### Development (localhost):
- Base URL: `https://127.0.0.1:5001`
- TT Redirect URI: `https://127.0.0.1:5001/zscialespersonal`
- SSL: Enabled (uses local certs)
- Debug: True
- Port: 5001

#### Production (Railway/algaebot.com):
- Base URL: `https://algaebot.com`
- TT Redirect URI: `https://algaebot.com/tt`
- SSL: Disabled (Railway handles TLS termination)
- Debug: False
- Port: From Railway's `PORT` env var

## 📋 Required Environment Variables for Railway

Set these in your Railway project environment variables:

### Core Application
```
ENVIRONMENT=production
```

### API Keys
```
XAI_API_KEY=your_xai_api_key_here
TT_API_KEY_SANDBOX=your_tastytrade_sandbox_api_key
TT_API_SECRET_SANDBOX=your_tastytrade_sandbox_secret
TT_SANDBOX_BASE_URL=https://api.cert.tastyworks.com
TT_ACCOUNT_NUMBER_SANDBOX=your_sandbox_account_number
TT_USERNAME_SANDBOX=your_sandbox_username
TT_PASSWORD_SANDBOX=your_sandbox_password
```

> **Note**: Copy the actual values from your local `.env` file. Never commit API keys to Git!

### Production TastyTrade Settings (when ready for live)
```
TT_API_KEY=your_production_api_key
TT_API_SECRET=your_production_api_secret
```

## 🔧 What Changed

### 1. `config.py` - Environment Detection
- Added automatic environment detection
- Environment-aware URL configuration
- Production vs development settings
- Console logging for debugging deployment

### 2. `tt.py` - Dynamic Redirect URI
- Now imports redirect URI from config
- Automatically uses correct callback URL
- Added environment logging

### 3. `app.py` - Production-Ready Flask Config
- Environment-aware Flask settings
- Production: No SSL (Railway handles it)
- Development: SSL enabled
- Dynamic port assignment

### 4. Deployment Files
- `railway.toml` - Railway-specific configuration
- `Procfile` - Updated to use `app.py`
- `requirements.txt` - Already configured

## 🚀 Deployment Steps

1. **Push to GitHub**: Ensure all changes are committed and pushed

2. **Connect Railway to GitHub**: 
   - Link your Railway project to the `simpleZero` repository
   - Set auto-deploy on main branch

3. **Set Environment Variables**: 
   - Copy the environment variables above into Railway
   - Don't forget to set `ENVIRONMENT=production`

4. **Deploy**: Railway will automatically deploy when you push

5. **Update TastyTrade OAuth**: 
   - In your TastyTrade developer console
   - Update the redirect URI to: `https://algaebot.com/tt`

## 🔍 Monitoring Deployment

The app logs important information on startup:
```
🌍 Environment: PRODUCTION
🔗 Base URL: https://algaebot.com
🔄 TT Redirect URI: https://algaebot.com/tt
🔧 TT Module - Environment: PRODUCTION
🔧 TT Module - Redirect URI: https://algaebot.com/tt
🚀 Flask App - Environment: PRODUCTION
🚀 Flask App - Debug Mode: False
🚀 Flask App - Port: 8080
```

Look for these logs in Railway to confirm correct configuration.

## 🛠️ Troubleshooting

### Common Issues:
1. **OAuth Redirect Mismatch**: Ensure TastyTrade developer console has `https://algaebot.com/tt`
2. **Environment Variables**: Double-check all required env vars are set in Railway
3. **Port Issues**: Railway assigns PORT automatically, don't set it manually
4. **SSL Issues**: Don't enable SSL in production, Railway handles it

### Debug Commands:
Railway will show startup logs. Look for the environment detection messages to confirm proper configuration.

## 🔐 Security Notes

- `.env` file is git-ignored (good!)
- Secret keys should be unique in production
- All sensitive data in Railway environment variables
- No hardcoded URLs or secrets in code

The app is now production-ready and will automatically configure itself based on the deployment environment! 🎉