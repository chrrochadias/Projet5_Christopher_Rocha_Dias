# Makefile — Projet Mongo migration

ifneq (,$(wildcard .env))
	include .env
	export
endif


SHELL := /bin/bash

COMPOSE := docker compose
MONGO_SERVICE := mongodb
MIGRATOR_SERVICE := script

.DEFAULT_GOAL := help

help: ## Affiche l'aide
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*##/ \t /'

check-env: ## Vérifie que le fichier .env existe
	@test -f .env || (echo "❌ .env manquant. Fais: cp .env.example .env" && exit 1)
	@echo "✅ .env OK"

ps: ## Liste les conteneurs
	@$(COMPOSE) ps

build: check-env ## Build des images
	@$(COMPOSE) build

up: check-env ## Démarre tout (Mongo + migrator)
	@$(COMPOSE) up --build

up-d: check-env ## Démarre tout en arrière-plan
	@$(COMPOSE) up -d --build

down: ## Stoppe et supprime les conteneurs (garde les volumes)
	@$(COMPOSE) down

reset: ## Reset complet (⚠️ supprime volumes => ré-exécute init-mongo.js)
	@$(COMPOSE) down -v
	@$(COMPOSE) up -d --build
	@echo "✅ Reset complet terminé"

logs: ## Logs de tous les services
	@$(COMPOSE) logs -f

logs-mongo: ## Logs Mongo uniquement
	@$(COMPOSE) logs -f $(MONGO_SERVICE)

logs-migrator: ## Logs migrator uniquement
	@$(COMPOSE) logs -f $(MIGRATOR_SERVICE)

migrate: check-env ## Lance la migration (run éphémère)
	@$(COMPOSE) run --rm $(MIGRATOR_SERVICE) bash -lc "python wait_for_mongo.py --timeout 60 && python migrate.py"

verify: check-env ## Vérifie qu'il y a des données (COLL=patients MIN=1)
	@COLL=$${COLL:-patients}; MIN=$${MIN:-1}; \
	$(COMPOSE) run --rm $(MIGRATOR_SERVICE) python wait_for_mongo.py --check-data --collection $$COLL --min-docs $$MIN --timeout 60

mongo-shell: check-env ## Ouvre mongosh root (admin)
	@$(COMPOSE) exec $(MONGO_SERVICE) mongosh -u $$MONGO_ROOT_USER -p $$MONGO_ROOT_PASSWORD --authenticationDatabase admin

count: check-env ## Compte les docs (COLL=patients par défaut)
	@COLL=$${COLL:-patients}; \
	$(COMPOSE) exec $(MONGO_SERVICE) mongosh -u $$MONGO_ROOT_USER -p $$MONGO_ROOT_PASSWORD --authenticationDatabase admin --quiet --eval "\
	const dbName='$$MONGO_DB'; \
	const collName='$$COLL'; \
	const c=db.getSiblingDB(dbName).getCollection(collName).countDocuments(); \
	print('db=' + dbName + ' coll=' + collName + ' count=' + c);"