# SimpleZero UI Enhancement TODOs

## Universal Interface for Credential Status

This document outlines the tasks needed to implement a unified interface for displaying the active credentials and environment status across the application.

## UI Components to Update

### 1. Base Template (`base.html`)

- [ ] Add a persistent environment indicator in the navbar
  - Should clearly show "PRODUCTION" or "SANDBOX" mode
  - Use distinctive colors (green for production, amber for sandbox)
  - Add tooltip with full environment details

- [ ] Create a status indicator for authentication
  - Show token status (valid/expired/missing)
  - Display remaining token lifetime
  - Add option to refresh tokens manually

- [ ] Add a collapsible debug panel (for development)
  - Show current API URLs in use
  - Display active credential source
  - Include toggle for sandbox mode

### 2. Dashboard UI (`dashboard.html`)

- [ ] Add credential status summary card
  - Show account details from active credentials
  - Display TastyTrade account number currently in use
  - Add visual distinction between production/sandbox accounts

- [ ] Create environment-aware trade buttons
  - Color-code buttons based on environment
  - Add confirmation dialogs with environment details for trades
  - Include environment labels on action buttons

- [ ] Implement credential switching interface
  - Add UI controls to switch between environments
  - Include confirmation for environment switches
  - Show loading indicators during credential changes

### 3. Trade Interface (`trade.html`)

- [ ] Add prominent environment banner
  - Large, visible indicator of current trading environment
  - Warning indicators for production environment
  - Clear labeling on all trade actions

- [ ] Implement order preview with environment context
  - Show environment as part of order preview
  - Include account details from active environment
  - Display different styling based on environment

- [ ] Add real-time credential status monitoring
  - Show token expiration countdown
  - Provide automatic refresh mechanism
  - Display connection status to appropriate TastyTrade environment

## Backend Support (`trader.py`)

- [ ] Create unified credential status method
  ```python
  def get_credential_status():
      """
      Returns a dictionary with comprehensive credential status information
      for use in UI templates.
      """
      return {
          'environment': 'PRODUCTION' if not config.USE_SANDBOX_MODE else 'SANDBOX',
          'account_number': self.account_number,
          'token_valid': self.is_token_valid(),
          'token_expires_in': self.get_token_expiry_seconds(),
          'api_url': self.base_url,
          'authenticated': self.is_authenticated(),
          'account_status': self.get_account_status()
      }
  ```

- [ ] Add methods to expose environment information
  - Function to check token validity and expiration
  - Method to get current environment details
  - API to check account connection status

- [ ] Implement consistent environment switching
  - Method to safely switch environments
  - Function to verify environment configuration
  - Callback to update UI when environment changes

## Data Models & Context Processors

- [ ] Create Flask context processor for environment data
  ```python
  @app.context_processor
  def inject_environment_info():
      """
      Adds environment information to all templates automatically
      """
      return {
          'environment': 'PRODUCTION' if not config.USE_SANDBOX_MODE else 'SANDBOX',
          'environment_color': 'success' if not config.USE_SANDBOX_MODE else 'warning',
          'is_authenticated': tt.is_authenticated(),
          'token_valid': tt.is_token_valid(),
          'account_number': session.get('account_number', 'Not selected')
      }
  ```

- [ ] Create environment status model
  - Class to represent environment status
  - Methods for environment comparison
  - Serialization for API responses

## Implementation Steps

1. **Design UI Components**
   - [ ] Create mockups for environment indicators
   - [ ] Design color scheme for different environments
   - [ ] Draft layout for status panels

2. **Update Templates**
   - [ ] Modify base.html with status components
   - [ ] Update dashboard.html with environment context
   - [ ] Enhance trade.html with safety features for production

3. **Backend Support**
   - [ ] Add API endpoints for environment status
   - [ ] Create context processors for template data
   - [ ] Implement status monitoring services

4. **Testing**
   - [ ] Test environment switching in UI
   - [ ] Verify correct display in all environments
   - [ ] Ensure proper warnings for production actions

5. **Documentation**
   - [ ] Document UI components and their meaning
   - [ ] Create user guide for environment switching
   - [ ] Add developer notes for extending the system

## Visual Designs

### Environment Indicator Example

```html
<!-- Environment indicator for navbar -->
<div class="env-indicator env-{{ environment_color }}">
  <i class="fas fa-{{ 'shield-alt' if environment == 'PRODUCTION' else 'flask' }}"></i>
  <span>{{ environment }}</span>
  {% if environment == 'PRODUCTION' %}
    <span class="badge badge-danger">LIVE</span>
  {% endif %}
</div>
```

### Token Status Component

```html
<!-- Token status indicator -->
<div class="token-status">
  <div class="status-indicator {{ 'valid' if token_valid else 'invalid' }}"></div>
  <div class="token-details">
    <span class="token-env">{{ environment }}</span>
    <span class="token-expiry">{{ token_expires_in | format_time }}</span>
  </div>
  <button class="btn btn-sm btn-refresh" onclick="refreshToken()">
    <i class="fas fa-sync"></i>
  </button>
</div>
```

### CSS for Environment Styling

```css
/* Environment-specific styling */
.env-success {
  background-color: #d4edda;
  border-color: #c3e6cb;
  color: #155724;
}

.env-warning {
  background-color: #fff3cd;
  border-color: #ffeeba;
  color: #856404;
}

/* Trade button styling based on environment */
.btn-trade-production {
  background-color: #dc3545;
  color: white;
  font-weight: bold;
}

.btn-trade-sandbox {
  background-color: #ffc107;
  color: #212529;
}
```