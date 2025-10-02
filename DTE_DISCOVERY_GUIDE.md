# Smart DTE Discovery System

## Overview

The automation system now includes intelligent DTE (Days to Expiration) discovery that automatically finds the optimal expiration date within our target range, rather than hardcoding 32 days.

## Problem Solved

**Before**: Hardcoded 32 DTE could land on weekends, holidays, or dates without available options
**After**: Smart discovery finds the best available expiration date within 28-35 days for weekly trades

## How It Works

### DTE Discovery Algorithm

1. **Query Available Expirations**: Uses existing `get_available_dtes()` function to fetch all available expiration dates from TastyTrade API
2. **Filter by Range**: Finds all expirations within acceptable range (target ± tolerance)
3. **Optimize Selection**: Sorts candidates by:
   - Distance from target (32 days)
   - Option count (liquidity indicator)
4. **Select Best Match**: Returns the optimal DTE

### Target Ranges by Context

- **Weekly Analysis**: 32 ± 3 days (29-35 range) for consistency
- **Test Analysis**: 32 ± 10 days (22-42 range) for flexibility  
- **Force Execute**: 32 ± 8 days (24-40 range) for manual testing

### Fallback Strategy

- If no 32DTE available in test mode, tries 7DTE ± 3 days
- If complete discovery fails, falls back to original target
- Comprehensive logging shows what was found and why

## Code Implementation

### New Method: `find_optimal_dte()`

```python
def find_optimal_dte(self, ticker: str = "SPY", target_dte: int = 32, tolerance: int = 5) -> Optional[int]:
    # Discovers optimal DTE within target ± tolerance range
    # Returns best available expiration date
```

### Updated Execution Methods

- `_execute_weekly_trade_analysis()`: Uses 32±3 days for weekly consistency
- `_execute_test_analysis()`: Uses 32±10 days with 7DTE fallback
- `force_execute_trade()`: Uses 32±8 days for manual testing

### New API Endpoint

- `/api/automation/dte-discovery`: Shows current optimal DTE and available options

## UI Enhancements

### Dashboard Display

- Shows "Next optimal expiration: X days" under strategy description
- Updates automatically when automation status refreshes
- Force execute button shows selected DTE in success message

### User Benefits

- **Transparency**: Users see which expiration was selected
- **Confidence**: Algorithm shows reasoning and alternatives
- **Flexibility**: System adapts to market conditions automatically

## Example Scenarios

### Scenario 1: Normal Monday
- Target: 32 DTE (Friday expiration)
- Found: 32 DTE available ✅
- Selected: 32 DTE (perfect match)

### Scenario 2: Holiday Week  
- Target: 32 DTE (falls on holiday)
- Found: 31 DTE and 33 DTE available
- Selected: 31 DTE (closer to target)

### Scenario 3: Low Liquidity
- Target: 32 DTE (only 5 options available)
- Found: 30 DTE (150 options), 35 DTE (20 options)
- Selected: 30 DTE (better liquidity, within range)

## Logging Output

```
🎯 Finding optimal DTE for SPY (target: 32±5 days)
✅ Optimal DTE found: 31 days (2025-11-03)
   📊 Options available: 1,247
   🎯 Distance from target: 1 days
   🔄 Alternatives: 33DTE, 35DTE
```

## Benefits

1. **Market Adaptive**: Works with actual available expirations
2. **Holiday Aware**: Automatically avoids weekends/holidays
3. **Liquidity Conscious**: Prefers expirations with more options
4. **Transparent**: Full logging of selection process
5. **Flexible**: Different tolerances for different use cases
6. **Robust**: Fallback strategies if discovery fails

## Future Enhancements

- **Volume Analysis**: Consider actual trading volume, not just option count
- **Bid-Ask Spreads**: Factor in spread tightness for liquidity assessment  
- **Multiple Strategies**: Different DTE preferences for different spread types
- **User Preferences**: Allow users to adjust target ranges
- **Market Conditions**: Tighter ranges during high volatility periods

This smart DTE discovery ensures that the automation system always finds tradeable, liquid options within our target timeframe, regardless of holidays, weekends, or market conditions.