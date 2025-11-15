# Cat Bot Database Migration Guide

## What Changed
Cat instances are now stored in the PostgreSQL database instead of JSON files (`data/cats.json`). This prevents data loss when moving servers.

## Migration Steps

### 1. Apply Database Migration
Run the SQL migration to add the new column using pgAdmin 4:

1. Open **pgAdmin 4**
2. Connect to your PostgreSQL server
3. Navigate to your database in the tree view (left panel)
4. Right-click on your database → Select **Query Tool**
5. In the Query Tool window:
   - Click **File** → **Open** (or press `Ctrl+O`)
   - Navigate to and select `migrations/add_cat_instances.sql`
   - Click **Execute/Run** button (▶️ icon) or press `F5`
6. You should see: "ALTER TABLE" and "CREATE INDEX" messages in the output
7. Verify the column was added:
   ```sql
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name = 'profile' AND column_name = 'cat_instances';
   ```
   You should see one row with `cat_instances | jsonb`

### 2. Migrate Existing Cat Data
**IMPORTANT:** Do this before running the updated bot code!

```bash
python migrate_cats_to_db.py
```

This will:
- Read all cats from `data/cats.json`
- Store them in the database `cat_instances` column
- Create a backup at `data/cats.json.backup`
- Show you a summary of migrated data

### 3. Start the Bot
Once migration is complete, start the bot normally:
```bash
python bot.py
```

## What This Fixes
- ✅ Cats persist when moving bot to new server
- ✅ No more "you don't have any cats" after server transfer
- ✅ Data is part of database backups
- ✅ No manual file copying needed

## Rollback (If Needed)
If you need to go back to JSON storage:
1. Stop the bot
2. Restore your old version of `main.py` and `database.py`
3. Copy `data/cats.json.backup` to `data/cats.json`
4. Start the bot

## Technical Details

### Database Schema
Added column: `cat_instances JSONB DEFAULT '[]'::jsonb`
- Stores array of cat objects with id, type, name, bond, hp, dmg, acquired_at
- GIN index for fast queries
- NULL-safe (defaults to empty array)

### Code Changes
- `get_user_cats()` - Now async, reads from database
- `save_user_cats()` - Now async, writes to database
- `ensure_user_instances()` - Updated to use database storage
- All callers updated to use `await`

## Need Help?
If cats are missing after migration:
1. Check `data/cats.json.backup` exists
2. Re-run `migrate_cats_to_db.py`
3. Check bot console for error messages
