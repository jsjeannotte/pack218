#!/bin/bash
timestamp=$(date +%Y%m%d_%H%M%S)
tar -czf "database_backup_${timestamp}.tgz" database.db database.db-shm database.db-wal
echo "Backup created: database_backup_${timestamp}.tgz"
