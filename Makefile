.PHONY: up down logs ps backup restore update
up:        ## build + start everything (one-command deploy)
	docker compose up -d --build
update:    ## pull latest git + rebuild + restart
	git pull --ff-only && docker compose up -d --build && docker image prune -f
down:
	docker compose down
logs:
	docker compose logs -f --tail=100
ps:
	docker compose ps
backup:
	./scripts/backup-now.sh
restore:   ## make restore FILE=backups/ledger_....dump
	./scripts/restore.sh $(FILE)
