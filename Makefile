# Makefile — Projet Mongo migration
SHELL := /bin/bash

COMPOSE := docker compose
MONGO_SERVICE := mongodb
MIGRATOR_SERVICE := migrator

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
	@$(COMPOSE) logs -f $(MIGRATOR_SERVICE)_
