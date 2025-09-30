# Simple Flask app with SSL and TastyTrade OAuth2
from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime
from tt import get_oauth_authorization_url, exchange_code_for_token, set_access_token, set_refresh_token, get_market_data, get_oauth_token, get_options_chain, get_trading_range, get_options_chain_by_date
import config
import uuid
import db_storage  # Import our database storage module
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_in_production'

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
                         authenticated=True)

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
    """API endpoint to get the latest cached Grok response"""
    try:
        # Get session ID
        session_id = get_user_session_id()
        
        # Get user ID from database based on session ID
        user_id = db_storage.get_or_create_user_id(session_id=session_id)
        
        print(f"🔍 Cached response debug: session_id={session_id}, user_id={user_id}")
        
        # Get latest Grok response and parsed trade
        raw_response = db_storage.get_latest_data('grok_raw_response', user_id=user_id)
        parsed_trade = db_storage.get_latest_data('parsed_trade', user_id=user_id)
        
        print(f"🔍 Raw response found: {raw_response is not None}")
        print(f"🔍 Parsed trade found: {parsed_trade is not None}")
        
        # If no data found for current user, get latest from any user
        if not raw_response:
            print("🔄 No data for current user, checking for latest from any user...")
            conn = db_storage.get_db_connection()
            cursor = conn.cursor()
            
            # Get latest raw response from any user
            cursor.execute("SELECT data_json FROM trade_data WHERE data_type = 'grok_raw_response' ORDER BY updated_at DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                import json
                raw_response = json.loads(result['data_json'])
                print("✅ Found latest raw response from database")
            
            # Get latest parsed trade from any user  
            cursor.execute("SELECT data_json FROM trade_data WHERE data_type = 'parsed_trade' ORDER BY updated_at DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                import json
                parsed_trade = json.loads(result['data_json'])
                print("✅ Found latest parsed trade from database")
            
            conn.close()
        
        if raw_response:
            response_data = {
                'success': True,
                'cached_response': raw_response.get('response', ''),
                'timestamp': raw_response.get('timestamp', ''),
                'parsed_trade': parsed_trade
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
    """Check if user is authenticated"""
    token = session.get('access_token')
    return jsonify({
        'authenticated': token is not None,
        'session_active': 'access_token' in session
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
        
        # TODO: Implement actual trade execution with TastyTrade API
        # For now, return a success simulation
        return jsonify({
            'success': True,
            'order_id': 'SIM123456789',
            'result': {
                'status': 'Submitted',
                'strategy': parsed_trade.get('strategy', 'Unknown'),
                'message': f'Trade submitted successfully to {config.ENVIRONMENT_NAME} environment'
            }
        })
        
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