# Finch Cheat Sheet

## Local development

- `local-dev`
- `finch-workflow local-dev`
- `.venv/bin/python scripts/setup_local_dev.py --migrate`
- `.venv/bin/python manage.py runserver`

## Release PR

- `release-pr`
- `finch-workflow release-pr`
- `.venv/bin/python scripts/create_release_pr.py --commit --title "..." --body "..."`
- Responses and progress updates for this skill are in Russian.

## Notes

- Local development uses SQLite when `DATABASE_URL` is not set.
- Release PRs should contain only production-facing changes.
