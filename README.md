
#  ![Discord Bots](https://top.gg/api/widget/servers/1387305159264309399.svg)
=======
# cat-botmcdiller
KITTAYYYYYYY!

Discord bot centered around catching cats.
fun!

Credits to milenakos for the source code <3

Run locally with `python bot.py`, or use `bash run.sh` if you want a launcher that restarts the process after a crash.

## Database setup

The bot needs PostgreSQL before it can start. Create a database and role, then put the connection values in `.env`:

```env
DB_USER=cat_bot
DB_PASSWORD=your-postgres-password
DB_NAME=cat_bot
DB_HOST=127.0.0.1
DB_PORT=5432
```

Alternatively, set `DATABASE_URL` to a PostgreSQL connection string. It takes precedence over the individual `DB_*` settings. Apply `schema.sql` to the database before the first run.
