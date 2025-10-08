# Simple Flask app with SSL and TastyTrade OAuth2
from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime
import os
import logging
from tt import get_oauth_authorization_url, exchange_code_for_token, set_access_token, set_refresh_token, get_market_data, get_oauth_token, get_options_chain, get_trading_range, get_options_chain_by_date, get_account_balances, get_account_positions
import config
import uuid
import db_storage  # Import our database storage module
from collections import defaultdict

# Import public routes
try:
    from public_routes import public_routes
    PUBLIC_ROUTES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Public routes not available: {e}")
    PUBLIC_ROUTES_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_in_production'

# Register public routes blueprint
if PUBLIC_ROUTES_AVAILABLE:
    app.register_blueprint(public_routes)
    print("✅ Public routes registered")

# Set Flask configuration based on environment
app.config['DEBUG'] = config.DEBUG
app.config['ENV'] = config.FLASK_ENV

# In-memory store for trade data to avoid session cookie bloat
# Kept for backward compatibility but we'll primarily use db_storage now
trade_store = defaultdict(dict)

def get_user_session_id():
    """Get or create a unique session ID for the user"""
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid.uuid4())
    return session['user_session_id']

def store_trade_data(trade_type, data):
    """
    Store trade data in both memory store (for backward compatibility) 
    and persistent database storage
    """
    # Get session ID for the current user
    session_id = get_user_session_id()
    
    # Still store in memory for backward compatibility
    trade_store[session_id][trade_type] = data
    
    # Extract ticker and DTE if available
    ticker = None
    dte = None
    if isinstance(data, dict):
        ticker = data.get('ticker') or data.get('underlying') or data.get('symbol')
        dte = data.get('dte')
    
    # Store in persistent database
    db_storage.store_data(
        data_type=trade_type,
        data=data,
        session_id=session_id,
        ticker=ticker,
        dte=dte
    )

print(f"🚀 Flask App - Environment: {'PRODUCTION' if config.IS_PRODUCTION else 'DEVELOPMENT'}")
print(f"🚀 Flask App - Debug Mode: {config.DEBUG}")
print(f"🚀 Flask App - Port: {config.PORT}")

@app.route('/health')
def health_check():
    """Health check endpoint for Railway deployment"""
    try:
        # Test database connection
        from unified_database import DatabaseManager
        db_manager = DatabaseManager()
        
        # Simple query to test database connectivity
        if hasattr(db_manager, 'test_connection'):
            db_status = db_manager.test_connection()
        else:
            db_status = True  # Assume OK if no test method
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'environment': config.ENVIRONMENT_NAME,
            'database': 'connected' if db_status else 'disconnected'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503

@app.route('/')
def home():
    """Home page - redirect to login if not authenticated, dashboard if authenticated"""
    token = session.get('access_token')
    if token:
        return redirect('/dashboard')
    else:
        return render_template('login.html', 
                             environment=config.ENVIRONMENT_NAME,
                             oauth_base_url=config.TT_OAUTH_BASE_URL)

@app.route('/dashboard')
def dashboard():
    """Main dashboard page - requires authentication"""
    token = session.get('access_token')
    if not token:
        return redirect('/')
    
    # Ensure tt.py has the token
    set_access_token(token)
    return render_template('dashboard.html',
                         environment=config.ENVIRONMENT_NAME,
                         authenticated=True,
                         config=config)

@app.route('/login')
def login():
    """Redirect to TastyTrade OAuth2 authorization"""
    auth_url = get_oauth_authorization_url()
    print(f"🔗 Redirecting to: {auth_url}")
    return redirect(auth_url)

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth2 callback from TastyTrade for current environment"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    print(f"🔐 OAuth callback received for {config.ENVIRONMENT_NAME} environment")
    print(f"🔐 Code: {code[:20]}..." if code else "No code")
    print(f"🔐 State: {state}")
    print(f"🔐 Error: {error}" if error else "No error")
    
    if error:
        return f"OAuth Error: {error}", 400
    
    if not code:
        return "No authorization code received", 400
    
    # Exchange code for token using unified configuration
    print(f"🔐 Exchanging code for {config.ENVIRONMENT_NAME} token...")
    token_data = exchange_code_for_token(code)
    
    if token_data and token_data.get('access_token'):
        print(f"🔐 Successfully received {config.ENVIRONMENT_NAME} tokens!")
        
        # Store tokens using unified token manager
        from token_manager import set_tokens
        success = set_tokens(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token')
        )
        
        if success:
            print(f"🔐 Redirecting to dashboard...")
            return redirect('/dashboard')
        else:
            print(f"🔐 Failed to store {config.ENVIRONMENT_NAME} tokens")
            return f"Failed to store {config.ENVIRONMENT_NAME} tokens", 500
    else:
        print(f"🔐 Failed to exchange code for {config.ENVIRONMENT_NAME} token")
        return f"Failed to exchange code for {config.ENVIRONMENT_NAME} token", 500

# Legacy OAuth callback routes for backward compatibility
@app.route('/zscialespersonal')
@app.route('/tt') 
@app.route('/zscialesProd')
@app.route('/ttProd')
def legacy_oauth_callback():
    """Legacy OAuth callback routes - redirect to unified callback"""
    print(f"⚠️ Legacy OAuth callback accessed: {request.path}")
    print(f"� Redirecting to unified OAuth callback for {config.ENVIRONMENT_NAME}")
    
    # Preserve query parameters for the redirect
    query_string = request.query_string.decode('utf-8')
    redirect_url = f'/oauth/callback?{query_string}' if query_string else '/oauth/callback'
    
    return redirect(redirect_url)

@app.route('/status')
def status():
    """Check authentication status"""
    token = session.get('access_token') or get_oauth_token()
    
    if token:
        return jsonify({
            'authenticated': True,
            'token_length': len(token),
            'token_preview': token[:20] + '...'
        })
    else:
        return jsonify({
            'authenticated': False,
            'message': 'No valid token found'
        })

@app.route('/market-data')
def market_data():
    """Test market data retrieval with authentication"""
    token = session.get('access_token')
    
    if not token:
        return """
        <h1>❌ Not Authenticated</h1>
        <p>You need to authenticate first to access market data.</p>
        <p><a href="/login">Login with TastyTrade</a></p>
        <p><a href="/">Home</a></p>
        """
    
    # Ensure tt.py has the token
    set_access_token(token)
    
    # Try to get market data
    try:
        market_info = get_market_data()
        
        if market_info:
            return f"""
            <h1>📊 Market Data for {market_info['symbol']}</h1>
            <table border="1" style="border-collapse: collapse; margin: 20px 0;">
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Current Price</td><td>${market_info['current_price']:.2f}</td></tr>
                <tr><td>Price Change</td><td>${market_info['price_change']:.2f}</td></tr>
                <tr><td>Percent Change</td><td>{market_info['percent_change']:.2f}%</td></tr>
                <tr><td>Bid</td><td>${market_info['bid']:.2f}</td></tr>
                <tr><td>Ask</td><td>${market_info['ask']:.2f}</td></tr>
                <tr><td>Volume</td><td>{market_info['volume']:,}</td></tr>
            </table>
            <p><a href="/market-data">Refresh</a> | <a href="/">Home</a></p>
            """
        else:
            return """
            <h1>❌ Market Data Failed</h1>
            <p>Unable to retrieve market data. Check the terminal for details.</p>
            <p><a href="/market-data">Try Again</a> | <a href="/">Home</a></p>
            """
    except Exception as e:
        return f"""
        <h1>❌ Error</h1>
        <p>Error retrieving market data: {str(e)}</p>
        <p><a href="/market-data">Try Again</a> | <a href="/">Home</a></p>
        """

@app.route('/api/market-data')
def api_market_data():
    """API endpoint for market data (JSON response)"""
    token = session.get('access_token')
    refresh_token = session.get('refresh_token')
    
    print(f"🔍 Flask session check:")
    print(f"  - Has access_token: {bool(token)}")
    print(f"  - Has refresh_token: {bool(refresh_token)}")
    if token:
        print(f"  - Token preview: {token[:20]}...")
    print(f"  - Session keys: {list(session.keys())}")
    
    if not token:
        print("❌ No access token in session")
        return jsonify({'error': 'Authentication required'}), 401
    
    # Ensure tt.py has both tokens
    print("🔄 Setting tokens in tt.py module")
    set_access_token(token)
    if refresh_token:
        set_refresh_token(refresh_token)
    
    # Try to get market data
    try:
        print("📞 Calling get_market_data() function")
        market_info = get_market_data()
        
        if market_info:
            print("✅ Market data retrieved successfully")
            return jsonify(market_info)
        else:
            print("❌ Market data function returned None")
            return jsonify({'error': 'Market data unavailable'}), 503
    except Exception as e:
        print(f"💥 Exception in market data retrieval: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account-balance')
def api_account_balance():
    """API endpoint for account balance data"""
    try:
        print("🔍 Flask session check for account balance:")
        print(f"  - Has access_token: {'access_token' in session}")
        print(f"  - Environment: {config.ENVIRONMENT_NAME}")
        
        # Check authentication first
        if 'access_token' not in session:
            print("❌ No access token in session")
            return jsonify({'error': 'Authentication required'}), 401
        
        # Set tokens in tt.py module
        print("🔄 Setting tokens in tt.py module for balance lookup")
        if 'access_token' in session:
            set_access_token(session['access_token'])
        if 'refresh_token' in session:
            set_refresh_token(session['refresh_token'])
        
        # Get account balance data
        print("💰 Calling get_account_balances() function")
        from tt import get_account_balances
        balance_data = get_account_balances()
        
        if balance_data and balance_data.get('success'):
            print(f"✅ Account balance retrieved successfully")
            return jsonify(balance_data)
        else:
            print(f"❌ Failed to get account balance")
            return jsonify({
                'success': False,
                'error': 'Could not retrieve account balance'
            }), 500
            
    except Exception as e:
        print(f"💥 Exception in account balance retrieval: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sync-positions', methods=['POST'])
def api_sync_positions():
    """Sync live positions from TastyTrade to database"""
    if not session.get('access_token'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        set_access_token(session.get('access_token'))
        
        # Get live positions from TastyTrade
        positions = get_account_positions()
        
        if positions is None:
            logger.error("❌ Could not retrieve positions from TastyTrade")
            return jsonify({
                'success': False,
                'error': 'Could not retrieve positions from TastyTrade'
            }), 500
        
        logger.info(f"📊 Retrieved {len(positions)} positions from TastyTrade")
        
        # Import unified database for storing positions
        from unified_database import db_manager
        
        # Clear existing OPEN trades for SPY to avoid duplicates
        # (We'll replace them with fresh data from TastyTrade)
        clear_query = "DELETE FROM trades WHERE status = 'OPEN' AND ticker = 'SPY'"
        try:
            db_manager.execute_query(clear_query, fetch=False)
            logger.info("✅ Cleared existing OPEN SPY trades")
        except Exception as e:
            logger.error(f"❌ Failed to clear existing trades: {e}")
        
        synced_count = 0
        
        # Convert positions to trade records
        for position in positions:
            try:
                logger.info(f"🔄 Processing position: {position['symbol']}")
                
                # Generate a trade ID based on the position
                trade_id = f"TT_{position['underlying_symbol']}_{position['expiration_date']}_{position['strike_price']:.0f}{position['option_type'][0]}"
                
                # Determine strategy type based on position quantity
                if position['quantity'] > 0:
                    strategy_type = f"Long {position['option_type']}"
                else:
                    strategy_type = f"Short {position['option_type']}"
                
                logger.info(f"  💼 Trade ID: {trade_id}, Strategy: {strategy_type}")
                
                # Insert position as a trade record
                insert_query = """
                INSERT INTO trades (
                    trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
                    short_strike, long_strike, quantity, entry_premium_received, 
                    entry_underlying_price, status, current_underlying_price, 
                    current_itm_status, last_price_update, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """ if db_manager.use_postgresql else """
                INSERT INTO trades (
                    trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
                    short_strike, long_strike, quantity, entry_premium_received, 
                    entry_underlying_price, status, current_underlying_price, 
                    current_itm_status, last_price_update, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                params = (
                    trade_id,
                    position['underlying_symbol'],
                    strategy_type,
                    position.get('days_to_expiration', 0),
                    position.get('created_at', datetime.now().isoformat()),
                    position['expiration_date'],
                    position['strike_price'],
                    position['strike_price'],  # For single options, short/long strike are same
                    abs(position['quantity']),
                    position['average_open_price'] * abs(position['quantity']) * 100,  # Convert to premium
                    0,  # We don't have underlying price at entry from positions
                    'OPEN',
                    0,  # Current underlying price - would need separate API call
                    'UNKNOWN',  # ITM status - would need current market data
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                )
                
                db_manager.execute_query(insert_query, params, fetch=False)
                synced_count += 1
                logger.info(f"  ✅ Synced position: {trade_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to sync position {position.get('symbol', 'unknown')}: {e}")
                continue
        
        logger.info(f"🎉 Sync complete: {synced_count}/{len(positions)} positions synced")
        
        return jsonify({
            'success': True,
            'message': f'Synced {synced_count} positions from TastyTrade',
            'positions_found': len(positions),
            'positions_synced': synced_count
        })
        
    except Exception as e:
        print(f"💥 Exception in position sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/options-chain')
def api_options_chain():
    """API endpoint for options chain data"""
    try:
        print("🔍 Flask session check:")
        print(f"  - Has access_token: {'access_token' in session}")
        print(f"  - Has refresh_token: {'refresh_token' in session}")
        
        # Check authentication first
        if 'access_token' not in session:
            print("❌ No access token in session")
            return jsonify({'error': 'Authentication required'}), 401
        
        if 'access_token' in session:
            token_preview = session['access_token'][:20] + '...' if len(session['access_token']) > 20 else session['access_token']
            print(f"  - Token preview: {token_preview}")
        
        print(f"  - Session keys: {list(session.keys())}")
        
        # Set tokens in tt.py module
        print("🔄 Setting tokens in tt.py module")
        if 'access_token' in session:
            set_access_token(session['access_token'])
        if 'refresh_token' in session:
            set_refresh_token(session['refresh_token'])
        
        # Get request parameters
        ticker = request.args.get('ticker', 'SPY').upper()
        limit = int(request.args.get('limit', 50))
        dte_only = request.args.get('dte_only', 'true').lower() == 'true'
        dte = request.args.get('dte')
        if dte:
            dte = int(dte)
        option_type = request.args.get('option_type')  # 'call', 'put', or None
        
        # Strike range parameters
        strike_min = request.args.get('strike_min')
        strike_max = request.args.get('strike_max')
        strike_range = None
        if strike_min or strike_max:
            strike_range = {}
            if strike_min:
                strike_range['min'] = float(strike_min)
            if strike_max:
                strike_range['max'] = float(strike_max)
        
        print(f"📞 Calling get_options_chain() function")
        print(f"📋 Parameters: ticker={ticker}, limit={limit}, dte_only={dte_only}, dte={dte}, option_type={option_type}, strike_range={strike_range}")
        
        # Call the options chain function
        options_info = get_options_chain(
            ticker=ticker,
            limit=limit,
            dte_only=dte_only,
            dte=dte,
            strike_range=strike_range,
            option_type=option_type
        )
        
        if options_info:
            print(f"✅ Options chain data retrieved successfully!")
            return jsonify(options_info)
        else:
            print("❌ Options chain function returned None")
            return jsonify({'error': 'Options chain data unavailable'}), 503
    except Exception as e:
        print(f"💥 Exception in options chain retrieval: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/available-dtes')
def api_available_dtes():
    """API endpoint to get available DTEs for a ticker"""
    from market_data import get_available_dtes
    
    try:
        # Get ticker from query params (default to SPY)
        ticker = request.args.get('ticker', 'SPY').upper()
        print(f"🔍 Getting available DTEs for {ticker}")
        
        # Check authentication
        if 'access_token' not in session:
            print("❌ No access token in session")
            return jsonify({'error': 'Not authenticated'}), 401
        
        available_dtes = get_available_dtes(ticker)
        
        if available_dtes:
            print(f"✅ Found {len(available_dtes)} available DTEs for {ticker}")
            return jsonify({
                'success': True,
                'ticker': ticker,
                'available_dtes': available_dtes,
                'count': len(available_dtes)
            })
        else:
            print(f"❌ No DTEs available for {ticker}")
            return jsonify({'error': f'No DTEs available for {ticker}'}), 404
            
    except Exception as e:
        print(f"💥 Exception getting available DTEs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-options')
def debug_options():
    """Debug endpoint to inspect raw options data"""
    try:
        # Check authentication first
        if 'access_token' not in session:
            print("❌ No access token in session")
            return jsonify({'error': 'Authentication required'}), 401
        
        print("🔧 Debug options endpoint called")
        ticker = request.args.get('ticker', 'SPY')
        
        # Get raw options chain data
        from market_data import get_compact_options_chain
        from tt import parse_option_symbol
        raw_data = get_compact_options_chain(ticker)
        
        # Process the data to extract useful information
        all_options = []
        expiration_dates = set()
        
        print(f"🔍 Raw data type: {type(raw_data)}")
        print(f"🔍 Raw data keys: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'Not a dict'}")
        
        if isinstance(raw_data, dict) and raw_data.get('success') and 'symbols' in raw_data:
            symbols = raw_data['symbols']
            print(f"🔍 Found {len(symbols)} symbols in raw_data['symbols']")
            
            for symbol in symbols:
                if isinstance(symbol, str):
                    # Parse the option symbol
                    parsed = parse_option_symbol(symbol)
                    if parsed:
                        option_info = {
                            'symbol': symbol,
                            'expiration_date': parsed.get('expiration_date', 'Unknown'),
                            'strike_price': parsed.get('strike_price', 'Unknown'),
                            'option_type': parsed.get('option_type', 'Unknown'),
                            'underlying': parsed.get('underlying', 'Unknown')
                        }
                        all_options.append(option_info)
                        
                        # Track expiration dates
                        exp_date = parsed.get('expiration_date')
                        if exp_date:
                            expiration_dates.add(exp_date)
                    else:
                        print(f"⚠️ Could not parse symbol: {symbol}")
        else:
            print(f"🔍 Raw data format not as expected. Success: {raw_data.get('success')}, has symbols: {'symbols' in raw_data}")
        
        # Sort expiration dates
        sorted_expirations = sorted(list(expiration_dates))
        
        # Get sample options (first 1000)
        sample_options = all_options[:1000]
        
        return jsonify({
            'success': True,
            'ticker': ticker,
            'total_options': len(all_options),
            'unique_expirations': len(sorted_expirations),
            'response_type': str(type(raw_data)),
            'raw_response_keys': list(raw_data.keys()) if isinstance(raw_data, dict) else [],
            'expiration_dates': sorted_expirations,
            'sample_options': sample_options,
            'raw_data_preview': str(raw_data)[:1000],  # First 1000 chars for debugging
            'raw_symbols_count': len(raw_data.get('symbols', [])) if isinstance(raw_data, dict) else 0
        })
    except Exception as e:
        print(f"💥 Exception in debug options: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading-range')
def api_trading_range():
    """API endpoint for trading range calculation"""
    try:
        print("🔍 Flask session check:")
        print(f"  - Has access_token: {'access_token' in session}")
        print(f"  - Has refresh_token: {'refresh_token' in session}")
        
        # Check authentication first
        if 'access_token' not in session:
            print("❌ No access token in session")
            return jsonify({'error': 'Authentication required'}), 401
        
        # Set tokens in tt.py module
        print("🔄 Setting tokens in tt.py module")
        if 'access_token' in session:
            set_access_token(session['access_token'])
        if 'refresh_token' in session:
            set_refresh_token(session['refresh_token'])
        
        # Get request parameters
        ticker = request.args.get('ticker', 'SPY').upper()
        current_price = request.args.get('current_price')
        if current_price:
            current_price = float(current_price)
        range_percent = request.args.get('range_percent')
        if range_percent:
            range_percent = float(range_percent)
        dte = request.args.get('dte')
        if dte:
            dte = int(dte)
        
        print(f"📞 Calling get_trading_range() function")
        print(f"📋 Parameters: ticker={ticker}, current_price={current_price}, range_percent={range_percent}, dte={dte}")
        
        # Call the trading range function
        range_info = get_trading_range(
            ticker=ticker,
            current_price=current_price,
            range_percent=range_percent,
            dte=dte
        )
        
        if range_info:
            print(f"✅ Trading range calculated successfully!")
            return jsonify(range_info)
        else:
            print("❌ Trading range function returned None")
            return jsonify({'error': 'Trading range calculation failed'}), 503
    except Exception as e:
        print(f"💥 Exception in trading range calculation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options-by-date')
def api_options_by_date():
    """API endpoint for options chain by expiration date"""
    try:
        print("🔍 Flask session check:")
        print(f"  - Has access_token: {'access_token' in session}")
        print(f"  - Has refresh_token: {'refresh_token' in session}")
        
        # Check authentication first
        if 'access_token' not in session:
            print("❌ No access token in session")
            return jsonify({'error': 'Authentication required'}), 401
        
        # Set tokens in tt.py module
        print("🔄 Setting tokens in tt.py module")
        if 'access_token' in session:
            set_access_token(session['access_token'])
        if 'refresh_token' in session:
            set_refresh_token(session['refresh_token'])
        
        # Get request parameters
        ticker = request.args.get('ticker', 'SPY').upper()
        expiration_date = request.args.get('expiration_date')
        
        if not expiration_date:
            return jsonify({'error': 'expiration_date parameter is required (format: YYYY-MM-DD)'}), 400
        
        print(f"📞 Calling get_options_chain_by_date() function")
        print(f"📋 Parameters: ticker={ticker}, expiration_date={expiration_date}")
        
        # Call the options chain by date function
        options_info = get_options_chain_by_date(
            ticker=ticker,
            expiration_date=expiration_date
        )
        
        if options_info:
            print(f"✅ Options chain by date retrieved successfully!")
            return jsonify(options_info)
        else:
            print("❌ Options chain by date function returned None")
            return jsonify({'error': 'Options chain by date not available'}), 503
    except Exception as e:
        print(f"💥 Exception in options chain by date retrieval: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-prompt', methods=['POST'])
def generate_prompt():
    """API endpoint to generate and preview the Grok prompt"""
    try:
        token = session.get('access_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # Import with dte_manager mock
        import sys
        if 'dte_manager' not in sys.modules:
            sys.modules['dte_manager'] = type(sys)('dte_manager')
            sys.modules['dte_manager'].get_current_dte = lambda: 0
            sys.modules['dte_manager'].dte_manager = type('DTEManager', (), {
                'get_current_dte': lambda self=None: 0,
                'get_dte_config': lambda self, dte=0: {'period': '1d', 'interval': '1m', 'data_points': 100},
                'get_dte_summary': lambda self=None: {'display_name': f'{getattr(self, "current_dte", 0)}DTE' if self else '0DTE'},
                'current_dte': 0,
                'get_dte_display_name': lambda self, dte=0: f'{dte}DTE'
            })()
        
        # Get request data
        data = request.get_json() or {}
        dte = data.get('dte', 0)
        ticker = data.get('ticker', 'SPY')
        
        # Generate the prompt using our enhanced comprehensive analysis system
        try:
            # Import our enhanced analysis functions
            from grok import get_comprehensive_market_data, format_market_analysis_prompt_v7_comprehensive
            
            print(f"🎯 Generating comprehensive analysis for {ticker} with {dte}DTE...")
            
            # Get comprehensive market data using our enhanced system
            market_data = get_comprehensive_market_data(ticker, dte)
            
            # Generate prompt using our enhanced formatting (only takes market_data parameter)
            prompt = format_market_analysis_prompt_v7_comprehensive(market_data)
            
            print(f"✅ Generated enhanced prompt with {len(prompt)} characters of comprehensive analysis")
            
        except Exception as analysis_error:
            print(f"⚠️  Enhanced analysis failed, using fallback: {analysis_error}")
            # Fallback to basic prompt if enhanced analysis fails
            prompt = f"""Analyze the current market conditions for {ticker} with {dte}DTE focus:

Market Analysis Request:
- Ticker: {ticker}
- Days to Expiration: {dte}
- Analysis Type: {"Intraday scalping" if dte == 0 else f"{dte}-day swing trading"}
- Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}

Please provide comprehensive market analysis with technical indicators, volume analysis, and options chain insights."""

        return jsonify({
            'success': True,
            'prompt': prompt,
            'ticker': ticker,
            'dte': dte
        })
        
    except Exception as e:
        print(f"💥 Exception in prompt generation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/grok-analysis', methods=['POST'])
def grok_analysis():
    """API endpoint for Grok market analysis"""
    try:
        token = session.get('access_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # Ensure tt.py has the token
        set_access_token(token)
        
        # Import grok functions (with error handling for dte_manager)
        try:
            from grok import GrokAnalyzer, get_comprehensive_market_data
        except ImportError as e:
            # Mock dte_manager if needed
            import sys
            if 'dte_manager' not in sys.modules:
                sys.modules['dte_manager'] = type(sys)('dte_manager')
                sys.modules['dte_manager'].get_current_dte = lambda: 0
                sys.modules['dte_manager'].dte_manager = type('DTEManager', (), {
                    'get_current_dte': lambda self=None: 0,
                    'get_dte_config': lambda self, dte=0: {'period': '1d', 'interval': '1m', 'data_points': 100},
                    'get_dte_summary': lambda self=None: {'display_name': f'{getattr(self, "current_dte", 0)}DTE' if self else '0DTE'},
                    'current_dte': 0,
                    'get_dte_display_name': lambda self, dte=0: f'{dte}DTE'
                })()
            from grok import GrokAnalyzer, get_comprehensive_market_data
        
        # Get request data
        data = request.get_json() or {}
        dte = data.get('dte', 0)
        ticker = data.get('ticker', 'SPY')
        include_sentiment = data.get('include_sentiment', True)  # Default to including sentiment
        
        print(f"🤖 Starting integrated Grok analysis for {ticker} {dte}DTE (sentiment: {include_sentiment})")
        
        # Create GrokAnalyzer
        analyzer = GrokAnalyzer()
        
        # Use the new integrated analysis method
        analysis_result = analyzer.send_analysis_request(ticker=ticker, dte=dte, include_sentiment=include_sentiment)
        
        if not analysis_result or not analysis_result['success']:
            return jsonify({'error': 'Failed to complete analysis'}), 500
        
        trading_analysis = analysis_result['trading_analysis']
        if trading_analysis:
            print(f"✅ Integrated Grok analysis completed")
            
            # Process and store the Grok response
            from trader_integration import process_grok_response
            user_session_id = session.get('session_id') or session.get('user_session_id')
            
            processing_result = process_grok_response(
                grok_response=trading_analysis,
                ticker=ticker,
                dte=dte,
                session_id=user_session_id
            )
            
            return jsonify({
                'success': True,
                'analysis': trading_analysis,
                'ticker': ticker,
                'dte': dte,
                'processing_result': processing_result,
                'trade_parsed': processing_result.get('success', False),
                'parsed_trade': processing_result.get('parsed_trade') if processing_result.get('success') else None,
                'includes_sentiment': analysis_result['includes_sentiment'],
                'prompt_length': analysis_result['prompt_length']
            })
        else:
            print(f"❌ Grok analysis failed")
            return jsonify({'error': 'Grok analysis failed'}), 500
            
    except Exception as e:
        print(f"💥 Exception in Grok analysis: {e}")
        return jsonify({'error': f'Exception: {str(e)}'}), 500

@app.route('/api/market-sentiment', methods=['POST'])
def market_sentiment():
    """API endpoint for market sentiment analysis"""
    try:
        token = session.get('access_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # Ensure tt.py has the token
        set_access_token(token)
        
        # Import grok functions
        try:
            from grok import run_market_sentiment_analysis
        except ImportError as e:
            return jsonify({'error': f'Import error: {str(e)}'}), 500
        
        # Get request data
        data = request.get_json() or {}
        dte = data.get('dte', 0)
        ticker = data.get('ticker', 'SPY')
        
        print(f"🌍 Starting market sentiment analysis for {ticker} {dte}DTE")
        
        # Run market sentiment analysis
        result = run_market_sentiment_analysis(dte=dte, ticker=ticker)
        
        if result['success']:
            print(f"✅ Market sentiment analysis completed")
            return jsonify({
                'success': True,
                'sentiment_data': result['sentiment_data'],
                'ticker': ticker,
                'dte': dte
            })
        else:
            print(f"❌ Market sentiment analysis failed: {result['error']}")
            return jsonify({'error': result['error']}), 500
            
    except Exception as e:
        print(f"💥 Exception in market sentiment analysis: {e}")
        return jsonify({'error': f'Exception: {str(e)}'}), 500

@app.route('/api/account-streaming', methods=['GET', 'POST'])
def account_streaming():
    """API endpoint for managing account streaming"""
    try:
        token = session.get('access_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        if request.method == 'GET':
            # Get streaming status
            from account_streamer import get_streamer_status
            status = get_streamer_status()
            return jsonify({
                'success': True,
                'status': status
            })
            
        elif request.method == 'POST':
            # Control streaming (start/stop)
            data = request.get_json() or {}
            action = data.get('action', 'status')  # 'start', 'stop', 'status'
            
            if action == 'start':
                from account_streamer import start_global_streamer
                from trader import get_current_account_number
                
                # Get account number for streaming
                account_number = get_current_account_number()
                account_numbers = [account_number] if account_number else None
                
                result = start_global_streamer(token, account_numbers)
                return jsonify({
                    'success': result['success'],
                    'message': result['message'],
                    'status': result.get('status', {})
                })
                
            elif action == 'stop':
                from account_streamer import stop_global_streamer
                result = stop_global_streamer()
                return jsonify({
                    'success': result['success'],
                    'message': result['message']
                })
                
            else:
                return jsonify({'error': 'Invalid action'}), 400
            
    except Exception as e:
        print(f"💥 Exception in account streaming: {e}")
        return jsonify({'error': f'Exception: {str(e)}'}), 500

@app.route('/api/test-order-message', methods=['POST'])
def test_order_message():
    """API endpoint to add test order message for UI testing"""
    try:
        if not session.get('access_token'):
            return jsonify({'error': 'Not authenticated'}), 401
            
        from account_streamer import add_test_order_message
        result = add_test_order_message()
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Exception in test order message: {e}")
        return jsonify({'error': f'Exception: {str(e)}'}), 500

@app.route('/api/test-fill-message', methods=['POST'])
def test_fill_message():
    """API endpoint to add test fill message for UI testing"""
    try:
        if not session.get('access_token'):
            return jsonify({'error': 'Not authenticated'}), 401
            
        from account_streamer import add_test_fill_message
        result = add_test_fill_message()
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Exception in test fill message: {e}")
        return jsonify({'error': f'Exception: {str(e)}'}), 500

@app.route('/api/latest-trade-recommendation')
def get_latest_trade_recommendation():
    """API endpoint to get the latest trade recommendation"""
    try:
        from trader_integration import get_latest_trade_recommendation
        user_session_id = session.get('session_id') or session.get('user_session_id')
        
        result = get_latest_trade_recommendation(session_id=user_session_id)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Exception getting latest trade recommendation: {e}")
        return jsonify({'error': f'Exception: {str(e)}'}), 500

@app.route('/api/cached-grok-response')
def get_cached_grok_response():
    """API endpoint to get the latest cached Grok response - prioritizes automation results"""
    try:
        # Get session ID
        session_id = get_user_session_id()
        
        # Get user ID from database based on session ID
        user_id = db_storage.get_or_create_user_id(session_id=session_id)
        
        print(f"🔍 Cached response debug: session_id={session_id}, user_id={user_id}")
        
        # First check for latest automation results (highest priority)
        raw_response = db_storage.get_latest_data('grok_response')  # Gets automation results first
        parsed_trade = db_storage.get_latest_data('parsed_trades')  # Gets automation results first
        
        # Legacy fallback for old data structure
        if not raw_response:
            raw_response = db_storage.get_latest_data('grok_raw_response', user_id=user_id)
        if not parsed_trade:
            parsed_trade = db_storage.get_latest_data('parsed_trade', user_id=user_id)
        
        print(f"🔍 Raw response found: {raw_response is not None}")
        print(f"🔍 Parsed trade found: {parsed_trade is not None}")
        
        # If no data found, get latest from any user (final fallback)
        if not raw_response or not parsed_trade:
            print("🔄 No recent data found, checking for latest from any user...")
            conn = db_storage.get_db_connection()
            cursor = conn.cursor()
            
            if not raw_response:
                # Check both new and old response types
                cursor.execute("SELECT data_json FROM trade_data WHERE data_type IN ('grok_response', 'grok_raw_response') ORDER BY updated_at DESC LIMIT 1")
                result = cursor.fetchone()
                if result:
                    import json
                    raw_response = json.loads(result['data_json'])
                    print("✅ Found latest raw response from database")
            
            if not parsed_trade:
                # Check both new and old trade types
                cursor.execute("SELECT data_json FROM trade_data WHERE data_type IN ('parsed_trades', 'parsed_trade') ORDER BY updated_at DESC LIMIT 1")
                result = cursor.fetchone()
                if result:
                    import json
                    parsed_trade = json.loads(result['data_json'])
                    print("✅ Found latest parsed trade from database")
            
            conn.close()
        
        if raw_response:
            # Extract response text from different data structures
            response_text = ''
            timestamp = ''
            
            if isinstance(raw_response, dict):
                response_text = raw_response.get('response', raw_response.get('data', ''))
                timestamp = raw_response.get('timestamp', raw_response.get('updated_at', ''))
            else:
                response_text = str(raw_response)
            
            response_data = {
                'success': True,
                'cached_response': response_text,
                'timestamp': timestamp,
                'parsed_trade': parsed_trade,
                'source': 'automation' if 'automation@' in str(raw_response) else 'user'
            }
        else:
            response_data = {
                'success': False,
                'message': 'No cached response available'
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"💥 Exception getting cached Grok response: {e}")
        return jsonify({'error': f'Exception: {str(e)}'}), 500

@app.route('/trade')
def trade_page():
    """Trade management page - displays latest trade recommendation"""
    try:
        # Check authentication first
        token = session.get('access_token')
        if not token:
            return redirect('/login')
        
        # Get session ID
        session_id = get_user_session_id()
        
        # Get user ID from database based on session ID  
        user_id = db_storage.get_or_create_user_id(session_id=session_id)
        
        # Get latest parsed trade recommendation
        parsed_trade_data = db_storage.get_latest_data('parsed_trade', user_id=user_id)
        
        # If no data found for current user, get latest from any user
        if not parsed_trade_data:
            print("🔄 No trade data for current user, checking for latest from any user...")
            conn = db_storage.get_db_connection()
            cursor = conn.cursor()
            
            # Get latest parsed trade from any user  
            cursor.execute("SELECT data_json FROM trade_data WHERE data_type = 'parsed_trade' ORDER BY updated_at DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                import json
                parsed_trade_data = json.loads(result['data_json'])
                print("✅ Found latest parsed trade from database")
            
            conn.close()
        
        # Convert dictionary to object-like structure for template compatibility
        parsed_trade = None
        if parsed_trade_data:
            # Create a simple namespace object that allows dot notation access
            class TradeData:
                def __init__(self, data_dict):
                    for key, value in data_dict.items():
                        setattr(self, key, value)
            
            parsed_trade = TradeData(parsed_trade_data)
            print(f"🎯 Trade page: parsed trade converted - strategy_type={getattr(parsed_trade, 'strategy_type', 'N/A')}")
            print(f"🎯 Trade page: available attributes={[attr for attr in dir(parsed_trade) if not attr.startswith('_')]}")
        else:
            print("❌ No parsed trade data found anywhere")
        
        # Determine environment and authentication status
        environment = config.ENVIRONMENT_NAME
        
        # Check authentication status for current environment
        authenticated = bool(session.get('access_token'))  # Unified token for current environment
        
        print(f"🎯 Trade page: environment={environment}, authenticated={authenticated}")
        print(f"🎯 Trade page: parsed_trade available={parsed_trade is not None}")
        
        return render_template(
            'trade.html',
            environment=environment,
            authenticated=authenticated,
            parsed_trade=parsed_trade
        )
        
    except Exception as e:
        print(f"💥 Exception in trade page: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

@app.route('/data-management')
def data_management():
    """Data management dashboard to view persistent storage"""
    try:
        # Check authentication first
        token = session.get('access_token')
        if not token:
            return redirect('/login')
        
        # Get session ID
        session_id = get_user_session_id()
        
        # Get user ID from database based on session ID
        user_id = db_storage.get_or_create_user_id(session_id=session_id)
        
        # Get all data for this user
        conn = db_storage.get_db_connection()
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_info = cursor.fetchone()
        
        # Get all data types for this user
        cursor.execute(
            "SELECT DISTINCT data_type FROM trade_data WHERE user_id = ? ORDER BY updated_at DESC", 
            (user_id,)
        )
        data_types = [row['data_type'] for row in cursor.fetchall()]
        
        # Get latest data for each type
        stored_data = {}
        for data_type in data_types:
            data = db_storage.get_latest_data(data_type, user_id=user_id)
            if data:
                stored_data[data_type] = data
        
        return render_template(
            'data_management.html',
            session_id=session_id,
            user_id=user_id,
            last_active=user_info['last_active'] if user_info else 'Unknown',
            stored_data=stored_data,
            environment=config.ENVIRONMENT_NAME,
            authenticated=True
        )
        
    except Exception as e:
        print(f"💥 Exception in data management: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/logout', methods=['POST'])
def logout():
    """Logout endpoint - clears session"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/auth-status')
def auth_status():
    """Check if user is authenticated for current environment"""
    token = session.get('access_token')
    is_authenticated = token is not None
    
    # Check token scopes if authenticated
    token_scopes = []
    has_trading_permissions = False
    
    if is_authenticated:
        try:
            from token_manager import verify_token_scopes
            has_required_scopes, scopes = verify_token_scopes(token)
            token_scopes = scopes or []
            has_trading_permissions = 'trade' in token_scopes
        except Exception as e:
            print(f"⚠️ Error checking token scopes: {e}")
    
    return jsonify({
        'authenticated': is_authenticated,
        'session_active': 'access_token' in session,
        'environment': config.ENVIRONMENT_NAME,
        'trading_permissions': has_trading_permissions,
        'scopes': token_scopes
    })

@app.route('/api/execute-trade', methods=['POST'])
def execute_trade():
    """Execute a trade (placeholder for now)"""
    try:
        # Check authentication for current environment
        access_token = session.get('access_token')
        if not access_token:
            return jsonify({
                'success': False,
                'error': f'{config.ENVIRONMENT_NAME} authentication required for trading'
            }), 401
        
        # Get the latest parsed trade
        session_id = get_user_session_id()
        user_id = db_storage.get_or_create_user_id(session_id=session_id)
        parsed_trade = db_storage.get_latest_data('parsed_trade', user_id=user_id)
        
        if not parsed_trade:
            return jsonify({
                'success': False,
                'error': 'No trade signal available'
            }), 400
        
        # Execute real trade through TastyTrade API
        from trader import TastyTradeAPI, GrokResponseParser
        
        try:
            # Initialize TastyTrade API
            api = TastyTradeAPI()
            
            # Parse the trade signal into a spread order
            parser = GrokResponseParser()
            spread_order = parser.build_spread_order_from_parsed_trade(parsed_trade)
            
            if not spread_order:
                return jsonify({
                    'success': False,
                    'error': 'Failed to build spread order from trade data'
                }), 400
            
            print(f"🚀 Executing real trade: {spread_order.legs[0].symbol} spread")
            
            # Get account number for streaming
            account_number = api.get_account_number()
            account_numbers = [account_number] if account_number else None
            print(f"📊 Account for streaming: {account_numbers}")
            
            # Start account streaming before submitting order
            from account_streamer import start_global_streamer
            streaming_result = start_global_streamer(access_token, account_numbers)
            
            if not streaming_result.get('success'):
                print(f"⚠️ Warning: Failed to start account streaming: {streaming_result.get('message')}")
            else:
                print("📡 Account streaming started for trade monitoring")
            
            # Submit the order to TastyTrade
            order_result = api.submit_spread_order(spread_order)
            
            if order_result:
                # Extract order details from TastyTrade response
                order_data = order_result.get('data', {}).get('order', {})
                order_id = order_data.get('id')
                status = order_data.get('status', 'Submitted')
                
                print(f"✅ Trade executed successfully - Order ID: {order_id}, Status: {status}")
                
                # Add manual order notification since websocket auth is failing
                try:
                    from account_streamer import add_manual_order_message
                    order_message = {
                        'id': order_id,
                        'status': status,
                        'account-number': account_number,
                        'underlying-symbol': parsed_trade.get('underlying_symbol', 'SPY'),
                        'strategy_type': parsed_trade.get('strategy_type', 'Unknown'),
                        'price': parsed_trade.get('credit_received', 0.0)
                    }
                    add_manual_order_message(order_message)
                    print(f"📝 Added manual order message for UI display")
                except Exception as msg_error:
                    print(f"⚠️ Failed to add manual order message: {msg_error}")
                
                # TODO: Fix websocket "Unknown domain" error - investigate token/auth issue
                
                # TODO: Implement order status polling for real-time updates
                # Since websocket auth is failing with "Unknown domain", we need polling fallback
                
                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'result': {
                        'status': status,
                        'strategy': parsed_trade.get('strategy_type', 'Unknown'),
                        'message': f'Real trade submitted to {config.ENVIRONMENT_NAME} - monitoring active'
                    },
                    'streaming_started': streaming_result.get('success', False)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to submit order to TastyTrade API'
                }), 500
                
        except Exception as trade_error:
            print(f"💥 Trade execution error: {trade_error}")
            return jsonify({
                'success': False,
                'error': f'Trade execution failed: {str(trade_error)}'
            }), 500
        
    except Exception as e:
        print(f"💥 Exception in execute trade: {e}")
        return jsonify({
            'success': False,
            'error': f'Exception: {str(e)}'
        }), 500

@app.route('/api/streaming/status')
def streaming_status():
    """Get streaming status (placeholder)"""
    return jsonify({
        'active': False,
        'connected': False,
        'message': 'Streaming not yet implemented'
    })

@app.route('/api/streaming/start', methods=['POST'])
def start_streaming():
    """Start order streaming (placeholder)"""
    return jsonify({
        'success': True,
        'message': 'Streaming started (placeholder)'
    })

@app.route('/api/streaming/stop', methods=['POST'])
def stop_streaming():
    """Stop order streaming (placeholder)"""
    return jsonify({
        'success': True,
        'message': 'Streaming stopped (placeholder)'
    })

@app.route('/api/streaming/updates')
def streaming_updates():
    """Get streaming updates (placeholder)"""
    return jsonify({
        'updates': [],
        'last_update': datetime.now().isoformat()
    })

# =============================================================================
# AUTOMATED TRADING API ENDPOINTS
# =============================================================================

@app.route('/api/automation/status')
def automation_status():
    """Get automation system status"""
    try:
        from auto_trade_scheduler import get_auto_trader_status, get_latest_automated_trade
        
        # Get basic status
        status = get_auto_trader_status()
        
        # Check if tokens are available for automation (database storage)
        try:
            from db_storage import get_stored_tokens
            access_token, refresh_token = get_stored_tokens(config.ENVIRONMENT_NAME)
            tokens_available = bool(access_token)
        except Exception:
            tokens_available = False
        
        # Try to get latest trade recommendation
        try:
            latest_trade = get_latest_automated_trade()
            if latest_trade and latest_trade.get('success'):
                status['latest_trade'] = {
                    'strategy': latest_trade.get('trade_data', {}).get('strategy_type', 'Unknown'),
                    'status': 'Ready for execution',
                    'ready_for_execution': True,
                    'timestamp': latest_trade.get('timestamp')
                }
            else:
                status['latest_trade'] = None
        except Exception as e:
            logger.warning(f"Could not fetch latest trade: {e}")
            status['latest_trade'] = None
        
        return jsonify({
            'success': True,
            'status': status['status'],
            'last_trade_date': status.get('last_trade_date'),
            'paper_trading': status.get('paper_trading', True),
            'detailed_status': status.get('detailed_status', {}),
            'next_scheduled_run': status.get('detailed_status', {}).get('next_scheduled_run'),
            'latest_trade': status.get('latest_trade'),
            'tokens_available': tokens_available,
            'auth_warning': 'No tokens stored for automation - re-authenticate to enable' if not tokens_available else None
        })
        
    except Exception as e:
        print(f"💥 Exception getting automation status: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to get automation status: {e}',
            'status': 'error'
        })

@app.route('/api/automation/sync-tokens', methods=['POST'])
def sync_automation_tokens():
    """Sync current session tokens to database for automation access"""
    try:
        if 'access_token' not in session:
            return jsonify({'success': False, 'message': 'No session tokens to sync'})
        
        # Get tokens from session
        access_token = session.get('access_token')
        refresh_token = session.get('refresh_token')
        token_scopes = session.get('token_scopes', '')
        
        if not access_token:
            return jsonify({'success': False, 'message': 'No access token in session'})
        
        # Store in database for automation access
        from db_storage import store_tokens
        success = store_tokens(
            environment=config.ENVIRONMENT_NAME,
            access_token=access_token,
            refresh_token=refresh_token,
            token_scopes=token_scopes
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Tokens synced to database - automation can now access them'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to store tokens in database'
            })
            
    except Exception as e:
        print(f"💥 Exception syncing tokens: {e}")
        return jsonify({
            'success': False,
            'message': f'Error syncing tokens: {e}'
        })

@app.route('/api/automation/start', methods=['POST'])
def start_automation():
    """Start the automated trading system"""
    try:
        # Check authentication
        if 'access_token' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'})
        
        from auto_trade_scheduler import start_automated_trading
        
        # Start automation (use simple Grok for testing if in development)
        use_simple_grok = not config.IS_PRODUCTION
        success = start_automated_trading(use_simple_grok=use_simple_grok)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Automated trading system started successfully',
                'mode': 'production' if config.IS_PRODUCTION else 'development'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to start automated trading system'
            })
            
    except Exception as e:
        print(f"💥 Exception starting automation: {e}")
        return jsonify({
            'success': False,
            'message': f'Error starting automation: {e}'
        })

@app.route('/api/automation/stop', methods=['POST'])
def stop_automation():
    """Stop the automated trading system"""
    try:
        from auto_trade_scheduler import stop_automated_trading
        
        success = stop_automated_trading()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Automated trading system stopped successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to stop automated trading system'
            })
            
    except Exception as e:
        print(f"💥 Exception stopping automation: {e}")
        return jsonify({
            'success': False,
            'message': f'Error stopping automation: {e}'
        })

@app.route('/api/automation/force-execute', methods=['POST'])
def force_execute_automation():
    """Force execute a trade analysis (for testing)"""
    try:
        # Check authentication
        if 'access_token' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'})
        
        from auto_trade_scheduler import force_execute_trade
        
        result = force_execute_trade()
        
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Exception in force execute: {e}")
        return jsonify({
            'success': False,
            'message': f'Error in force execution: {e}'
        })

@app.route('/api/automation/execute-trade', methods=['POST'])
def execute_automated_trade():
    """Execute the latest automated trade recommendation"""
    try:
        # Check authentication
        if 'access_token' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'})
        
        from auto_trade_scheduler import get_latest_automated_trade
        
        # Get the latest trade recommendation
        trade_data = get_latest_automated_trade()
        
        if not trade_data or not trade_data.get('success'):
            return jsonify({
                'success': False,
                'message': 'No automated trade recommendations available'
            })
        
        # Here you would integrate with the actual trade execution system
        # For now, we'll return a simulated success response
        return jsonify({
            'success': True,
            'message': 'Trade execution initiated (simulated)',
            'trade_details': trade_data.get('trade_data', {}),
            'note': 'This is currently a simulation. Integrate with actual trading system.'
        })
        
    except Exception as e:
        print(f"💥 Exception executing automated trade: {e}")
        return jsonify({
            'success': False,
            'message': f'Error executing trade: {e}'
        })

@app.route('/api/automation/dte-discovery')
def dte_discovery():
    """Get information about optimal DTE discovery for SPY"""
    try:
        # Check authentication
        if 'access_token' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'})
        
        from trading_scheduler import get_scheduler_instance
        
        scheduler = get_scheduler_instance()
        
        # Get current optimal DTE
        optimal_dte = scheduler.find_optimal_dte(ticker="SPY", target_dte=32, tolerance=5)
        
        # Also get all available DTEs for context
        from market_data import get_available_dtes
        available_dtes = get_available_dtes("SPY")
        
        # Filter to show relevant range
        relevant_dtes = [d for d in available_dtes if 20 <= d['dte'] <= 45]
        
        return jsonify({
            'success': True,
            'optimal_dte': optimal_dte,
            'target_range': '28-33 days',
            'available_dtes_in_range': relevant_dtes,
            'discovery_info': {
                'target': 32,
                'tolerance': 5,
                'min_acceptable': 27,
                'max_acceptable': 37
            }
        })
        
    except Exception as e:
        print(f"💥 Exception in DTE discovery: {e}")
        return jsonify({
            'success': False,
            'message': f'Error in DTE discovery: {e}'
        })

if __name__ == '__main__':
    # Initialize automated trading system (optional)
    try:
        print("🤖 Checking automated trading system initialization...")
        
        # Auto-start conditions:
        # 1. Production mode (Railway deployment)
        # 2. ENABLE_AUTOMATION environment variable set to 'true'
        should_auto_start = (
            config.IS_PRODUCTION or 
            os.getenv('ENABLE_AUTOMATION', 'false').lower() == 'true'
        )
        
        if should_auto_start:
            print("🚀 Auto-starting automated trading system...")
            from auto_trade_scheduler import start_automated_trading
            
            # Use simple Grok for development, comprehensive for production
            use_simple_grok = not config.IS_PRODUCTION
            automation_started = start_automated_trading(use_simple_grok=use_simple_grok)
            
            if automation_started:
                grok_mode = "comprehensive" if config.IS_PRODUCTION else "simple"
                print(f"✅ Automated trading system started successfully ({grok_mode} mode)")
                print("📅 32DTE analysis scheduled for Mondays at 10:00 AM ET")
            else:
                print("⚠️ Failed to start automated trading system")
        else:
            print("🔧 Automated trading disabled - start manually via UI")
            print("💡 To enable: set ENABLE_AUTOMATION=true environment variable")
            
    except ImportError as e:
        print(f"📦 Automated trading dependencies not available: {e}")
        print("💡 Install missing packages: pip install schedule")
    except Exception as e:
        print(f"⚠️ Could not initialize automated trading: {e}")
    
    # Start Flask application
    if config.IS_PRODUCTION:
        # Production settings for Railway
        print("🌍 Starting in PRODUCTION mode...")
        app.run(
            debug=config.DEBUG,
            host='0.0.0.0',
            port=config.PORT,
            threaded=True
            # No SSL in production - Railway handles TLS termination
        )
    else:
        # Development settings with SSL
        print("🌍 Starting in DEVELOPMENT mode...")
        app.run(
            debug=config.DEBUG,
            host='0.0.0.0',
            port=config.PORT,
            threaded=True,
            ssl_context=('certs/cert.pem', 'certs/key.pem')
        )