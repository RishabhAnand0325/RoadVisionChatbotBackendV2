#!/bin/bash

# Production Data Sync - Quick Start
# This script automates backing up PostgreSQL, Weaviate, and DMS from production
# and restoring them locally

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration - EDIT THESE
PROD_USER="autumn"
PROD_HOST="your-prod-server.com"
PROD_DB_HOST="localhost"  # DB host on prod server
PROD_DB_USER="postgres"
PROD_DB_NAME="ceigall"
PROD_DMS_PATH="/home/autumn/Apache/roadvision/chatbot-backend/tenders"  # Adjust as needed
PROD_WEAVIATE_CONTAINER="weaviate"  # Docker container name

LOCAL_USER="$(whoami)"
LOCAL_DB_NAME="ceigall_dev"
LOCAL_DB_USER="postgres"
LOCAL_DATA_DIR="$HOME/production_data"
LOCAL_DMS_PATH="$LOCAL_DATA_DIR/dms"

# ============================================================================
# STEP 1: BACKUP ON PRODUCTION
# ============================================================================

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         PRODUCTION DATA BACKUP & SYNC                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

echo -e "${YELLOW}Step 1: Creating backups on production server...${NC}"

# Create backup directory on production
PROD_BACKUP_DIR="/tmp/dev_backup_$(date +%Y%m%d_%H%M%S)"

ssh $PROD_USER@$PROD_HOST "
  echo -e '${YELLOW}Creating backup directory...${NC}'
  mkdir -p $PROD_BACKUP_DIR

  echo -e '${YELLOW}[1/3] Backing up PostgreSQL...${NC}'
  pg_dump -h $PROD_DB_HOST -U $PROD_DB_USER -Fc $PROD_DB_NAME > $PROD_BACKUP_DIR/database.dump
  gzip $PROD_BACKUP_DIR/database.dump
  echo -e '${GREEN}✓ PostgreSQL backup complete${NC}'

  echo -e '${YELLOW}[2/3] Backing up Weaviate...${NC}'
  docker cp $PROD_WEAVIATE_CONTAINER:/weaviate-backups $PROD_BACKUP_DIR/weaviate 2>/dev/null || true
  echo -e '${GREEN}✓ Weaviate backup complete${NC}'

  echo -e '${YELLOW}[3/3] Compressing DMS folders...${NC}'
  tar -czf $PROD_BACKUP_DIR/dms.tar.gz $PROD_DMS_PATH
  echo -e '${GREEN}✓ DMS backup complete${NC}'

  echo -e '${YELLOW}Backup location: $PROD_BACKUP_DIR${NC}'
  du -sh $PROD_BACKUP_DIR/
"

# ============================================================================
# STEP 2: DOWNLOAD BACKUPS
# ============================================================================

echo -e "${YELLOW}Step 2: Downloading backups to local machine...${NC}"

mkdir -p $LOCAL_DATA_DIR

# Download all backups
echo -e "${YELLOW}Downloading from $PROD_USER@$PROD_HOST:$PROD_BACKUP_DIR${NC}"
scp -r $PROD_USER@$PROD_HOST:$PROD_BACKUP_DIR/* $LOCAL_DATA_DIR/

echo -e "${GREEN}✓ Download complete${NC}"
echo -e "${YELLOW}Downloaded files:${NC}"
ls -lh $LOCAL_DATA_DIR/

# ============================================================================
# STEP 3: RESTORE POSTGRESQL
# ============================================================================

echo -e "${YELLOW}Step 3: Restoring PostgreSQL locally...${NC}"

# Check if PostgreSQL is running
if ! psql --version &>/dev/null; then
  echo -e "${RED}✗ PostgreSQL client not installed${NC}"
  echo -e "${YELLOW}Install it with: brew install postgresql${NC}"
  exit 1
fi

# Create local database
echo -e "${YELLOW}Creating local database: $LOCAL_DB_NAME${NC}"
dropdb -U $LOCAL_DB_USER $LOCAL_DB_NAME 2>/dev/null || true
createdb -U $LOCAL_DB_USER $LOCAL_DB_NAME

# Find the database backup file
BACKUP_FILE=$(find $LOCAL_DATA_DIR -name "database.dump.gz" -o -name "database.dump" | head -1)

if [ -z "$BACKUP_FILE" ]; then
  echo -e "${RED}✗ Could not find database backup file${NC}"
  exit 1
fi

echo -e "${YELLOW}Restoring from: $BACKUP_FILE${NC}"
pg_restore -h localhost -U $LOCAL_DB_USER -d $LOCAL_DB_NAME --verbose < <(gunzip -c "$BACKUP_FILE") || true

echo -e "${GREEN}✓ PostgreSQL restore complete${NC}"

# Verify
RECORD_COUNT=$(psql -h localhost -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -t -c "SELECT COUNT(*) FROM scrape_runs;")
echo -e "${YELLOW}Verification: Found $RECORD_COUNT scrape runs${NC}"

# ============================================================================
# STEP 4: RESTORE DMS
# ============================================================================

echo -e "${YELLOW}Step 4: Restoring DMS folders...${NC}"

mkdir -p $LOCAL_DMS_PATH

# Find DMS backup
DMS_BACKUP=$(find $LOCAL_DATA_DIR -name "dms.tar.gz" | head -1)

if [ -z "$DMS_BACKUP" ]; then
  echo -e "${RED}✗ Could not find DMS backup file${NC}"
else
  echo -e "${YELLOW}Extracting DMS from: $DMS_BACKUP${NC}"
  tar -xzf "$DMS_BACKUP" -C $LOCAL_DMS_PATH --strip-components=10 2>/dev/null || \
  tar -xzf "$DMS_BACKUP" -C $LOCAL_DMS_PATH

  echo -e "${GREEN}✓ DMS restore complete${NC}"
  echo -e "${YELLOW}DMS location: $LOCAL_DMS_PATH${NC}"
  du -sh $LOCAL_DMS_PATH/
fi

# ============================================================================
# STEP 5: RESTORE WEAVIATE (OPTIONAL)
# ============================================================================

echo -e "${YELLOW}Step 5: Weaviate restore (requires Docker Compose running)...${NC}"

if command -v docker-compose &> /dev/null; then
  echo -e "${YELLOW}Checking if Weaviate container exists...${NC}"

  if docker-compose ps weaviate &>/dev/null 2>&1; then
    echo -e "${YELLOW}Stopping Weaviate...${NC}"
    docker-compose stop weaviate || true

    echo -e "${YELLOW}Removing old Weaviate data...${NC}"
    docker volume rm weaviate_data 2>/dev/null || true

    echo -e "${YELLOW}Starting Weaviate...${NC}"
    docker-compose up -d weaviate
    sleep 5

    WEAVIATE_BACKUP=$(find $LOCAL_DATA_DIR -type d -name "weaviate" | head -1)
    if [ -d "$WEAVIATE_BACKUP" ]; then
      echo -e "${YELLOW}Copying Weaviate backup...${NC}"
      docker cp $WEAVIATE_BACKUP/. weaviate:/weaviate-backups 2>/dev/null || true

      echo -e "${YELLOW}Triggering Weaviate restore...${NC}"
      curl -X POST http://localhost:8080/v1/backups/filesystem/restore \
        -H "Content-Type: application/json" \
        -d '{"path": "/weaviate-backups", "backend": "filesystem"}' 2>/dev/null || true

      sleep 5
      echo -e "${GREEN}✓ Weaviate restore triggered${NC}"
    else
      echo -e "${YELLOW}No Weaviate backup found, skipping${NC}"
    fi
  else
    echo -e "${YELLOW}Weaviate not running in Docker Compose, skipping${NC}"
  fi
else
  echo -e "${YELLOW}Docker Compose not found, skipping Weaviate${NC}"
fi

# ============================================================================
# STEP 6: CONFIGURATION
# ============================================================================

echo -e "${YELLOW}Step 6: Updating local configuration...${NC}"

echo -e "${BLUE}Update your .env file with these values:${NC}"
echo ""
echo -e "${GREEN}DATABASE_URL=postgresql://$LOCAL_DB_USER:password@localhost/$LOCAL_DB_NAME${NC}"
echo -e "${GREEN}DMS_STORAGE_PATH=$LOCAL_DMS_PATH${NC}"
echo ""

echo -e "${YELLOW}Or run these commands to update .env:${NC}"
echo "cd $PWD"
echo "sed -i \"s|DATABASE_URL=.*|DATABASE_URL=postgresql://$LOCAL_DB_USER@localhost/$LOCAL_DB_NAME|g\" .env"
echo "sed -i \"s|DMS_STORAGE_PATH=.*|DMS_STORAGE_PATH=$LOCAL_DMS_PATH|g\" .env"

# ============================================================================
# FINAL SUMMARY
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✓ DATA SYNC COMPLETE!                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

echo -e "${YELLOW}Summary:${NC}"
echo -e "  PostgreSQL Database: ${GREEN}ceigall_dev${NC}"
echo -e "  DMS Storage Path:    ${GREEN}$LOCAL_DMS_PATH${NC}"
echo -e "  Backup Location:     ${YELLOW}$LOCAL_DATA_DIR${NC}"

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Update your .env file (see above)"
echo "  2. Restart your application: docker-compose restart"
echo "  3. Verify with: curl http://localhost:8000/api/v1/tenderiq/dates"

echo ""
echo -e "${YELLOW}To cleanup production backup (optional):${NC}"
echo "  ssh $PROD_USER@$PROD_HOST 'rm -rf $PROD_BACKUP_DIR'"

echo ""
