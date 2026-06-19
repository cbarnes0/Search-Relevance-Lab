# Deployment (single VM)

How the live instance at <https://search.search-relevance-lab.com> is deployed. The whole stack runs on one small VM via [`docker-compose.prod.yml`](docker-compose.prod.yml), a **self-contained** production compose file (run on its own, **not** merged with the dev `docker-compose.yml`). It differs from the dev stack in a few deliberate ways:

- **No source bind-mounts** — the built images are what run (`web` uses [`apps/web/Dockerfile.prod`](apps/web/Dockerfile.prod), a multi-stage standalone Next.js build; `api` runs `uvicorn` without `--reload`).
- **Datastores are not published to the host** — Postgres/Typesense/Qdrant are reachable only on the internal Docker network.
- **[Caddy](docker/caddy/Caddyfile) sits in front** of `web` as the only service exposing ports (80/443) and terminates TLS with automatic HTTPS.

## Prerequisites

- A VM (2 vCPU / 4 GB RAM is sufficient for NFCorpus) running a recent Linux with Docker + the Compose plugin.
- Inbound firewall open to **22, 80, 443** only.
- A DNS `A` record pointing your hostname at the VM's IP (needed for automatic HTTPS).

## Steps

```bash
# 1. Clone and create the data dir (./data is gitignored)
git clone <repo-url> Search-Relevance-Lab && cd Search-Relevance-Lab
mkdir -p data

# 2. Copy the host-downloaded caches up from your machine (the API/indexer run
#    HF_HUB_OFFLINE=1 and load the model from disk — they never download):
#    scp -r ./data/hf_cache ./data/ir_datasets <user>@<host>:~/Search-Relevance-Lab/data/

# 3. Configure secrets/host (no secrets are committed — .env is gitignored)
cp .env.example .env
#   set POSTGRES_PASSWORD and TYPESENSE_API_KEY to strong random values
#     (generate with: openssl rand -hex 24)
#   set SITE_ADDRESS=your-domain.com  (or :80 to serve plain HTTP without a domain)

# 4. Build and start the stack
docker compose -f docker-compose.prod.yml config >/dev/null   # validate
docker compose -f docker-compose.prod.yml up -d --build

# 5. Populate the datastores once (indexer is a one-shot under the `tools` profile)
docker compose -f docker-compose.prod.yml --profile tools run --rm indexer python ingest.py
docker compose -f docker-compose.prod.yml --profile tools run --rm indexer python index_lexical.py
docker compose -f docker-compose.prod.yml --profile tools run --rm indexer python index_vector.py
```

Open `https://your-domain.com` (Caddy fetches a certificate on first request).

## Eval runs in production

The eval harness writes to Postgres and is built for the dev stack, so the deployed `/runs` pages need that data in the production database. Either point the harness at the prod stack, or migrate runs you've already computed by dumping the two eval tables from dev and restoring them:

```bash
# on the dev host (use a UTF-8 shell — PowerShell's > redirection writes UTF-16)
docker compose exec -T postgres pg_dump -U <user> -d <db> -t eval_runs -t eval_results > eval_dump.sql
# on the server
docker compose -f docker-compose.prod.yml exec -T postgres psql -U <user> -d <db> < eval_dump.sql
```

## Backups

[`scripts/backup-postgres.sh`](scripts/backup-postgres.sh) dumps the database to a timestamped, gzipped file under `./backups/` and prunes dumps older than 14 days. Schedule it from cron:

```cron
30 3 * * * /home/<user>/Search-Relevance-Lab/scripts/backup-postgres.sh >> /home/<user>/Search-Relevance-Lab/backups/backup.log 2>&1
```
