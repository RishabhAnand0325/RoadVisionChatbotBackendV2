# Production Data Sync to Local Development Server

**Date**: November 4, 2025
**Purpose**: Sync all production data (PostgreSQL, Weaviate, DMS folders) to local development environment
**Time Required**: 15-60 minutes (depends on data size)

---

## Overview

This guide shows how to:
1. Backup PostgreSQL database from production
2. Download PostgreSQL backup to your local machine
3. Restore PostgreSQL locally
4. Backup Weaviate vector database from production
5. Download and restore Weaviate locally
6. Sync DMS folders using SCP
7. Verify everything works

---

## Prerequisites

### On Production Server
- SSH access with sudo/admin privileges
- `pg_dump` installed (comes with PostgreSQL)
- `tar` and `gzip` installed (standard on Linux)
- Docker or direct Weaviate access
- At least 2x the database size in free disk space for backup

### On Your Local Machine
- SSH key configured for production server access
- `psql` client installed (PostgreSQL client tools)
- `curl` or similar for Weaviate API testing
- Sufficient disk space for backups
- `scp` configured (for DMS folders)

---

## Part 1: PostgreSQL Backup & Restore

### Step 1.1: Check Database Size

**On Production Server**:
```bash
# SSH to production
ssh user@prod-server

# Check database size
psql -h <db-host> -U <db-user> -c "SELECT pg_database_size('ceigall') as size;"

# Example output:
# size
# ──────────────
# 523456789  (about 523 MB)
```

### Step 1.2: Create Full Backup

**On Production Server**:
```bash
# Set variables
DB_HOST="<database-host>"
DB_USER="<database-user>"
DB_NAME="ceigall"
BACKUP_DIR="/tmp/pg_backups"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Create full backup (custom format - more flexible)
pg_dump -h $DB_HOST -U $DB_USER -Fc $DB_NAME > $BACKUP_DIR/ceigall_${BACKUP_DATE}.dump

# Verify backup created
ls -lh $BACKUP_DIR/ceigall_${BACKUP_DATE}.dump

# Expected: file should be similar size to database
# (custom format is often smaller than plain text)
```

### Step 1.3: Compress Backup (Optional but Recommended)

**On Production Server**:
```bash
# Compress the backup further
gzip $BACKUP_DIR/ceigall_${BACKUP_DATE}.dump

# Check compressed size
ls -lh $BACKUP_DIR/ceigall_${BACKUP_DATE}.dump.gz

# Now you can delete the uncompressed version
rm $BACKUP_DIR/ceigall_${BACKUP_DATE}.dump
```

### Step 1.4: Download Backup to Local Machine

**On Your Local Machine**:
```bash
# Set variables
PROD_USER="your-prod-username"
PROD_HOST="prod-server.com"
PROD_BACKUP_PATH="/tmp/pg_backups/ceigall_*.dump.gz"
LOCAL_BACKUP_DIR="~/production_data/postgres"

# Create local directory
mkdir -p $LOCAL_BACKUP_DIR

# Download the backup
scp -r $PROD_USER@$PROD_HOST:$PROD_BACKUP_PATH $LOCAL_BACKUP_DIR/

# Verify download
ls -lh $LOCAL_BACKUP_DIR/
```

### Step 1.5: Prepare Local Database

**On Your Local Machine**:
```bash
# Check if PostgreSQL is running
psql --version

# If not installed, install it:
# macOS:
brew install postgresql

# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL (if not already running)
# macOS:
brew services start postgresql

# Ubuntu/Debian:
sudo systemctl start postgresql
```

### Step 1.6: Create Local Database

**On Your Local Machine**:
```bash
# Connect to PostgreSQL (default user is 'postgres')
psql -U postgres

# Inside psql:
CREATE DATABASE ceigall_dev;
\q

# Or from command line:
createdb -U postgres ceigall_dev
```

### Step 1.7: Restore PostgreSQL Backup

**On Your Local Machine**:
```bash
# Set variables
BACKUP_FILE="~/production_data/postgres/ceigall_*.dump.gz"
LOCAL_DB="ceigall_dev"
LOCAL_USER="postgres"

# Decompress if needed
# gunzip $BACKUP_FILE
# Note: pg_restore can read gzipped files directly

# Restore the backup
pg_restore -h localhost -U $LOCAL_USER -d $LOCAL_DB $BACKUP_FILE

# This will take a few minutes depending on database size
# Output will show progress
```

### Step 1.8: Verify PostgreSQL Restore

**On Your Local Machine**:
```bash
# Connect to the restored database
psql -h localhost -U postgres -d ceigall_dev

# Inside psql, run verification queries:
SELECT COUNT(*) as scrape_runs FROM scrape_runs;
SELECT COUNT(*) as tenders FROM scraped_tenders;
SELECT COUNT(*) as dms_documents FROM dms_documents;
SELECT COUNT(*) as dms_folders FROM dms_folders;

\q

# Update your .env to use the local database
# Change DATABASE_URL=postgresql://...local... or update connection string
```

---

## Part 2: Weaviate Backup & Restore

Weaviate stores vector embeddings. You need to backup and restore its data.

### Step 2.1: Check Weaviate Status

**On Production Server**:
```bash
# Check if Weaviate is running (usually on port 8080)
curl -s http://localhost:8080/v1/.well-known/ready

# If running in Docker:
docker ps | grep weaviate

# Get Weaviate container ID
WEAVIATE_CONTAINER=$(docker ps --filter "name=weaviate" -q)
```

### Step 2.2: Backup Weaviate Data

**Option A: If Weaviate is in Docker with volume mount**

**On Production Server**:
```bash
# Find the Weaviate volume location
docker inspect weaviate | grep -A 5 '"Mounts"'

# Look for "Source" path - that's where the data is stored
# Example: /var/lib/docker/volumes/weaviate_data/_data

# Create backup of Weaviate data directory
WEAVIATE_DATA_PATH="/var/lib/docker/volumes/weaviate_data/_data"
BACKUP_DIR="/tmp/weaviate_backups"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/weaviate_data_${BACKUP_DATE}.tar.gz $WEAVIATE_DATA_PATH

# Verify backup
ls -lh $BACKUP_DIR/weaviate_data_${BACKUP_DATE}.tar.gz
```

**Option B: If Weaviate has a backup API (Recommended)**

**On Production Server**:
```bash
# Create backup via Weaviate API
curl -X POST http://localhost:8080/v1/backups/filesystem \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/weaviate-backups",
    "backend": "filesystem"
  }'

# This creates a backup in /weaviate-backups directory inside the container
# Now export that backup
WEAVIATE_CONTAINER=$(docker ps --filter "name=weaviate" -q)

docker cp $WEAVIATE_CONTAINER:/weaviate-backups /tmp/weaviate_backups

# Verify
ls -la /tmp/weaviate_backups/
```

### Step 2.3: Download Weaviate Backup

**On Your Local Machine**:
```bash
# Set variables
PROD_USER="your-prod-username"
PROD_HOST="prod-server.com"
LOCAL_BACKUP_DIR="~/production_data/weaviate"

# Create local directory
mkdir -p $LOCAL_BACKUP_DIR

# Download the backup
scp -r $PROD_USER@$PROD_HOST:/tmp/weaviate_backups $LOCAL_BACKUP_DIR/

# Verify download
ls -lh $LOCAL_BACKUP_DIR/
```

### Step 2.4: Restore Weaviate Locally

**On Your Local Machine**:

**Option A: If using Docker Compose**

```bash
# Stop Weaviate if running
docker-compose stop weaviate

# Remove old data (backup first if concerned)
docker volume rm weaviate_data

# Copy backup data to the correct location
# First, start Weaviate once to create the volume
docker-compose up -d weaviate
sleep 5

# Get the volume path
VOLUME_PATH=$(docker inspect weaviate | grep '"Source"' | grep -o '/var/[^"]*')

# Copy backup data (as root/sudo)
sudo cp -r ~/production_data/weaviate/* $VOLUME_PATH/

# Or if using named volume:
docker run --rm -v weaviate_data:/data -v ~/production_data/weaviate:/backup alpine \
  sh -c 'cp -r /backup/* /data/'

# Restart Weaviate
docker-compose restart weaviate

# Verify Weaviate is running
curl http://localhost:8080/v1/.well-known/ready
```

**Option B: Using Weaviate API to restore**

```bash
# Copy backup files to Docker volume
docker cp ~/production_data/weaviate weaviate:/weaviate-backups

# Inside Weaviate container, restore from backup
curl -X POST http://localhost:8080/v1/backups/filesystem/restore \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/weaviate-backups",
    "backend": "filesystem"
  }'

# Wait for restore to complete
sleep 10

# Verify
curl http://localhost:8080/v1/objects/count
```

### Step 2.5: Verify Weaviate Restore

**On Your Local Machine**:
```bash
# Check if Weaviate is healthy
curl -s http://localhost:8080/v1/.well-known/ready

# Check if data was restored
curl -s http://localhost:8080/v1/objects/count

# You should see a count of objects/classes similar to production
```

---

## Part 3: DMS Folders Sync

### Step 3.1: Check DMS Storage Location

**On Production Server**:
```bash
# Find where DMS files are stored
# Usually in: /var/lib/dms/storage or configured in env

# Check environment variable
grep -i "dms\|storage" .env | grep -i path

# Or check the code
grep -r "STORAGE_PATH\|DMS.*PATH" app/

# Typical location: /data/dms or /var/lib/dms
# List the structure
du -sh /data/dms/
ls -la /data/dms/
```

### Step 3.2: Download DMS Folders

**On Your Local Machine**:
```bash
# Set variables
PROD_USER="your-prod-username"
PROD_HOST="prod-server.com"
PROD_DMS_PATH="/data/dms"  # Or wherever it is on production
LOCAL_DMS_PATH="~/production_data/dms"

# Create local directory
mkdir -p $LOCAL_DMS_PATH

# Download DMS folders (this may take a while for large amounts of data)
scp -r $PROD_USER@$PROD_HOST:$PROD_DMS_PATH/* $LOCAL_DMS_PATH/

# Monitor progress
du -sh $LOCAL_DMS_PATH/
```

### Step 3.3: Configure Local DMS Path

**On Your Local Machine**:
```bash
# Update your .env or configuration
# Set DMS_STORAGE_PATH to point to the local directory

# Edit your .env file
nano .env

# Update or add:
DMS_STORAGE_PATH=~/production_data/dms
# Or absolute path:
# DMS_STORAGE_PATH=/home/username/production_data/dms

# Verify the path
ls -la $DMS_STORAGE_PATH/
```

---

## Part 4: Complete Sync Process (All Together)

Here's a complete script to automate everything:

### 4.1: Production Backup Script

**Create on Production Server**: `backup_for_dev.sh`

```bash
#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_BASE_DIR="/tmp/dev_backup_$(date +%Y%m%d_%H%M%S)"
DB_HOST="<database-host>"
DB_USER="<database-user>"
DB_NAME="ceigall"
DMS_PATH="/data/dms"  # Adjust as needed
WEAVIATE_CONTAINER="weaviate"  # Or container ID

echo -e "${YELLOW}Starting production data backup for dev environment...${NC}"

# Create backup directory
mkdir -p $BACKUP_BASE_DIR

# 1. PostgreSQL Backup
echo -e "${YELLOW}[1/3] Backing up PostgreSQL...${NC}"
pg_dump -h $DB_HOST -U $DB_USER -Fc $DB_NAME > $BACKUP_BASE_DIR/database.dump
gzip $BACKUP_BASE_DIR/database.dump
echo -e "${GREEN}✓ PostgreSQL backup complete${NC}"

# 2. Weaviate Backup
echo -e "${YELLOW}[2/3] Backing up Weaviate...${NC}"
mkdir -p $BACKUP_BASE_DIR/weaviate
docker cp $WEAVIATE_CONTAINER:/weaviate-backups $BACKUP_BASE_DIR/weaviate/ 2>/dev/null || \
  tar -czf $BACKUP_BASE_DIR/weaviate.tar.gz /var/lib/docker/volumes/weaviate_data/_data
echo -e "${GREEN}✓ Weaviate backup complete${NC}"

# 3. DMS Folders
echo -e "${YELLOW}[3/3] Preparing DMS folders...${NC}"
mkdir -p $BACKUP_BASE_DIR/dms
tar -czf $BACKUP_BASE_DIR/dms.tar.gz $DMS_PATH
echo -e "${GREEN}✓ DMS backup complete${NC}"

# Summary
echo -e "${GREEN}Backup complete!${NC}"
echo -e "${YELLOW}Location: $BACKUP_BASE_DIR${NC}"
du -sh $BACKUP_BASE_DIR/

# Provide download instructions
echo -e "${YELLOW}To download on your local machine:${NC}"
echo "scp -r $USER@$(hostname):$BACKUP_BASE_DIR ~/production_backup/"
```

### 4.2: Local Restore Script

**Create on Local Machine**: `restore_from_prod.sh`

```bash
#!/bin/bash

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BACKUP_DIR="$1"  # Pass backup directory as argument
if [ -z "$BACKUP_DIR" ]; then
  echo -e "${RED}Usage: $0 /path/to/backup${NC}"
  exit 1
fi

LOCAL_DB="ceigall_dev"
LOCAL_USER="postgres"
DMS_PATH="~/production_data/dms"

echo -e "${YELLOW}Starting restore from production backup...${NC}"

# 1. Restore PostgreSQL
echo -e "${YELLOW}[1/3] Restoring PostgreSQL...${NC}"
if [ -f "$BACKUP_DIR/database.dump.gz" ]; then
  # Drop existing database (optional, use with caution)
  dropdb -U $LOCAL_USER $LOCAL_DB 2>/dev/null
  createdb -U $LOCAL_USER $LOCAL_DB

  # Restore
  pg_restore -h localhost -U $LOCAL_USER -d $LOCAL_DB \
    --verbose < <(gunzip -c "$BACKUP_DIR/database.dump.gz")
  echo -e "${GREEN}✓ PostgreSQL restore complete${NC}"
else
  echo -e "${RED}✗ Database backup not found${NC}"
fi

# 2. Restore Weaviate
echo -e "${YELLOW}[2/3] Restoring Weaviate...${NC}"
docker-compose stop weaviate 2>/dev/null
if [ -f "$BACKUP_DIR/weaviate.tar.gz" ]; then
  docker volume rm weaviate_data 2>/dev/null
  docker-compose up -d weaviate
  sleep 5

  docker run --rm -v weaviate_data:/data -v $BACKUP_DIR:/backup alpine \
    sh -c 'tar -xzf /backup/weaviate.tar.gz -C /data --strip-components=5'

  docker-compose restart weaviate
  echo -e "${GREEN}✓ Weaviate restore complete${NC}"
else
  echo -e "${RED}✗ Weaviate backup not found${NC}"
fi

# 3. Restore DMS
echo -e "${YELLOW}[3/3] Restoring DMS folders...${NC}"
mkdir -p $DMS_PATH
if [ -f "$BACKUP_DIR/dms.tar.gz" ]; then
  tar -xzf "$BACKUP_DIR/dms.tar.gz" -C $DMS_PATH --strip-components=1
  echo -e "${GREEN}✓ DMS folders restore complete${NC}"
else
  echo -e "${RED}✗ DMS backup not found${NC}"
fi

echo -e "${GREEN}Restore complete!${NC}"
echo -e "${YELLOW}Update your .env file with:${NC}"
echo "DATABASE_URL=postgresql://postgres:password@localhost/ceigall_dev"
echo "DMS_STORAGE_PATH=$DMS_PATH"
```

---

## Part 5: Verification Checklist

After restoring, verify everything works:

### PostgreSQL
```bash
# Connect to local database
psql -h localhost -U postgres -d ceigall_dev

# Check record counts
SELECT COUNT(*) FROM scrape_runs;
SELECT COUNT(*) FROM scraped_tenders;
SELECT COUNT(*) FROM dms_documents;

# Check specific data
SELECT * FROM scrape_runs LIMIT 5;
```

### Weaviate
```bash
# Check health
curl -s http://localhost:8080/v1/.well-known/ready

# Check data count
curl -s http://localhost:8080/v1/objects/count

# List classes
curl -s http://localhost:8080/v1/schema
```

### DMS
```bash
# Check directory structure
ls -la ~/production_data/dms/

# Verify files exist
find ~/production_data/dms -type f | head -20
```

### Application
```bash
# Start your application
python -m app.main  # or however you start it

# Test endpoints
curl http://localhost:8000/api/v1/tenderiq/dates

# Check logs for errors
tail -f logs/app.log
```

---

## Part 6: Storage Space Required

Before starting, ensure you have enough disk space:

```bash
# On Production Server
df -h

# Calculate space needed (get current sizes)
du -sh /var/lib/postgresql/  # PostgreSQL
du -sh /var/lib/docker/volumes/weaviate_data/  # Weaviate
du -sh /data/dms/  # DMS

# Typical requirements:
# PostgreSQL: 1-2x database size
# Weaviate: 50-100% of vector store size
# DMS: File size as-is
# Total: Usually 2-3x total production data size

# On Local Machine
df -h
# Make sure you have space for all backups
```

---

## Part 7: Troubleshooting

### PostgreSQL Issues

**Issue**: `pg_restore: error: could not find block`
```bash
# Solution: Backup may be corrupted, try again:
pg_dump -h $DB_HOST -U $DB_USER --format=plain $DB_NAME > database.sql
# Then restore with:
psql -h localhost -U postgres -d ceigall_dev < database.sql
```

**Issue**: `FATAL: Ident authentication failed`
```bash
# Solution: Check pg_hba.conf for authentication settings
# Update .env with correct connection string or use:
psql -h localhost -U postgres -d ceigall_dev -W  # Prompt for password
```

### Weaviate Issues

**Issue**: `Error: Connection refused on port 8080`
```bash
# Solution: Check if Weaviate is running
docker-compose ps
docker-compose logs weaviate
```

**Issue**: `Error: Backup not found`
```bash
# Solution: Create backup first
curl -X POST http://localhost:8080/v1/backups/filesystem \
  -H "Content-Type: application/json" \
  -d '{"path": "/weaviate-backups", "backend": "filesystem"}'
```

### DMS Issues

**Issue**: `Permission denied when copying files`
```bash
# Solution: Check permissions
ls -la ~/production_data/dms/
chmod -R 755 ~/production_data/dms/
```

---

## Part 8: Keeping Data in Sync

After initial sync, to pull new production data:

```bash
# Simple approach: Just download latest backups again
# Script to run periodically:

#!/bin/bash
BACKUP_DIR="/tmp/prod_backup_latest"
mkdir -p $BACKUP_DIR

# Download latest
scp -r user@prod:/tmp/pg_backups/*.dump.gz $BACKUP_DIR/
scp -r user@prod:/tmp/weaviate_backups $BACKUP_DIR/

# Restore to fresh databases
dropdb -U postgres ceigall_dev
createdb -U postgres ceigall_dev
pg_restore -h localhost -U postgres -d ceigall_dev $BACKUP_DIR/*.dump.gz
```

---

## Quick Reference: All Steps in Order

```bash
# 1. On Production Server
ssh user@prod-server
mkdir -p /tmp/dev_backup
pg_dump -h db-host -U db-user -Fc ceigall | gzip > /tmp/dev_backup/database.dump.gz
docker cp weaviate:/weaviate-backups /tmp/dev_backup/
tar -czf /tmp/dev_backup/dms.tar.gz /data/dms

# 2. On Local Machine
mkdir -p ~/production_data
scp -r user@prod:/tmp/dev_backup ~/production_data/

# 3. Restore locally
dropdb -U postgres ceigall_dev 2>/dev/null
createdb -U postgres ceigall_dev
pg_restore -h localhost -U postgres -d ceigall_dev ~/production_data/database.dump.gz

# 4. Configure .env
echo "DATABASE_URL=postgresql://postgres@localhost/ceigall_dev" >> .env
echo "DMS_STORAGE_PATH=~/production_data/dms" >> .env

# 5. Start app
docker-compose up
```

---

## Summary

You now have:
- ✅ PostgreSQL backup/restore procedure
- ✅ Weaviate backup/restore procedure
- ✅ DMS folders sync via SCP
- ✅ Complete automation scripts
- ✅ Troubleshooting guide
- ✅ Verification checklist

All production data can now be synced to your local development environment!

---

*Last Updated: November 4, 2025*
