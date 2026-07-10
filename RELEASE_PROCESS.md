# Finch Release Process

Use this checklist every time you ship production changes.

## 1. Verify the PR

- Check that the PR only contains production changes.
- Confirm there are no secrets, local helper files, or server-only files.
- Make sure the branch is not `main`.

## 2. Merge to `main`

- Merge the PR in GitHub.
- After merge, `main` becomes the deploy target.

## 3. Update the server

On the production server:

```bash
cd ~/finch
git pull origin main
bash ./deploy.sh
```

If you need to target a specific branch for a temporary deploy, pass it explicitly:

```bash
bash ./deploy.sh main
```

The deploy script will:

- fetch the branch
- install Python dependencies
- run migrations
- compile translation files when `msgfmt` is available
- collect static files
- run Django system checks
- restart the `finch` service with `sudo` when available

## 4. Check the server

After deploy:

```bash
sudo systemctl status finch
```

Then verify:

- home page loads
- `/health/` responds
- login works
- static files load
- the feature you changed behaves correctly

## 5. If something fails

- If `compilemessages` fails, install GNU gettext on the server.
- If service restart fails, check sudo access and the `finch` systemd unit.
- If nginx changes are needed, update `/etc/nginx/conf.d/finch.conf` separately and run:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 6. Quick summary
```bash
git pull origin main
bash ./deploy.sh
sudo systemctl status finch
```
