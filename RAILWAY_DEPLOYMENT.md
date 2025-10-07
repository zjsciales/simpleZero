rm # SimpleZero Railway Deployment Guide

This guide walks through deploying SimpleZero to Railway with PostgreSQL.

## 🚀 Quick Setup (Recommended)

### 1. Deploy to Railway
1. Fork this repository to your GitHub account
2. Go to [Railway](https://railway.app)
3. Connect your GitHub account
4. Click "New Project" → "Deploy from GitHub repo"
5. Select your forked `simpleZero` repository

### 2. Add PostgreSQL Database
1. In your Railway project dashboard, click "New Service"
2. Select "PostgreSQL" from the database options
3. Railway will automatically:
   - Provision a PostgreSQL instance
   - Set the `DATABASE_URL` environment variable
   - Connect it to your app

### 3. Configure Environment Variables
In Railway project settings, add these environment variables:

**Required:**
- `TT_API_KEY` - Your TastyTrade API key
- `TT_CLIENT_SECRET` - Your TastyTrade client secret  
- `TT_REDIRECT_URI` - Your TastyTrade OAuth redirect URI (set to your Railway domain + `/callback`)

**Automatic (set by Railway):**
- `DATABASE_URL` - PostgreSQL connection string (auto-configured)
- `ENVIRONMENT` - Set to "production" (in railway.toml)

### 4. Set Up PostgreSQL Schema via Terminal

**Option A: Using Railway CLI (Recommended)**

1. **Install Railway CLI** (if not already installed):
   ```bash
   # macOS
   brew install railway
   
   # Or with npm
   npm install -g @railway/cli
   ```

2. **Login and Link Project**:
   ```bash
   # Login to Railway
   railway login
   
   # Link to your existing project
   railway link
   # Select your workspace → project → production → Postgres service
   ```

3. **Apply the Database Schema**:
   ```bash
   # Connect to PostgreSQL and run schema
   railway connect
   # This opens psql shell connected to your Railway PostgreSQL
   
   # Copy and paste the contents of railway_schema.sql
   # Or run it directly:
   \i railway_schema.sql
   
   # Exit the database shell
   \q
   ```

**Option B: Using psql with DATABASE_URL**

1. **Get your DATABASE_URL**:
   ```bash
   railway variables
   # Look for DATABASE_PUBLIC_URL (for external access)
   ```

2. **Connect using psql**:
   ```bash
   # Replace with your actual DATABASE_PUBLIC_URL from Railway
   psql "postgresql://postgres:ZWIcHp...@centerbeam.proxy.rlwy.net:16984/railway"
   ```

3. **Run the Schema**:
   ```bash
   # Inside psql, run the schema file
   \i railway_schema.sql
   
   # Or copy/paste the schema manually
   # Exit when done
   \q
   ```

**Option C: Direct SQL Copy/Paste**

If the above methods don't work, copy the entire contents of `railway_schema.sql` and paste directly into any PostgreSQL client connected to your Railway database.

**Verify Setup**:
```bash
# Test that tables were created
railway connect
\dt
# Should show: trades, grok_analyses, performance_metrics, market_snapshots
\q
```

### 5. Access Your App
- Main app: `https://your-app-name.up.railway.app`
- Public scoreboard: `https://your-app-name.up.railway.app/scoreboard`
- Analysis library: `https://your-app-name.up.railway.app/library`

## 🔧 PostgreSQL Schema Setup

### Database Schema Files

The repository includes two key files for database setup:

- **`railway_schema.sql`** - Complete PostgreSQL schema optimized for Railway
- **`database_schema.sql`** - Full schema with sample data and documentation

### Quick Schema Application

**Method 1: Railway CLI (Simplest)**
```bash
# After linking your project
railway connect
\i railway_schema.sql
\q
```

**Method 2: psql with Connection String**
```bash
# Get DATABASE_PUBLIC_URL from: railway variables
psql "your-database-url-here" -f railway_schema.sql
```

**Method 3: Copy/Paste Method**
1. Open `railway_schema.sql` in your editor
2. Copy the entire contents (112 lines)
3. Connect to your PostgreSQL database via any client
4. Paste and execute the SQL

### What the Schema Creates

- **`trades`** table - Core trading data and performance tracking
- **`grok_analyses`** table - AI trading insights and recommendations  
- **`performance_metrics`** table - Aggregated performance data for scoreboard
- **`market_snapshots`** table - Historical market data
- **Indexes** for optimal query performance
- **Initial data** with zero performance metrics
- **`public_scoreboard`** view for easy API queries

## 🔧 Environment Configuration

### Environment Variables Details

| Variable | Description | Example |
|----------|-------------|---------|
| `TT_API_KEY` | TastyTrade API key | `your-api-key` |
| `TT_CLIENT_SECRET` | TastyTrade client secret | `your-client-secret` |
| `TT_REDIRECT_URI` | OAuth redirect URI | `https://your-app.up.railway.app/callback` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `ENVIRONMENT` | Deployment environment | `production` |

### Database Configuration

The app automatically detects the environment:
- **Local Development**: Uses SQLite (`simple_zero_data.db`)
- **Production**: Uses PostgreSQL (via `DATABASE_URL`)

### Health Checks

Railway automatically monitors the `/health` endpoint:
- Returns 200 for healthy status
- Returns 503 for unhealthy status
- Checks database connectivity

## 📊 Public Features

Once deployed, your app includes public pages that don't require authentication:

### Scoreboard (`/scoreboard`)
- Live trading performance metrics
- Win/loss statistics  
- Recent trade results
- All-time performance summary

### Analysis Library (`/library`)
- Archive of all Grok AI analyses
- Searchable by ticker and date
- Performance tracking per analysis
- Filter by DTE (Days to Expiration)

## 🔄 Data Migration

The migration script (`migrate_database.py`) handles:
- Creating PostgreSQL schema from `database_schema.sql`
- Migrating existing SQLite data to PostgreSQL
- Setting up initial performance metrics
- Verifying migration success

**Run migration after first deployment:**
```bash
python migrate_database.py
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Railway App   │    │   PostgreSQL    │    │   TastyTrade    │
│                 │    │                 │    │      API        │
│  Flask Web App  │◄──►│   Database      │    │                 │
│  Public Routes  │    │   - Trades      │    │  OAuth2 & Data  │
│  Health Checks  │    │   - Analyses    │    │                 │
│                 │    │   - Metrics     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🐛 Troubleshooting

### Database Connection Issues
1. Check Railway logs for connection errors
2. Verify `DATABASE_URL` is set correctly
3. Ensure PostgreSQL service is running
4. **Run schema setup if tables are missing**:
   ```bash
   railway connect
   \dt  # List tables - should show trades, grok_analyses, etc.
   ```

### Schema Setup Issues
1. **Tables not found**: Re-run `railway_schema.sql`
2. **Permission errors**: Ensure you're connected to the right database
3. **Connection timeout**: Use DATABASE_PUBLIC_URL for external access
4. **psql not found**: Install PostgreSQL client tools

### Testing Database Setup
```bash
# Verify all tables exist
railway connect
\dt

# Test a simple query
SELECT 'Database working!' as status;

# Check performance metrics table
SELECT * FROM performance_metrics;
\q
```

### Authentication Issues  
1. Verify TastyTrade API credentials
2. Check redirect URI matches Railway domain
3. Ensure OAuth2 flow is working

### Health Check Failures
1. Check `/health` endpoint manually
2. Review Railway deployment logs
3. Verify database connectivity
4. Check application startup errors

## 📈 Scaling

The PostgreSQL database is designed to handle:
- **10,000+ Grok analyses** with full text search
- **100,000+ trade records** with performance indexing
- **Real-time market data** with efficient storage
- **Public API endpoints** with optimized queries

## 🔒 Security

- Environment variables for sensitive data
- Production-only database access
- Health check endpoints don't expose secrets
- OAuth2 authentication with TastyTrade

---

## Next Steps

1. **Deploy to Railway** using the quick setup above
2. **Set up PostgreSQL schema** using one of the terminal methods
3. **Configure TastyTrade OAuth** with your Railway domain  
4. **Test public scoreboard** and analysis library
5. **Start trading** and watch your performance metrics grow!

### Post-Deployment Checklist

- [ ] PostgreSQL service added to Railway project
- [ ] Database schema applied via terminal (`railway_schema.sql`)
- [ ] Environment variables configured (TT_API_KEY, TT_CLIENT_SECRET, etc.)
- [ ] Health check endpoint responding at `/health`
- [ ] Public pages accessible at `/scoreboard` and `/library`
- [ ] OAuth flow working with TastyTrade

Your SimpleZero app will automatically scale with Railway's infrastructure and provide a professional trading analysis platform.