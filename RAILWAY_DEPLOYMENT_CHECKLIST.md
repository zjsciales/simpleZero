# Railway Production Deployment Checklist

## ✅ Pre-Deployment Verification

### Environment Detection
- [x] Railway environment detection via `RAILWAY_ENVIRONMENT` 
- [x] Fallback detection via `PORT` environment variable
- [x] Production config in `railway.toml` sets `ENVIRONMENT=production`

### Database Configuration  
- [x] PostgreSQL dependency (`psycopg2-binary`) in requirements.txt
- [x] DATABASE_URL environment variable support
- [x] Graceful fallback to SQLite if PostgreSQL fails
- [x] Schema compatibility between PostgreSQL and SQLite

### Database Schema Updates
- [x] Updated `railway_schema.sql` with `include_sentiment` column
- [x] Fixed `store_grok_analysis()` function for PostgreSQL compatibility  
- [x] Ensured parameter counts match between PostgreSQL (%s) and SQLite (?)

### Application Features
- [x] Database storage hooks in `/api/grok-analysis` endpoint
- [x] Database storage hooks in `/api/generate-prompt` endpoint  
- [x] Database storage hooks in `/api/sync-positions` endpoint
- [x] Performance metrics updating after trade saves
- [x] SPY-only filtering for all public data

## 🚀 Deployment Process

1. **Push to Railway**
   ```bash
   git add .
   git commit -m "feat: add database storage hooks for all generated content"
   git push origin feature/open-acesss
   ```

2. **Railway Auto-Deploy**
   - Railway will detect the push and auto-deploy
   - PostgreSQL database will be initialized with `railway_schema.sql`
   - Environment variables will be set from `railway.toml`

3. **Verify Deployment**
   - Check Railway logs for successful deployment
   - Test database connectivity endpoint: `/api/test-database`
   - Verify public pages show real data: `/scoreboard`, `/library`

## 🔍 Production Testing Endpoints

### Test Database Connectivity
```
GET https://your-railway-app.railway.app/api/test-database
```

### Test Grok Analysis Generation (with database save)
```
POST https://your-railway-app.railway.app/api/grok-analysis
{
  "ticker": "SPY",
  "dte": 0,
  "include_sentiment": true
}
```

### Test Position Sync (with database save)
```
GET https://your-railway-app.railway.app/api/sync-positions
```

### Verify Public Data
```
GET https://your-railway-app.railway.app/api/public/live-trades
GET https://your-railway-app.railway.app/api/public/performance  
GET https://your-railway-app.railway.app/api/public/latest-analysis
```

## 🛠️ Troubleshooting

### If PostgreSQL Connection Fails
- Check Railway PostgreSQL service is running
- Verify DATABASE_URL environment variable is set
- System will automatically fallback to SQLite

### If Data Not Appearing
- Check application logs for database save errors
- Verify database hooks are being called in endpoints
- Test direct database functions with `/api/test-database`

### Schema Issues
- Verify `railway_schema.sql` was applied correctly
- Check PostgreSQL logs for schema creation errors
- Compare local SQLite schema with production PostgreSQL

## 📊 Expected Results

After successful deployment:
- **Scoreboard**: Shows real SPY trading performance metrics
- **Library**: Shows historical Grok analyses for SPY  
- **Live Trades**: Shows real positions synced from TastyTrade
- **Database**: PostgreSQL with all tables populated from generated content

All generated content (Grok analyses, trades, prompts) will be automatically saved to the database and available on public pages.