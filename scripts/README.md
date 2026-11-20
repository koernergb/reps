# Scripts

Repository automation that is not naturally expressed as a package command belongs here. Scripts must fail loudly, avoid secrets in output, and have a documented owner/use case.

| Script | Use |
| --- | --- |
| `start-reps.sh` | Day-to-day local launch (`make start`): Docker, Postgres, sandbox, migrate/seed, web+API, browser |
| `backup-db.sh` | Write `backups/reps-<UTC>.dump` |
| `restore-db.sh` | Restore a dump into a named database |
| `verify-restore.sh` | Restore the newest dump into `reps_restore_check` and compare row counts |
