# Simple Flask app with SSL and TastyTrade OAuth2
from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime
from tt import get_oauth_authorization_url, exchange_code_for_token, set_access_token, set_refresh_token, get_oauth_token, get_options_chain, get_trading_range, get_options_chain_by_date, get_options_chain_data
from tt_data import TastyTradeMarketData
import config
import requests
import uuid
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_in_production'

# In-memory store for trade data to avoid session cookie bloat
# This could be replaced with Redis or a database for production scaling
trade_store = defaultdict(dict)

def get_user_session_id():
    """Get or create a unique session ID for the user"""
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid.uuid4())
    return session['user_session_id']

def store_trade_data(trade_type, data):
    """Store trade data in memory store"""
    session_id = get_user_session_id()
    trade_store[session_id][trade_type] = data
    print(f"🗄️ Stored {trade_type} for session {session_id[:8]}...")

def get_trade_data(trade_type):
    """Retrieve trade data from memory store"""
    session_id = get_user_session_id()
    return trade_store[session_id].get(trade_type)

# Set Flask configuration based on environment
app.config['DEBUG'] = config.DEBUG
app.config['ENV'] = config.FLASK_ENV

print(f"🚀 Flask App - Environment: {'PRODUCTION' if config.IS_PRODUCTION else 'DEVELOPMENT'}")
print(f"🚀 Flask App - Debug Mode: {config.DEBUG}")
print(f"🚀 Flask App - Port: {config.PORT}")

# Helper function for market data using clean architecture
def get_market_data_clean(ticker='SPY'):
    """Get market data using the clean tt_data.py implementation"""
    try:
        client = TastyTradeMarketData()
        market_data = client.get_market_data_clean(ticker)
        
        if market_data:
            return {
                'symbol': market_data['symbol'],
                'current_price': market_data['current_price'],
                'bid': market_data['bid'],
                'ask': market_data['ask'],
                'volume': market_data['volume'],
                'price_change': market_data['price_change'],
                'percent_change': market_data['percent_change'],
                'status': 'success'
            }
        else:
            return {
                'symbol': ticker,
                'current_price': 0.0,
                'bid': 0.0,
                'ask': 0.0,
                'volume': 0,
                'price_change': 0.0,
                'percent_change': 0.0,
                'status': 'error',
                'error': 'No market data available'
            }
    except Exception as e:
        return {
            'symbol': ticker,
            'current_price': 0.0,
            'bid': 0.0,
            'ask': 0.0,
            'volume': 0,
            'price_change': 0.0,
            'percent_change': 0.0,
            'status': 'error',
            'error': str(e)
        }

@app.route('/')
def home():
    """Home page - redirect to login if not authenticated, dashboard if authenticated"""
    token = session.get('prod_access_token') or session.get('access_token')
    if token:
        print(f"✅ User authenticated, redirecting to dashboard")
        return redirect('/dashboard')
    else:
        print("❌ No authentication, showing login page")
        return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard page - requires authentication"""
    # Check for production token (new naming or legacy)
    token = session.get('prod_access_token') or session.get('access_token')
    if not token:
        print("❌ No authentication token found, redirecting to login")
        return redirect('/')
    
    print(f"✅ Dashboard access granted with token: {token[:20]}...")
    
    # Ensure tt.py has the token
    set_access_token(token)
    return render_template('dashboard.html')

@app.route('/login')
def login():
    """Redirect to TastyTrade OAuth2 authorization"""
    auth_url = get_oauth_authorization_url()
    print(f"🔗 Redirecting to: {auth_url}")
    return redirect(auth_url)

@app.route('/zscialespersonal')  # Legacy dev callback - keep for backward compatibility
@app.route('/tt')  # Legacy production callback - keep for backward compatibility
@app.route('/zscialesProd')  # New dev callback for TastyTrade Prod integration
@app.route('/ttProd')  # New production callback for TastyTrade Prod integration
def oauth_callback():
    """Handle OAuth2 callback from TastyTrade (supports multiple endpoints)"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    # Determine which callback URI was used
    callback_uri = request.path
    environment_info = ""
    if callback_uri == "/zscialesProd":
        environment_info = " (Development → TastyTrade Prod)"
    elif callback_uri == "/ttProd":
        environment_info = " (Production → TastyTrade Prod)"
    elif callback_uri == "/zscialespersonal":
        environment_info = " (Legacy Dev Callback)"
    elif callback_uri == "/tt":
        environment_info = " (Legacy Prod Callback)"
    
    print(f"🔐 OAuth callback received on {callback_uri}{environment_info}")
    print(f"🔐 Code: {code[:20]}..." if code else "No code")
    print(f"🔐 State: {state}")
    print(f"🔐 Error: {error}" if error else "No error")
    
    if error:
        return f"OAuth Error: {error}", 400
    
    if not code:
        return "No authorization code received", 400
    
    # Exchange code for token
    print("🔐 Exchanging code for token...")
    token_data = exchange_code_for_token(code)
    
    if token_data and token_data.get('access_token'):
        print("🔐 Successfully received tokens!")
        # Store PRODUCTION tokens in session with proper naming
        session['prod_access_token'] = token_data['access_token']
        if token_data.get('refresh_token'):
            session['prod_refresh_token'] = token_data['refresh_token']
        
        # Also set the tokens in tt.py module (for backward compatibility)
        set_access_token(token_data['access_token'])
        if token_data.get('refresh_token'):
            set_refresh_token(token_data['refresh_token'])
            
        print("🏭 Production tokens stored successfully")
            
        print("🔐 Redirecting to dashboard...")
        return redirect('/dashboard')
    else:
        print("🔐 Failed to exchange code for token")
        return "Failed to exchange code for token", 500

@app.route('/oauth/sandbox/callback')
def new_sandbox_oauth_callback():
    """Handle OAuth2 callback from TastyTrade Sandbox"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    print(f"🧪 Sandbox OAuth callback received")
    print(f"🔐 Code: {code[:20]}..." if code else "No code")
    print(f"🔐 State: {state}")
    print(f"🔐 Error: {error}" if error else "No error")
    
    if error:
        return f"OAuth Error: {error}", 400
    
    if not code:
        return "No authorization code received", 400
    
    # Exchange code for SANDBOX token
    print("🧪 Exchanging code for sandbox token...")
    token_data = exchange_sandbox_code_for_token(code)
    
    if token_data and token_data.get('access_token'):
        print("🧪 Successfully received sandbox tokens!")
        # Store SANDBOX tokens in session
        session['sandbox_access_token'] = token_data['access_token']
        if token_data.get('refresh_token'):
            session['sandbox_refresh_token'] = token_data['refresh_token']
            
        print("🧪 Sandbox tokens stored successfully")
        print("🔐 Redirecting to dashboard...")
        return redirect('/dashboard')
    else:
        print("🧪 Failed to exchange code for sandbox token")
        return "Failed to exchange code for sandbox token", 500

@app.route('/status')
def status():
    """Check authentication status"""
    token = session.get('prod_access_token') or session.get('access_token') or get_oauth_token()
    
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
    # Check for production tokens (new naming scheme with backward compatibility)
    token = session.get('prod_access_token') or session.get('access_token')
    
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
        market_info = get_market_data_clean()
        
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
    # Check for production tokens (new naming scheme with backward compatibility)
    token = session.get('prod_access_token') or session.get('access_token')
    refresh_token = session.get('prod_refresh_token') or session.get('refresh_token')
    
    print(f"🔍 Flask session check:")
    print(f"  - Has prod_access_token: {bool(token)}")
    print(f"  - Has refresh_token: {bool(refresh_token)}")
    if token:
        print(f"  - Token preview: {token[:20]}...")
    print(f"  - Session keys: {list(session.keys())}")
    
    if not token:
        print("❌ No production access token in session")
        return jsonify({'error': 'Production authentication required'}), 401
    
    # Ensure tt.py has both tokens
    print("🔄 Setting production tokens in tt.py module")
    set_access_token(token)
    if refresh_token:
        set_refresh_token(refresh_token)
    
    # Try to get market data
    try:
        print("📞 Calling get_market_data_clean() function")
        market_info = get_market_data_clean()
        
        if market_info and market_info.get('status') == 'success':
            print("✅ Market data retrieved successfully")
            return jsonify(market_info)
        else:
            error_msg = market_info.get('error', 'Market data unavailable') if market_info else 'Market data function returned None'
            print(f"❌ Market data error: {error_msg}")
            return jsonify({'error': error_msg}), 503
    except Exception as e:
        print(f"💥 Exception in market data retrieval: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options-chain')
def api_options_chain():
    """API endpoint for options chain data"""
    try:
        print("🔍 Flask session check:")
        prod_token = session.get('prod_access_token') or session.get('access_token')
        print(f"  - Has prod_access_token: {bool(prod_token)}")
        print(f"  - Has refresh_token: {'refresh_token' in session}")
        
        if prod_token:
            token_preview = prod_token[:20] + '...' if len(prod_token) > 20 else prod_token
            print(f"  - Token preview: {token_preview}")
        
        print(f"  - Session keys: {list(session.keys())}")
        
        # Set tokens in tt.py module
        print("🔄 Setting tokens in tt.py module")
        if prod_token:
            set_access_token(prod_token)
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
        
        print(f"📞 Calling get_options_chain_data() function with bulk API")
        print(f"📋 Parameters: ticker={ticker}, dte={dte}")
        
        # Call the new bulk options chain function
        options_info = get_options_chain_data(
            ticker=ticker,
            dte=dte if dte is not None else 0,  # Default to 0DTE if not specified
            current_price=None  # Let it fetch the current price
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
        
        # Check authentication (new naming scheme with backward compatibility)
        prod_token = session.get('prod_access_token') or session.get('access_token')
        if not prod_token:
            print("❌ No production access token in session")
            return jsonify({'error': 'Production authentication required'}), 401
            
        # Set token in tt.py module for the market_data function
        set_access_token(prod_token)
        
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
        prod_token = session.get('prod_access_token') or session.get('access_token')
        print(f"  - Has prod_access_token: {bool(prod_token)}")
        print(f"  - Has refresh_token: {'refresh_token' in session}")
        
        # Set tokens in tt.py module
        print("🔄 Setting tokens in tt.py module")
        if prod_token:
            set_access_token(prod_token)
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
        prod_token = session.get('prod_access_token') or session.get('access_token')
        print(f"  - Has prod_access_token: {bool(prod_token)}")
        print(f"  - Has refresh_token: {'refresh_token' in session}")
        
        # Set tokens in tt.py module
        print("🔄 Setting tokens in tt.py module")
        if prod_token:
            set_access_token(prod_token)
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
        token = session.get('prod_access_token') or session.get('access_token')
        if not token:
            return jsonify({'error': 'Production authentication required'}), 401
        
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
        token = session.get('prod_access_token') or session.get('access_token')
        if not token:
            return jsonify({'error': 'Production authentication required'}), 401
        
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
        
        print(f"🤖 Starting Grok analysis for {ticker} {dte}DTE")
        
        # Create GrokAnalyzer
        analyzer = GrokAnalyzer()
        
        print(f"� Starting comprehensive Grok analysis for {ticker} {dte}DTE...")
        
        # Use the comprehensive analysis method
        grok_response = analyzer.send_analysis_request(ticker, dte)
        
        if grok_response:
            print(f"✅ Grok analysis completed - Response length: {len(grok_response)} characters")
            
            # Cache the Grok response
            session['cached_grok_response'] = {
                'analysis': grok_response,
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'ticker': ticker,
                'dte': dte
            }
            
            # Parse the trade from Grok response
            parsed_trade = None
            try:
                from trader import GrokResponseParser
                parser = GrokResponseParser()
                trade_signal = parser.parse_grok_response(grok_response)
                
                if trade_signal:
                    # Store parsed trade in memory store (not session to avoid cookie bloat)
                    parsed_trade = {
                        'strategy': trade_signal.strategy_type.value,
                        'underlying': trade_signal.underlying_symbol,
                        'confidence': trade_signal.confidence,  # Fixed: confidence not confidence_score
                        'market_bias': trade_signal.market_bias,
                        'short_strike': trade_signal.short_strike,
                        'long_strike': trade_signal.long_strike,
                        'expiration_date': trade_signal.expiration,  # Fixed: expiration not expiration_date
                        'credit': trade_signal.credit_received,
                        'quantity': 1,  # Default quantity
                        'timestamp': datetime.utcnow().isoformat(),
                        'raw_analysis': grok_response
                    }
                    
                    # Store in memory store instead of session
                    store_trade_data('parsed_trade', parsed_trade)
                    store_trade_data('cached_grok_response', {
                        'analysis': grok_response,
                        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                        'ticker': ticker,
                        'dte': dte
                    })
                    
                    print(f"🎯 Trade parsed and stored: {trade_signal.strategy_type.value} on {ticker}")
                    
            except Exception as parse_error:
                print(f"⚠️ Trade parsing failed: {parse_error}")
                # Continue without parsed trade
            
            return jsonify({
                'success': True,
                'analysis': grok_response,
                'ticker': ticker,
                'dte': dte,
                'parsed_trade': parsed_trade
            })
        else:
            print(f"❌ Grok analysis failed")
            return jsonify({'error': 'Grok analysis failed'}), 500
            
    except Exception as e:
        print(f"💥 Exception in Grok analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/cached-grok-response')
def cached_grok_response():
    """API endpoint to get cached Grok response"""
    try:
        # Check if there's a cached response in memory store
        cached_response = get_trade_data('cached_grok_response')
        parsed_trade = get_trade_data('parsed_trade')
        
        if cached_response:
            return jsonify({
                'success': True,
                'cached_response': cached_response['analysis'],
                'timestamp': cached_response.get('timestamp', 'Unknown'),
                'ticker': cached_response.get('ticker', 'SPY'),
                'dte': cached_response.get('dte', 0),
                'parsed_trade': parsed_trade
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No cached response available'
            })
            
    except Exception as e:
        print(f"💥 Exception getting cached response: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/logout', methods=['POST'])
def logout():
    """Logout endpoint - clears session"""
    session.clear()
    return jsonify({'success': True})

# =========================================================================
# TRADE MANAGEMENT SYSTEM
# =========================================================================

@app.route('/trade')
def trade_page():
    """Trade management page with sandbox authentication and parsed trades"""
    try:
        # Check for parsed trade in memory store (not session)
        parsed_trade = get_trade_data('parsed_trade')
        
        # Check sandbox authentication status
        sandbox_authenticated = bool(session.get('sandbox_access_token'))
        
        # Get production authentication status for comparison
        prod_authenticated = bool(session.get('prod_access_token'))
        
        print(f"📊 Trade page loaded - Parsed trade available: {parsed_trade is not None}")
        if parsed_trade:
            print(f"📊 Trade details: {parsed_trade.get('strategy')} on {parsed_trade.get('underlying')}")
        
        return render_template('trade.html',
            parsed_trade=parsed_trade,
            sandbox_authenticated=sandbox_authenticated,
            prod_authenticated=prod_authenticated,
            environment=config.TRADING_MODE
        )
    except Exception as e:
        print(f"❌ Error in trade page: {e}")
        return render_template('trade.html', 
            error=str(e),
            sandbox_authenticated=False,
            prod_authenticated=False
        )

@app.route('/sandbox-auth')
def sandbox_auth():
    """Initiate TastyTrade sandbox OAuth authentication"""
    try:
        # Generate sandbox OAuth URL
        sandbox_auth_url = get_sandbox_oauth_authorization_url()
        if sandbox_auth_url:
            print(f"🔗 Redirecting to sandbox OAuth: {sandbox_auth_url}")
            return redirect(sandbox_auth_url)
        else:
            print("❌ Failed to generate sandbox OAuth URL")
            return redirect('/trade?error=sandbox_auth_failed')
    except Exception as e:
        print(f"❌ Error initiating sandbox auth: {e}")
        return redirect('/trade?error=sandbox_auth_failed')

def get_sandbox_oauth_authorization_url():
    """Generate OAuth2 authorization URL for TastyTrade Sandbox"""
    try:
        print("🧪 TastyTrade Sandbox uses session-based authentication, not OAuth")
        print("� Will authenticate directly with username/password when needed")
        
        sandbox_client_id = config.TT_TRADING_API_KEY   # Sandbox API key
        
        # Use the sandbox-specific redirect URI from config
        sandbox_redirect_uri = config.TT_SANDBOX_REDIRECT_URI
        
        # TastyTrade Sandbox OAuth - use the correct sandbox-specific endpoint
        # Based on working implementation from main branch
        auth_url = "https://cert-my.staging-tasty.works/auth.html"
        
        params = {
            'client_id': sandbox_client_id,
            'redirect_uri': sandbox_redirect_uri,
            'response_type': 'code',
            'scope': 'read trade openid',
            'state': 'sandbox_oauth_state'  # State parameter for sandbox flow
        }
        
        print(f"🔗 Using sandbox OAuth endpoint: {auth_url}")
        print(f"🔑 Client ID: {sandbox_client_id}")
        print(f"🔄 Redirect URI: {sandbox_redirect_uri}")
        
        # Convert to query string
        import urllib.parse
        query_string = urllib.parse.urlencode(params)
        full_auth_url = f"{auth_url}?{query_string}"
        
        print(f"🔗 Generated sandbox OAuth URL: {full_auth_url}")
        return full_auth_url
        
    except Exception as e:
        print(f"❌ Error in sandbox auth setup: {e}")
        return None



@app.route('/zscialespersonal')
def sandbox_oauth_callback_personal():
    """Handle OAuth2 callback from TastyTrade Sandbox - correct redirect URI"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    print(f"🔐 Sandbox OAuth callback received at /zscialespersonal")
    print(f"🔐 Code: {code[:20]}..." if code else "No code")
    print(f"🔐 State: {state}")
    print(f"🔐 Error: {error}" if error else "No error")
    
    if error:
        print(f"❌ Sandbox OAuth error: {error}")
        return redirect('/trade?error=sandbox_auth_failed')
    
    if not code:
        print("❌ No sandbox authorization code received")
        return redirect('/trade?error=no_sandbox_code')
    
    # Exchange code for sandbox token
    print("🔐 Exchanging sandbox code for token...")
    sandbox_token_data = exchange_sandbox_code_for_token(code)
    
    if sandbox_token_data and sandbox_token_data.get('access_token'):
        print("🔐 Successfully received sandbox tokens!")
        
        # Store SANDBOX tokens in session with proper naming
        session['sandbox_access_token'] = sandbox_token_data['access_token']
        if sandbox_token_data.get('refresh_token'):
            session['sandbox_refresh_token'] = sandbox_token_data['refresh_token']
            
        session['sandbox_authenticated_at'] = datetime.utcnow().isoformat()
        print("🧪 Sandbox tokens stored successfully")
            
        print("🔐 Redirecting to trade page...")
        return redirect('/trade')
    else:
        print("🔐 Failed to exchange sandbox code for token")
        return redirect('/trade?error=sandbox_token_failed')

def exchange_sandbox_code_for_token(code):
    """Exchange authorization code for sandbox access token"""
    try:
        sandbox_base_url = config.TT_TRADING_BASE_URL
        sandbox_client_id = config.TT_TRADING_API_KEY
        sandbox_client_secret = config.TT_TRADING_API_SECRET
        sandbox_redirect_uri = config.TT_SANDBOX_REDIRECT_URI
        
        token_url = f"{sandbox_base_url}/oauth/token"
        
        print(f"🔗 Exchanging sandbox code for token: {token_url}")
        print(f"🔑 Sandbox Client ID: {sandbox_client_id[:10]}..." if sandbox_client_id else "❌ No Client ID")
        print(f"🔑 Sandbox Client Secret: {sandbox_client_secret[:10]}..." if sandbox_client_secret else "❌ No Client Secret")
        print(f"🔄 Redirect URI: {sandbox_redirect_uri}")
        
        # Use the same headers format as tt.py
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Prepare token exchange data - same format as tt.py exchange_code_for_token
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': sandbox_redirect_uri,
            'client_id': sandbox_client_id,
            'client_secret': sandbox_client_secret
        }
        
        print(f"📋 Payload: {payload}")
        
        # Make the token exchange request with proper headers
        response = requests.post(token_url, data=payload, headers=headers)
        
        print(f"📡 Sandbox token response status: {response.status_code}")
        
        if response.status_code == 200:
            token_response = response.json()
            print("✅ Sandbox token exchange successful")
            
            # Log token details (safely)
            if 'access_token' in token_response:
                print(f"📋 Token type: {token_response.get('token_type', 'Unknown')}")
                print(f"⏰ Expires in: {token_response.get('expires_in', 'Unknown')} seconds")
                print(f"🔄 Refresh token received: {'refresh_token' in token_response}")
            
            return token_response
        else:
            print(f"❌ Sandbox token exchange failed: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 Exception during sandbox token exchange: {e}")
        return None

@app.route('/api/execute-trade', methods=['POST'])
def execute_trade():
    """Execute the parsed trade in sandbox environment"""
    try:
        # Check sandbox authentication
        if not session.get('sandbox_access_token'):
            return jsonify({'error': 'Sandbox authentication required'}), 401
            
        # Get the parsed trade from memory store
        parsed_trade = get_trade_data('parsed_trade')
        if not parsed_trade:
            return jsonify({'error': 'No trade available for execution'}), 400
            
        # Import trading components
        from trader import TastyTradeAPI, SpreadTradeBuilder
        
        # Create API instance and authenticate
        api = TastyTradeAPI()
        api.trading_token = session.get('sandbox_access_token')
        
        # Build the order from parsed trade
        builder = SpreadTradeBuilder()
        
        if parsed_trade['strategy'] == 'BULL_PUT_SPREAD':
            order = builder.create_bull_put_spread(
                underlying=parsed_trade['underlying'],
                short_strike=parsed_trade['short_strike'],
                long_strike=parsed_trade['long_strike'],
                expiration_date=parsed_trade['expiration_date'],
                quantity=parsed_trade.get('quantity', 1),
                price=parsed_trade.get('credit', 0.0)
            )
        elif parsed_trade['strategy'] == 'BEAR_CALL_SPREAD':
            order = builder.create_bear_call_spread(
                underlying=parsed_trade['underlying'],
                short_strike=parsed_trade['short_strike'],
                long_strike=parsed_trade['long_strike'],
                expiration_date=parsed_trade['expiration_date'],
                quantity=parsed_trade.get('quantity', 1),
                price=parsed_trade.get('credit', 0.0)
            )
        else:
            return jsonify({'error': f'Unsupported strategy: {parsed_trade["strategy"]}'}), 400
            
        # Submit the order
        result = api.submit_spread_order(order)
        
        if result and result.get('success'):
            # Store execution result
            session['last_execution'] = {
                'timestamp': datetime.utcnow().isoformat(),
                'trade': parsed_trade,
                'result': result,
                'order_id': result.get('order_id')
            }
            
            return jsonify({
                'success': True,
                'message': 'Trade executed successfully',
                'order_id': result.get('order_id'),
                'result': result
            })
        else:
            return jsonify({
                'error': 'Trade execution failed',
                'details': result
            }), 500
            
    except Exception as e:
        print(f"❌ Error executing trade: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth-status')
def auth_status():
    """Check if user is authenticated with TastyTrade API"""
    try:
        # Check Flask session for production tokens
        prod_token = session.get('prod_access_token') or session.get('access_token')  # backward compatibility
        sandbox_token = session.get('sandbox_access_token')
        
        has_prod_session = prod_token is not None
        has_sandbox_session = sandbox_token is not None
        
        # Check actual TastyTrade API connection
        from tt_data import TastyTradeMarketData
        client = TastyTradeMarketData()
        api_authenticated = client.authenticate()
        
        # Test actual API call if authenticated
        api_working = False
        if api_authenticated:
            try:
                # Try a simple API call to verify connection
                test_data = client.get_market_data_clean('SPY')
                api_working = test_data is not None
            except Exception as e:
                print(f"🔍 API test call failed: {e}")
                api_working = False
        
        return jsonify({
            'authenticated': api_authenticated and api_working,
            'prod_session_active': has_prod_session,
            'sandbox_session_active': has_sandbox_session,
            'api_authenticated': api_authenticated,
            'api_working': api_working,
            'details': {
                'prod_session': has_prod_session,
                'sandbox_session': has_sandbox_session,
                'tt_headers': api_authenticated,
                'api_test': api_working
            }
        })
    except Exception as e:
        print(f"❌ Error checking auth status: {e}")
        return jsonify({
            'authenticated': False,
            'prod_session_active': False,
            'sandbox_session_active': False,
            'api_authenticated': False,
            'api_working': False,
            'error': str(e)
        })

# =============================================================================
# ACCOUNT STREAMING ENDPOINTS
# =============================================================================

# Global streamers store to manage multiple user sessions
active_streamers = {}

@app.route('/api/streaming/start', methods=['POST'])
def start_account_streaming():
    """Start real-time account streaming for the current user"""
    try:
        # Check sandbox authentication
        sandbox_token = session.get('sandbox_access_token')
        if not sandbox_token:
            return jsonify({
                'error': 'Sandbox authentication required for streaming',
                'authenticated': False
            }), 401
        
        # Get session ID
        session_id = get_user_session_id()
        
        # Import streamer after ensuring it's available
        from account_streamer import create_sandbox_streamer
        
        # Get sandbox account numbers from config/environment
        sandbox_accounts = [config.TT_TRADING_ACCOUNT_NUMBER] if config.TT_TRADING_ACCOUNT_NUMBER else []
        if not sandbox_accounts:
            # Try to get from TastyTrade API
            try:
                from trader import TastyTradeAPI
                api = TastyTradeAPI()
                api.trading_token = sandbox_token
                accounts = api.get_accounts()
                if accounts and len(accounts) > 0:
                    sandbox_accounts = [acc.get('account-number') for acc in accounts]
            except Exception as e:
                print(f"⚠️ Could not fetch account numbers: {e}")
                sandbox_accounts = []
        
        # Stop existing streamer if present
        if session_id in active_streamers:
            try:
                active_streamers[session_id].disconnect()
                print(f"🔌 Stopped existing streamer for session {session_id[:8]}...")
            except:
                pass
            del active_streamers[session_id]
        
        # Create and configure new streamer
        streamer = create_sandbox_streamer(sandbox_token, sandbox_accounts)
        
        # Add custom handlers for order and fill monitoring
        def order_handler(order_data, timestamp):
            """Handle order updates"""
            print(f"📝 Order Update - Session {session_id[:8]}: {order_data.get('id')} -> {order_data.get('status')}")
            # Store order update in trade data
            store_trade_data('latest_order_update', {
                'order_data': order_data,
                'timestamp': timestamp,
                'received_at': datetime.now().isoformat()
            })
        
        def fill_handler(fill_data, timestamp):
            """Handle fill notifications"""
            print(f"🎯 Fill Received - Session {session_id[:8]}: {fill_data}")
            # Store fill notification
            store_trade_data('latest_fill', {
                'fill_data': fill_data,
                'timestamp': timestamp,
                'received_at': datetime.now().isoformat()
            })
        
        def balance_handler(balance_data, timestamp):
            """Handle balance updates"""
            print(f"💰 Balance Update - Session {session_id[:8]}: {balance_data}")
            # Store balance update
            store_trade_data('latest_balance', {
                'balance_data': balance_data,
                'timestamp': timestamp,
                'received_at': datetime.now().isoformat()
            })
        
        # Set up handlers
        streamer.set_order_handler(order_handler)
        streamer.set_fill_handler(fill_handler)
        streamer.set_balance_handler(balance_handler)
        
        # Connect to streamer
        if streamer.connect():
            active_streamers[session_id] = streamer
            print(f"✅ Account streaming started for session {session_id[:8]}...")
            
            return jsonify({
                'success': True,
                'message': 'Account streaming started successfully',
                'accounts': sandbox_accounts,
                'session_id': session_id[:8],
                'status': streamer.get_status()
            })
        else:
            return jsonify({
                'error': 'Failed to connect to TastyTrade streamer',
                'success': False
            }), 500
            
    except Exception as e:
        print(f"❌ Error starting account streaming: {e}")
        return jsonify({
            'error': f'Failed to start streaming: {str(e)}',
            'success': False
        }), 500

@app.route('/api/streaming/stop', methods=['POST'])
def stop_account_streaming():
    """Stop account streaming for the current user"""
    try:
        session_id = get_user_session_id()
        
        if session_id in active_streamers:
            streamer = active_streamers[session_id]
            streamer.disconnect()
            del active_streamers[session_id]
            print(f"🔌 Stopped account streaming for session {session_id[:8]}...")
            
            return jsonify({
                'success': True,
                'message': 'Account streaming stopped successfully'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'No active streaming session found'
            })
            
    except Exception as e:
        print(f"❌ Error stopping account streaming: {e}")
        return jsonify({
            'error': f'Failed to stop streaming: {str(e)}',
            'success': False
        }), 500

@app.route('/api/streaming/status')
def get_streaming_status():
    """Get current streaming status for the user"""
    try:
        session_id = get_user_session_id()
        
        if session_id in active_streamers:
            streamer = active_streamers[session_id]
            status = streamer.get_status()
            
            # Add recent updates from trade store
            recent_updates = {
                'latest_order': get_trade_data('latest_order_update'),
                'latest_fill': get_trade_data('latest_fill'),
                'latest_balance': get_trade_data('latest_balance')
            }
            
            return jsonify({
                'streaming_active': True,
                'streamer_status': status,
                'recent_updates': recent_updates,
                'session_id': session_id[:8]
            })
        else:
            return jsonify({
                'streaming_active': False,
                'streamer_status': None,
                'recent_updates': {},
                'session_id': session_id[:8]
            })
            
    except Exception as e:
        print(f"❌ Error getting streaming status: {e}")
        return jsonify({
            'error': f'Failed to get status: {str(e)}',
            'streaming_active': False
        }), 500

@app.route('/api/streaming/updates')
def get_recent_updates():
    """Get recent order/fill updates from streaming"""
    try:
        # Get updates from trade store
        updates = {
            'orders': get_trade_data('latest_order_update'),
            'fills': get_trade_data('latest_fill'),
            'balances': get_trade_data('latest_balance'),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(updates)
        
    except Exception as e:
        print(f"❌ Error getting recent updates: {e}")
        return jsonify({
            'error': f'Failed to get updates: {str(e)}'
        }), 500

# Cleanup streamers when the app shuts down
import atexit

def cleanup_streamers():
    """Clean up all active streamers on app shutdown"""
    print("🧹 Cleaning up active streamers...")
    for session_id, streamer in active_streamers.items():
        try:
            streamer.disconnect()
        except:
            pass
    active_streamers.clear()

atexit.register(cleanup_streamers)

# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================

if __name__ == '__main__':
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