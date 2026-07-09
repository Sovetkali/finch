# Finch Deployment Checklist

## Before deploy
- Set `DEBUG=False`.
- Set `SECRET_KEY` to a strong secret.
- Set `ALLOWED_HOSTS` to the production domain.
- Set `DATABASE_URL` or keep the SQLite database only for local testing.
- Set `REDIS_URL` if Redis is available.
- Set `DEFAULT_FROM_EMAIL` and mail server credentials if email delivery is needed.

## Server setup
- Install the Python dependencies.
- Create and activate the virtual environment.
- Run database migrations.
- Collect static files into `staticfiles/`.
- Verify the health check at `/health/`.

## Process startup
- Start Django through `gunicorn` using `gunicorn.conf.py`.
- Put `NGINX` in front of the app.
- Make sure `staticfiles/` is served directly by `NGINX`.
- Confirm `X-Forwarded-Proto` is passed through so HTTPS detection works.

## Verification
- Open the home page and confirm the feed loads.
- Check the notification badge updates.
- Confirm login, registration, and comment posting work.
- Run the load-test script once and compare the response times.

## After deploy
- Watch the request logs for slow endpoints.
- Watch the error rate and 500 responses.
- Tune worker count if CPU or memory pressure appears.
