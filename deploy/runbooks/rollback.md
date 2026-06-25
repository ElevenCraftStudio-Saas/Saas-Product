# Runbook — Rollback Procedures

Layered: app rollback is fast and common; infra rollback is rare and careful.

## A. Application rollback (bad image / bad deploy)
The fastest path. `deploy.sh` records the prior image in
`/opt/wedfind/.deploy-state.prev`.
```bash
sudo deploy/scripts/rollback.sh                 # → previous image
# or pin an explicit known-good tag:
sudo deploy/scripts/rollback.sh <registry>/wedfind-backend:<good-tag>
```
Re-renders `.env`, pulls the target image, restarts, and gates on `/readyz`.
**RTO:** ~1–2 min (image already cached locally if recent).

## B. Bad migration
Migrations run via `alembic upgrade head` in the api start command. If a release
ships a broken migration:
1. Roll the app back to the previous image (A). If that image's code is
   compatible with the **already-applied** schema, you're done.
2. If the schema itself must move back:
   ```bash
   $C exec -T api alembic downgrade -1     # step back one revision
   ```
   Only downgrade if the migration has a tested `down_revision` path. Prefer a
   forward-fix migration for data-bearing changes.
3. If data is at risk, restore from RDS (D) into a new instance and re-point
   `DATABASE_URL`.

## C. Bad secret / credential
```bash
# Restore the previous secret version to AWSCURRENT, then redeploy:
aws secretsmanager list-secret-version-ids --secret-id wedfind-<env>/app --region <region>
aws secretsmanager update-secret-version-stage --secret-id wedfind-<env>/app \
  --version-stage AWSCURRENT --move-to-version-id <PREV> --remove-from-version-id <BAD> --region <region>
sudo deploy/scripts/deploy.sh <current-image>
```
(See secrets-manager.md / firebase-key-rotation.md.)

## D. Database restore (data loss / corruption)
Automated backups retain `db_backup_retention_days` (default 7). Point-in-time
restore creates a NEW instance — it never overwrites the live one.
```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier wedfind-<env>-pg \
  --target-db-instance-identifier wedfind-<env>-pg-restore \
  --restore-time 2026-06-25T10:00:00Z \
  --db-subnet-group-name wedfind-<env>-db-subnets \
  --vpc-security-group-ids <rds-sg-id> --no-publicly-accessible --region <region>
```
Then update `DATABASE_URL` in the secret to the restored endpoint and `deploy.sh`.
Decommission the old instance once verified.

## E. Full infra rollback (Terraform)
For a bad infra change, prefer `terraform plan` + targeted revert over destroy.
```bash
git revert <bad-commit>           # revert the IaC change
terraform plan                    # review — confirm no destroy of RDS/S3
terraform apply
```
**Guards:** RDS has `deletion_protection` in prod and `skip_final_snapshot=false`;
S3 has versioning. Never `terraform destroy` an environment with live data — to
tear down staging intentionally, snapshot RDS + sync S3 elsewhere first.

## Decision guide
| Symptom | Action |
|---|---|
| 5xx after deploy, schema unchanged | A (app rollback) |
| 5xx after deploy, migration shipped | A, then B if needed |
| Auth/Firestore broken after key change | C (secret restore) |
| Data corrupted/deleted | D (PITR restore) |
| Networking/SG/infra mistake | E (revert IaC) |
