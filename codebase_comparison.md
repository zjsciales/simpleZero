# Codebase Comparison: Options Processing Systems

This document provides a thorough comparison of the attached development files to identify redundancies, overlaps, and the existence of multiple options processing systems in your codebase. The goal is to clarify how options data is fetched, parsed, and formatted, and to recommend a path toward consolidation and simplification.

---

## 1. **Files Involved in Options Processing**

- **tt.py**: TastyTrade API authentication, market data, and options chain endpoints.
- **tt_data.py**: Market data client, quote fetching, options chain formatting, technical analysis, and legacy Alpaca compatibility.
- **streamlined_data.py**: Streamlined market data collection, including global market overview, options chain fetching, and compact options chain logic.
- **dte_manager.py**: DTE (Days to Expiration) management, including DTE discovery, validation, and caching.

---

## 2. **Options Chain Fetching: Redundant Systems**

### **A. tt.py**
- Implements `get_options_chain`, `get_options_chain_by_date`, and related functions.
- Uses `/option-chains/{ticker}` endpoint for fetching options.
- Handles authentication, filtering, and parsing of options data.
- Contains logic for parsing option symbols and formatting options data.

### **B. tt_data.py**
- Implements `get_spy_options_chain`, `get_options_chain`, and `format_options_data`.
- Contains legacy Alpaca compatibility functions, but now uses TastyTrade endpoints.
- Provides DataFrame formatting and options flow analysis.
- Has its own symbol parsing and formatting logic.

### **C. streamlined_data.py**
- Calls `get_options_chain` from `tt.py` for options chain data.
- Implements `get_compact_options_chain` for fetching compact symbol lists.
- Uses `filter_options_by_criteria` and `get_options_market_data` for filtering and fetching market data for options.
- Contains its own symbol parsing logic (`parse_option_symbol`).

### **D. dte_manager.py**
- Focuses on DTE management and validation.
- Calls into options chain functions for DTE discovery.
- Contains logic for calculating expiration dates and validating available DTEs.

---

## 3. **Symbol Parsing: Multiple Implementations**

- **tt.py**: `parse_option_symbol(symbol)` parses TastyTrade option symbols.
- **tt_data.py**: Also implements `parse_option_symbol(symbol)` with similar but not identical logic.
- **streamlined_data.py**: Implements its own `parse_option_symbol(symbol)` with regex and manual parsing.

**Redundancy:**  
There are at least three separate implementations of symbol parsing, which can lead to inconsistencies and maintenance headaches.

---

## 4. **Options Data Formatting**

- **tt_data.py**: `format_options_data(options_data)` formats raw options data into a DataFrame, with detailed columns and spread calculations.
- **tt.py**: Formats options data for prompt generation and analysis, but not as a DataFrame.
- **streamlined_data.py**: Formats options data for prompt output, but does not use DataFrames.

**Redundancy:**  
Multiple formatting systems exist, with different output structures (DataFrame vs. dict/list). This can cause confusion when integrating with the UI or prompt generation.

---

## 5. **Options Chain Filtering**

- **tt.py**: Filters options by DTE, strike range, and option type within `get_options_chain`.
- **streamlined_data.py**: Uses `filter_options_by_criteria` to filter compact option symbols by DTE and strike range.
- **tt_data.py**: Filters options within DataFrame formatting and analysis functions.

**Overlap:**  
Filtering logic is duplicated across files, sometimes using different criteria or approaches.

---

## 6. **Market Data for Options**

- **tt.py**: Implements `get_options_market_data` to fetch market data for each option symbol individually.
- **streamlined_data.py**: Calls `get_options_market_data` after filtering symbols.
- **tt_data.py**: Does not fetch market data for options directly, but formats available quote data.

**Redundancy:**  
Market data fetching is centralized in `tt.py`, but called from multiple places.

---

## 7. **DTE Discovery and Management**

- **dte_manager.py**: Handles DTE discovery, caching, and validation, with logic for both static and live discovery.
- **streamlined_data.py**: Implements `get_available_dtes` by analyzing the raw options chain for expiration dates.
- **tt.py**: Also contains logic for DTE calculation and expiration date parsing.

**Overlap:**  
DTE management is split between `dte_manager.py`, `streamlined_data.py`, and `tt.py`, with some functions calling into each other.

---

## 8. **Legacy Alpaca Compatibility**

- **tt_data.py** and **dte_manager.py**: Still contain references and compatibility functions for Alpaca, even though the system is now TastyTrade-focused.

**Redundancy:**  
Legacy code can be removed to simplify the codebase.

---

## 9. **Prompt Generation and Data Flow**

- **tt.py** and **streamlined_data.py**: Both format options data for prompt generation, but sometimes the filtered/processed options data is not passed correctly to the prompt (as seen in your logs).

**Bug:**  
Options data may be processed but not included in the final prompt due to mismatched data structures or missing keys.

---

## 10. **Recommendations for Consolidation**

### **A. Centralize Option Symbol Parsing**
- Create a single, well-tested `parse_option_symbol(symbol)` function in a utility module.
- Refactor all files to use this function.

### **B. Unify Options Chain Fetching**
- Use one main function for fetching and filtering options chains (preferably in `tt.py` or a new `options.py`).
- Remove duplicate logic from `tt_data.py` and `streamlined_data.py`.

### **C. Standardize Data Formatting**
- Decide on a single output format for options data (dict/list or DataFrame).
- Refactor all formatting functions to use this standard.

### **D. Centralize Market Data Fetching**
- Keep market data fetching for options in one place (`tt.py`), and call it from other modules as needed.

### **E. Consolidate DTE Management**
- Move all DTE discovery and validation logic to `dte_manager.py`.
- Other modules should call into `dte_manager.py` for DTE-related operations.

### **F. Remove Legacy Alpaca Code**
- Delete all Alpaca compatibility functions and references.

### **G. Fix Data Flow to Prompt**
- Ensure that the processed options data is always passed to the prompt generation function.
- Add debug logging to verify data structures at each step.

---

## 11. **Summary Table**

| Functionality         | tt.py | tt_data.py | streamlined_data.py | dte_manager.py | Redundancy/Overlap |
|----------------------|-------|------------|--------------------|----------------|--------------------|
| Option Chain Fetch   | ✅    | ✅         | ✅                 | ❌             | High               |
| Symbol Parsing       | ✅    | ✅         | ✅                 | ❌             | High               |
| Data Formatting      | ✅    | ✅         | ✅                 | ❌             | High               |
| Market Data Fetch    | ✅    | ❌         | ✅                 | ❌             | Medium             |
| DTE Management       | ✅    | ❌         | ✅                 | ✅             | High               |
| Prompt Generation    | ✅    | ❌         | ✅                 | ❌             | Medium             |
| Alpaca Compatibility | ❌    | ✅         | ❌                 | ✅             | Legacy             |

---

## 12. **Action Items**

1. **Audit and remove duplicate symbol parsing functions.**
2. **Refactor options chain fetching to a single module.**
3. **Standardize options data formatting and output.**
4. **Centralize market data fetching for options.**
5. **Move all DTE logic to dte_manager.py.**
6. **Remove Alpaca legacy code.**
7. **Ensure prompt generation always receives the processed options data.**
8. **Add debug logging at each data handoff point.**

---

## 13. **Conclusion**

Your codebase currently has multiple overlapping systems for options processing, symbol parsing, and DTE management. Consolidating these into single, well-documented modules will reduce bugs, improve maintainability, and ensure that all features work as expected.

**Next Steps:**  
- Refactor for single-source-of-truth functions.
- Remove legacy and redundant code.
- Test data flow end-to-end, especially for prompt generation.

---

*Generated by GitHub Copilot on September 22, 2025.*