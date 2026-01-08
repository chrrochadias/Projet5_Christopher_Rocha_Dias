# Projet 5 — Migration de données médicales vers MongoDB (Docker & AWS-ready)

## 🎯 Contexte de la mission

Dans le cadre de ma mission de stagiaire Data Engineer chez **DataSoluTech**, j’ai été chargé de concevoir une solution permettant la **migration d’un dataset de données médicales de patients vers MongoDB**, dans un contexte de **scalabilité horizontale** et de **préparation au déploiement cloud (AWS)**.

Le client rencontrait des limitations avec une architecture traditionnelle et souhaitait une solution :
- scalable,
- reproductible,
- sécurisée,
- et facilement déployable dans un environnement cloud.

---

## 🧠 Objectifs du projet

- Automatiser la migration d’un dataset médical (CSV / JSON) vers MongoDB
- Conteneuriser l’ensemble avec Docker
- Garantir une migration **idempotente** (relançable sans doublons)
- Mettre en place une authentification MongoDB avec rôles
- Documenter l’architecture, le schéma et les choix techniques
- Préparer la solution pour un futur déploiement sur AWS

## 🧱 Architecture globale

├── docker-compose.yml
├── Makefile
├── .env.example
├── mongo/
│ └── init-mongo.js
├── migrator/
│ ├── Dockerfile
│ ├── requirements.txt
│ ├── migrate.py
│ └── wait_for_mongo.py
├── data/
│ └── dataset.csv
└── README.md

### Services Docker
- **mongodb** : base MongoDB avec authentification activée
- **migrator** : service Python chargé de la migration des données

---

## 🔐 Sécurité & authentification

Trois types d’utilisateurs MongoDB sont créés automatiquement au démarrage :

| Utilisateur | Rôle | Usage |
|------------|-----|------|
| `root` | admin | maintenance |
| `app_ingest` | readWrite | ingestion des données |
| `app_readonly` | read | consultation / BI |

Les credentials sont fournis via variables d’environnement (non versionnées).

---

## 🗄️ Modèle de données MongoDB

### Base
- **Database** : `medical`
- **Collection** : `patients`

### Clé métier
- `patient_id` (hash SHA256 basé sur le nom + date d’admission)

### Exemple de document

```json
{
  "patient_id": "f4b8c3...",
  "name": {
    "full": "Leslie Terry",
    "normalized": "leslie terry"
  },
  "age": 62,
  "gender": "Male",
  "blood_type": "A+",
  "medical_condition": "Obesity",
  "admission": {
    "type": "Emergency",
    "date": "2019-08-20",
    "discharge_date": "2019-08-26",
    "room_number": 265
  },
  "doctor": "Samantha Davies",
  "hospital": "Kim Inc",
  "insurance_provider": "Medicare",
  "billing_amount": 33643.33,
  "medication": "Ibuprofen",
  "test_results": "Inconclusive",
  "created_at": "2026-01-05T20:40:00Z",
  "updated_at": "2026-01-05T20:40:00Z"
}