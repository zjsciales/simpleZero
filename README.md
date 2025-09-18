# SPY Options Trading System with Enhanced Grok AI Analysis

A comprehensive Python-based options trading system that integrates TastyTrade API with advanced Grok AI market analysis for sophisticated SPY options trading strategies.

## 🚀 Key Features

### Enhanced Market Analysis (Comprehensive v7)
- **Real-time Market Data Quality**: 1-minute precision price action with DTE-aware data collection
- **Advanced Options Chain Analysis**: Enhanced bid/ask spreads, Greeks integration, and liquidity metrics
- **Sophisticated Volume Analysis**: Flow pattern detection, unusual volume alerts, and directional bias confirmation
- **Professional Technical Indicators**: Multi-timeframe RSI, Bollinger Band squeeze detection, and volatility breakout analysis

### Trading Capabilities
- **DTE-Aware Trading**: Optimized strategies for 0DTE through longer-term expiration dates
- **Risk Management**: Comprehensive position sizing and risk controls
- **Automated Execution**: Integration with TastyTrade for live order execution
- **Strategy Focus**: Vertical spreads (Bull Put, Bear Call, Iron Condor)

### AI Integration
- **Grok AI Analysis**: Advanced market analysis using XAI's Grok model
- **Intelligent Prompts**: Comprehensive market data formatting for optimal AI recommendations
- **Strategy Selection**: AI-driven optimal strategy selection based on market conditions

## 📊 Technical Analysis Features

### Enhanced RSI Analysis
- Multi-timeframe precision with primary and secondary timeframe confirmation
- Momentum pattern detection (accelerating, rising, consolidating, falling)
- Divergence analysis and enhanced interpretation
- RSI strength calculations with rate of change analysis

### Advanced Bollinger Bands
- Squeeze detection (width in lower 20th percentile)
- Volume-confirmed breakouts with significance analysis
- Volatility expansion detection using ATR analysis
- Market state classifications (Squeeze, Breakout, Expansion, Normal Range)

### Volume Flow Analysis
- Directional flow bias (Strong/Moderate Call/Put Flow, Balanced)
- Unusual volume detection (2+ standard deviations above mean)
- Volume concentration analysis and high-volume strike identification
- Call/put ratio analysis with flow confirmation

## 🛠 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/simpleZero.git
   cd simpleZero
   ```

2. **Set up Python environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Required API Keys**
   - TastyTrade API credentials
   - XAI API key for Grok AI integration

## 📁 Project Structure

```
simpleZero/
├── app.py                    # Flask web application
├── grok.py                   # Enhanced Grok AI analysis system
├── tt.py                     # TastyTrade API integration
├── tt_data.py                # Enhanced technical analysis
├── config.py                 # Configuration settings
├── dte_manager.py            # DTE-aware trading logic
├── auto_trade_scheduler.py   # Automated trading scheduler
├── templates/                # Web UI templates
├── certs/                    # SSL certificates
└── requirements.txt          # Python dependencies
```

## 🔧 Configuration

### Environment Variables (.env)
```env
# TastyTrade API
TASTYTRADE_USERNAME=your_username
TASTYTRADE_PASSWORD=your_password

# XAI Grok API
XAI_API_KEY=your_xai_api_key

# Trading Configuration
PAPER_TRADING=true
DEFAULT_TICKER=SPY
MAX_DAILY_LOSS=500
```

### Key Configuration Options
- **DTE Management**: Automated expiration date handling
- **Risk Parameters**: Position sizing and loss limits
- **Technical Analysis**: RSI periods, Bollinger Band settings
- **Volume Thresholds**: Unusual volume detection sensitivity

## 🎯 Usage

### Web Interface
```bash
python app.py
```
Access the web interface at `https://localhost:5001`

### Direct Analysis
```python
from grok import run_dte_aware_analysis

# Run comprehensive market analysis
results = run_dte_aware_analysis(dte=0, ticker="SPY")
print(results['grok_response'])
```

### Automated Trading
```python
from grok import run_automated_analysis_and_trading

# Complete workflow: analysis + execution
results = run_automated_analysis_and_trading()
```

## 📈 Enhanced Analysis Capabilities

### Market Data Collection
- **Real-time Precision**: 1-minute bars with comprehensive OHLCV data
- **DTE Optimization**: Timeframe adaptation based on expiration date
- **Price Action**: Last 10 bars analysis with change calculations

### Options Analysis
- **Enhanced Chain Data**: Bid/ask spreads with mid-price calculations
- **Greeks Integration**: Comprehensive Delta, Gamma, Theta, Vega analysis
- **Volume Patterns**: Flow detection with unusual activity alerts

### Technical Indicators
- **Multi-timeframe RSI**: Primary/secondary timeframe confirmation
- **Bollinger Analysis**: Squeeze detection and breakout confirmation
- **Trend Strength**: Percentage-based measurements with multi-period validation

## 🔐 Security

- Environment variables for sensitive data
- SSL certificate support for web interface
- API key encryption and secure storage
- Trading confirmation requirements

## 🚧 Development

### Running Tests
```bash
python -m pytest tests/
```

### Code Quality
```bash
# Format code
black .

# Lint
flake8 .
```

## 📊 Performance Metrics

The enhanced system provides:
- **Institutional-grade analysis** with professional technical indicators
- **Multi-timeframe confirmation** for high-probability setups
- **Volume validation** for trade confirmation
- **Risk-adjusted returns** through sophisticated position sizing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading options involves substantial risk and is not suitable for all investors. Past performance does not guarantee future results. Always consult with a qualified financial advisor before making trading decisions.

## 🙏 Acknowledgments

- TastyTrade for market data and execution API
- XAI for Grok AI analysis capabilities
- Python community for excellent libraries and tools

---

**Built with comprehensive market analysis and institutional-grade technical indicators for sophisticated options trading strategies.**