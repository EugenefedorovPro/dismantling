# Dismantling production deployment (kant VPS)

The workflow `.github/workflows/deploy.yml` checks Django, runs tests, then
deploys a successful push to `main` over SSH to `kant@176.117.78.212`.
Pull requests to `main` run tests but never deploy. The workflow does not
deploy until it has been merged into `main` and the setup below is completed.

## 1. Prepare the VPS once

Install Docker Engine, the Docker Compose plugin, and Python 3 if needed.
The `kant` account must be able to run `docker compose` without a password
prompt. Docker group membership effectively grants root access, so protect
the deploy key and the repository's `main` branch accordingly.

The GitHub repository is public, so the VPS can clone it read-only via HTTPS:

```sh
sudo install -d -o kant -g kant /opt/apps/dismantling
git clone https://github.com/EugenefedorovPro/dismantling.git /opt/apps/dismantling
cd /opt/apps/dismantling
cp .env.example .env
chmod 600 .env
```

Edit `/opt/apps/dismantling/.env` so it contains these **production** values:

```dotenv
WEB_PORT=8088
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_SECRET
DJANGO_ALLOWED_HOSTS=dismantle.rhyme.kyiv.ua,127.0.0.1,localhost
DJANGO_TRUST_PROXY_SSL_HEADER=1
```

Generate a secret locally using `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'`.
Never commit `.env`, share the secret in chat, or put it in the workflow.
The workflow deliberately refuses to deploy without `.env` and
`DJANGO_DEBUG=0`.

Production binds `127.0.0.1:8088` and uses the host database at
`/opt/apps/dismantling/data/db.sqlite3`. The deploy workflow selects
`deploy/compose.production.yaml` explicitly. Use it with the base file for
production Compose commands. The base file on its own uses a named volume for
local development.

For an existing deployment, verify the running container's mount before merging
the workflow. The command below reads the current mount without restarting it.

```sh
docker inspect "$(docker compose ps -q web)" \
  --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Type}} {{.Source}}{{end}}{{end}}'
```

The expected result is `bind /opt/apps/dismantling/data`. If the running app
uses a named volume, make a verified SQLite backup from that app and migrate the
current database to the bind mount before deploying. The workflow checks the
existing container's mount and stops when it differs.

On a new site with no database to preserve, initialize SQLite once from a
checkout containing the production override.

```sh
mkdir -p data
docker compose -f docker-compose.yaml -f deploy/compose.production.yaml build web
docker compose -f docker-compose.yaml -f deploy/compose.production.yaml \
  run --rm --no-deps web python manage.py migrate --noinput
```

## 2. Configure Cloudflare and Nginx

In the Cloudflare DNS zone `rhyme.kyiv.ua`, add:

| Type | Name | IPv4 address | Proxy | TTL |
| --- | --- | --- | --- | --- |
| A | dismantle | 176.117.78.212 | Proxied | Auto |

Create a dedicated Nginx site for the hostname using
`deploy/nginx-dismantle.conf.example` as a reference, leaving the existing
`myconfig.conf` and other sites intact. The example requires a valid origin
certificate for `dismantle.rhyme.kyiv.ua`. Check whether your existing
Cloudflare Origin CA certificate is a wildcard covering that hostname;
otherwise issue a new one. Use Cloudflare SSL/TLS **Full (strict)** once the
origin certificate is ready. Be aware that changing the SSL mode for the
entire Cloudflare zone can affect `rhyme.kyiv.ua` too.

After configuring the new site, test and reload Nginx:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

## 3. Configure a dedicated deployment SSH key

On your **local trusted computer**, create a key just for this workflow:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/dismantling_github_actions -C dismantling-github-actions
ssh-copy-id -i ~/.ssh/dismantling_github_actions.pub kant@176.117.78.212
```

Choose an empty passphrase for this CI-only key. Restrict the key to this
deployment account and never reuse a personal SSH key in GitHub Actions.
Confirm SSH access with:

```sh
ssh -i ~/.ssh/dismantling_github_actions kant@176.117.78.212 true
```

On the **VPS**, print its SSH host public key as a `known_hosts` entry:

```sh
sudo awk '{ print "176.117.78.212 " $1 " " $2 }' /etc/ssh/ssh_host_ed25519_key.pub
```

Verify that the host key fingerprint matches a previously trusted SSH
connection. Do not use an unverified `ssh-keyscan` result as your trusted key.

On GitHub go to **Settings → Environments → New environment**, create
`production`, and add these environment secrets:

| Secret | Value |
| --- | --- |
| `DEPLOY_SSH_PRIVATE_KEY` | Entire content of the local `~/.ssh/dismantling_github_actions` private key |
| `DEPLOY_SSH_KNOWN_HOSTS` | Entire `176.117.78.212 ssh-ed25519 AAAA...` line printed on the VPS |

Restrict the `production` environment to `main` if desired. Protect
`main` with pull request reviews: any change merged to `main` will trigger a
deployment and will execute code on your server.

## 4. Initial deployment and ongoing updates

After the workflow has been merged into `main`, every push to `main`
automatically:

1. Installs Python dependencies and runs Django checks and tests on GitHub.
2. Connects to the VPS over SSH (strict host-key checking).
3. Verifies the run's tested SHA against the current GitHub `main` and builds
   from an archive of that exact commit.
4. Verifies the SQLite mount, saves a database snapshot, and starts the candidate
   image. Admin edits are paused while Compose checks the new container.
5. If startup fails, restores the database snapshot and starts the previous image.

The server's Git working tree is independent of the release. Update it with
`git pull --ff-only` when you need current configuration files for manual
maintenance.

GitHub reports a failed release even when rollback succeeds. If the release is
interrupted and `data/.deploy-backup.sqlite3` remains, the next deploy stops
before changing the service. Check the running image and the saved database
before clearing the interrupted deployment state.

Watch the result under **GitHub → Actions → Test and deploy Dismantling**.
The Django site should be accessible at `https://dismantle.rhyme.kyiv.ua/`.

If you need to create an Admin user after the first deployment:

```sh
cd /opt/apps/dismantling
docker compose -f docker-compose.yaml -f deploy/compose.production.yaml \
  exec web python manage.py createsuperuser
```

Run `docker compose logs -f web` on the VPS to investigate application errors.
