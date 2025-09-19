# Simple Flask app with SSL and TastyTrade OAuth2
from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime
from tt import get_oauth_authorization_url, exchange_code_for_token, set_access_token, set_refresh_token, get_market_data, get_oauth_token, get_options_chain, get_trading_range, get_options_chain_by_date
import config

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_in_production'

# Set Flask configuration based on environment
app.config['DEBUG'] = config.DEBUG
app.config['ENV'] = config.FLASK_ENV

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
        return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard page - requires authentication"""
    token = session.get('access_token')
    if not token:
        return redirect('/')
    
    # Ensure tt.py has the token
    set_access_token(token)
    return render_template('dashboard.html')

@app.route('/login')
def login():
    """Redirect to TastyTrade OAuth2 authorization"""
    auth_url = get_oauth_authorization_url()
    print(f"🔗 Redirecting to: {auth_url}")
    return redirect(auth_url)

@app.route('/zscialespersonal')
def oauth_callback():
    """Handle OAuth2 callback from TastyTrade"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        return f"OAuth Error: {error}", 400
    
    if not code:
        return "No authorization code received", 400
    
    # Exchange code for token
    token_data = exchange_code_for_token(code)
    
    if token_data and token_data.get('access_token'):
        # Store both access and refresh tokens in session
        session['access_token'] = token_data['access_token']
        if token_data.get('refresh_token'):
            session['refresh_token'] = token_data['refresh_token']
        
        # Also set the tokens in tt.py module
        set_access_token(token_data['access_token'])
        if token_data.get('refresh_token'):
            set_refresh_token(token_data['refresh_token'])
            
        return redirect('/dashboard')
    else:
        return "Failed to exchange code for token", 500

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

@app.route('/api/trading-range')
def api_trading_range():
    """API endpoint for trading range calculation"""
    try:
        print("🔍 Flask session check:")
        print(f"  - Has access_token: {'access_token' in session}")
        print(f"  - Has refresh_token: {'refresh_token' in session}")
        
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
        
        print(f"🤖 Starting Grok analysis for {ticker} {dte}DTE")
        
        # Create GrokAnalyzer
        analyzer = GrokAnalyzer()
        
        # Generate comprehensive market analysis prompt
        prompt = f"""Analyze the current market conditions for {ticker} with {dte}DTE focus:

Market Analysis Request:
- Ticker: {ticker}
- Days to Expiration: {dte}
- Analysis Type: {"Intraday scalping" if dte == 0 else f"{dte}-day swing trading"}
- Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}

Please provide a comprehensive analysis including:

1. **Current Market Assessment**
   - Overall market sentiment and trend direction
   - Key technical levels (support/resistance)
   - Current price action and momentum indicators

2. **Technical Analysis**
   - RSI conditions and overbought/oversold levels
   - Moving average positioning and trends
   - Bollinger Band analysis and volatility assessment

3. **Options Trading Opportunities**
   - Optimal strike price recommendations for {dte}DTE
   - Credit spread opportunities (put/call spreads)
   - Risk/reward ratios for recommended trades

4. **Risk Management**
   - Position sizing recommendations
   - Stop-loss levels and profit targets
   - Market conditions to avoid trading

5. **Actionable Insights**
   - Specific entry and exit strategies
   - Time-of-day considerations for {dte}DTE trading
   - Market catalysts to watch

Focus on actionable, specific recommendations for {ticker} {dte}DTE trading with current market conditions."""

        print(f"📤 Sending market analysis prompt to Grok...")
        grok_response = analyzer.send_to_grok(prompt)
        
        if grok_response:
            print(f"✅ Grok analysis completed")
            return jsonify({
                'success': True,
                'analysis': grok_response,
                'ticker': ticker,
                'dte': dte
            })
        else:
            print(f"❌ Grok analysis failed")
            return jsonify({'error': 'Grok analysis failed'}), 500
            
    except Exception as e:
        print(f"💥 Exception in Grok analysis: {e}")
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

if __name__ == '__main__':
    if config.IS_PRODUCTION:
        # Production settings for Railway
        app.run(
            debug=config.DEBUG,
            host='0.0.0.0',
            port=config.PORT,
            threaded=True
            # No SSL in production - Railway handles TLS termination
        )
    else:
        # Development settings with SSL
        app.run(
            debug=config.DEBUG,
            host='0.0.0.0',
            port=config.PORT,
            threaded=True,
            ssl_context=('certs/cert.pem', 'certs/key.pem')
        )