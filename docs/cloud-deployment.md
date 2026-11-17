# Cloud trial deployment (not production)

This guide is for a **specific Linux cloud machine you control**. It does not mean that a cloud machine has been connected or deployed from ChatGPT. Do not deploy on an unconfirmed host.

## Requirements

- Linux cloud VM with permission to install/use Docker Engine and Docker Compose v2; Git and curl installed.
- At least 2 vCPU, 2 GiB RAM, and 10 GiB free storage **as a suggested evaluation capacity, not an official minimum**.
- Access to the VM's own terminal or an authorized SSH session.
- Do not use customer data; the repository is public and the app is a local trial with one shared API key.

## Launch on the target VM

```bash
git clone https://github.com/slotmagia/stone-seo-growth.git
cd stone-seo-growth
bash deploy/cloud.sh up
bash deploy/cloud.sh status
```

The script creates `.env` if absent, containing randomly generated `ADMIN_API_KEY` and `POSTGRES_PASSWORD` (neither is printed), validates secret format, starts PostgreSQL and API using `compose.yaml`, and checks **the VM's own** `http://127.0.0.1:8000/health` endpoint. It never publicly exposes port 8000. Store `.env` securely; do not commit it or transmit it via chat. If `.env` already exists it is not overwritten. Database data is in a named Docker volume. To stop without deleting the volume: `bash deploy/cloud.sh stop`.

Run `docker compose -f compose.yaml ps` and `docker compose -f compose.yaml logs --tail=100 api` *on the VM* for troubleshooting; inspect logs before sharing, as they may contain sensitive operator data.

## View from your own laptop

Forward traffic through your trusted SSH connection (replace placeholders with the actual account/host supplied by your operator):

```bash
ssh -N -L 8000:127.0.0.1:8000 YOUR_USER@YOUR_CLOUD_HOST
```

In your local browser open `http://127.0.0.1:8000/` or `/docs`. The application requires the `X-API-Key` header on `/api/v1/*`, using the secret stored in `.env` **on the VM**. Do not expose it in shell history, logs, screenshots or Git.

## Limitations and next gates

- API startup runs `alembic upgrade head` against PostgreSQL before serving. **Back up the database before upgrading a running instance.** Existing legacy field mirrors remain stored but require re-verification as ProductFact v2; never treat old `verified_fields` as trusted current facts. The initial baseline migration intentionally refuses destructive downgrade.
- PostgreSQL migrations have not yet been exercised against a real target PostgreSQL server in this session. Test a backup-restored staging database before production use.
- Shared API key is not per-user authentication; there is no RBAC/SSO, rate limiting, HTTPS termination, or automatic backups. Keep the web port bound to loopback; no public deployment yet.
- External CMS, Baidu, Douyin, marketplace and search APIs are not connected. `site_audit` evaluates supplied page metadata only.
- Before deploying into long-lived use: exercise and verify PostgreSQL migrations, encrypted backups and restore drills, SSO/RBAC, reverse proxy with HTTPS, monitoring, secret rotation and DNS/asset authorization.
- On future upgrades use `git pull --ff-only` and **review schema changes and backup strategy first**; blindly rebuilding on live data is not a safe upgrade policy.
