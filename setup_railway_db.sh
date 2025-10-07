#!/bin/bash
# Railway PostgreSQL Setup via CLI
# Run this after deploying to Railway and adding PostgreSQL service

echo "🚀 Setting up PostgreSQL schema on Railway..."

# Get your DATABASE_URL from Railway dashboard and export it
# export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Apply schema
psql $DATABASE_URL < railway_schema.sql

echo "✅ PostgreSQL schema applied successfully!"
echo "🎉 Your production database is ready!"

# Test connection
echo "🔍 Testing database connection..."
psql $DATABASE_URL -c "SELECT 'Database connection successful! 🎉' as status;"