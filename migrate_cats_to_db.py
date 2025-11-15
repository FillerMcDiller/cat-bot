"""
Migration script to move cat instances from JSON files to PostgreSQL database.
This ensures no data loss when switching from JSON storage to database storage.
"""

import asyncio
import json
import os
import catpg
from database import Profile
import config

CATS_DB_PATH = "data/cats.json"

async def migrate_cats_to_database():
    """Read all cats from JSON and store them in the database."""
    
    # Initialize database connection
    print("🔌 Connecting to database...")
    try:
        await catpg.connect(user="cat_bot", password=config.DB_PASS, database="cat_bot", host="127.0.0.1", max_size=10)
        print("✅ Database connected")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return
    
    # Check if JSON file exists
    if not os.path.exists(CATS_DB_PATH):
        print(f"❌ No cats.json file found at {CATS_DB_PATH}")
        print("   If this is a fresh install, this is normal.")
        return
    
    # Load JSON data
    try:
        with open(CATS_DB_PATH, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading cats.json: {e}")
        return
    
    if not json_data:
        print("ℹ️  cats.json is empty, nothing to migrate.")
        return
    
    print(f"📦 Found cats.json with {len(json_data)} guild(s)")
    
    total_users = 0
    total_cats = 0
    migrated_users = 0
    
    # Process each guild
    for guild_id_str, users in json_data.items():
        guild_id = int(guild_id_str)
        
        # Process each user in the guild
        for user_id_str, cats_list in users.items():
            user_id = int(user_id_str)
            total_users += 1
            
            if not cats_list:
                continue
            
            total_cats += len(cats_list)
            
            try:
                # Get or create profile
                profile = await Profile.get_or_create(guild_id=guild_id, user_id=user_id)
                
                # Store cat instances in database as JSON string
                # catpg will handle converting it to JSONB
                profile.cat_instances = json.dumps(cats_list)
                await profile.save()
                
                migrated_users += 1
                print(f"✅ Migrated {len(cats_list)} cats for user {user_id} in guild {guild_id}")
                
            except Exception as e:
                print(f"❌ Error migrating user {user_id} in guild {guild_id}: {e}")
    
    print("\n" + "="*60)
    print("📊 Migration Summary:")
    print(f"   Total guilds processed: {len(json_data)}")
    print(f"   Total users found: {total_users}")
    print(f"   Users successfully migrated: {migrated_users}")
    print(f"   Total cats migrated: {total_cats}")
    print("="*60)
    
    # Create backup of JSON file
    backup_path = CATS_DB_PATH + ".backup"
    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Backup created at: {backup_path}")
    except Exception as e:
        print(f"\n⚠️  Warning: Could not create backup: {e}")
    
    print("\n✨ Migration complete! You can now safely use database storage.")
    
    # Close database connection
    try:
        await catpg.close()
        print("🔌 Database connection closed")
    except Exception:
        pass

if __name__ == "__main__":
    print("🚀 Starting cat instances migration from JSON to PostgreSQL...")
    print()
    asyncio.run(migrate_cats_to_database())
