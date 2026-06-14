# AgentFlow — Backend API

Plateforme d'agents IA métiers avec système RAG configurable, authentification JWT, gestion multi-tenant et architecture multi-agents.

## Stack technique

- **Framework** : FastAPI (Python 3.11+)
- **Base de données** : PostgreSQL + pgvector
- **ORM** : SQLAlchemy 2.0 + Alembic (migrations)
- **Auth** : JWT (HS256) + bcrypt + cookies HttpOnly
- **Email** : FastMail (SMTP)
- **Embeddings** : sentence-transformers (BGE-M3 / BGE-base / MiniLM)
- **LLM** : Groq API (Llama 3.3 70B Versatile)
- **PDF** : pdfplumber + PyPDF2

---  
## Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Prérequis

- Python 3.11+
- PostgreSQL 15+ avec l'extension pgvector installée
- Un compte Groq (gratuit) pour la clé API LLM

### Activer pgvector dans PostgreSQL

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---
## Lancement

```bash
uvicorn app.main:app --reload
```

- API : http://localhost:8000
- Documentation Swagger : http://localhost:8000/docs
- Documentation ReDoc : http://localhost:8000/redoc

---

## Structure du projet

```
backend/
├── app/
│   ├── main.py                 # Point d'entrée FastAPI, CORS, routeurs
│   ├── config.py               # Settings depuis .env (Pydantic)
│   ├── database.py             # Connexion PostgreSQL, session SQLAlchemy
│   │
│   ├── models/                 # Modèles SQLAlchemy (tables)
│   │   ├── __init__.py         # Imports centralisés
│   │   ├── organization.py     # Organization (PERSONAL / BUSINESS)
│   │   ├── department.py       # Department (RH, Finance, Support...)
│   │   ├── user.py             # User (ADMIN / IT / USER)
│   │   ├── rag_space.py        # RAGSpace (config du pipeline)
│   │   ├── document.py         # Document (fichiers uploadés)
│   │   └── chunk.py            # Chunk (morceaux + embeddings pgvector)
│   │
│   ├── schemas/                # Schémas Pydantic (validation)
│   │   ├── auth.py             # Register, Login, ForgotPassword, OTP
│   │   ├── user.py             # Invite, Activate, UpdateRole, Department
│   │   └── rag.py              # CreateRAGSpace, Query, ChunkStrategy
│   │
│   ├── routes/                 # Endpoints API (routeurs FastAPI)
│   │   ├── auth.py             # /api/auth/*
│   │   ├── users.py            # /api/users/*
│   │   └── rag.py              # /api/rag/*
│   │
│   └── services/               # Logique métier
│       ├── auth_service.py     # Register, login, JWT, OTP, rate limiting
│       ├── user_service.py     # Invite, activate, CRUD users, departments
│       └── rag_service.py      # Pipeline RAG complet
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

---

## Modèles de données

### Organization

| Champ      | Type     | Description           |
| ---------- | -------- | --------------------- |
| id         | UUID     | Clé primaire          |
| name       | String   | Nom de l'organisation |
| type       | Enum     | PERSONAL ou BUSINESS  |
| created_at | DateTime | Date de création      |

### User

| Champ           | Type   | Description                                 |
| --------------- | ------ | ------------------------------------------- |
| id              | UUID   | Clé primaire                                |
| name            | String | Nom complet (null si invitation en attente) |
| email           | String | Email unique, indexé                        |
| password_hash   | String | Haché avec bcrypt (tronqué à 72 bytes)      |
| role            | Enum   | ADMIN, IT ou USER                           |
| status          | Enum   | ACTIVE ou PENDING                           |
| invite_token    | String | Token d'invitation (null si activé)         |
| organization_id | FK     | Lien vers Organization                      |
| department_id   | FK     | Lien vers Department (optionnel)            |

### Department

| Champ           | Type   | Description                         |
| --------------- | ------ | ----------------------------------- |
| id              | UUID   | Clé primaire                        |
| name            | String | Nom du département (RH, Finance...) |
| organization_id | FK     | Lien vers Organization              |

### RAGSpace

| Champ           | Type    | Description                     |
| --------------- | ------- | ------------------------------- |
| id              | UUID    | Clé primaire                    |
| name            | String  | Nom de l'espace RAG             |
| description     | String  | Description                     |
| organization_id | FK      | Lien vers Organization          |
| chunk_size      | Integer | Taille des chunks (défaut: 512) |
| chunk_overlap   | Integer | Chevauchement (défaut: 50)      |
| top_k           | Integer | Nombre de résultats (défaut: 5) |
| chunk_strategy  | Enum    | FIXED, SEMANTIC ou HIERARCHICAL |

### Document

| Champ        | Type    | Description                         |
| ------------ | ------- | ----------------------------------- |
| id           | UUID    | Clé primaire                        |
| file_name    | String  | Nom du fichier original             |
| file_type    | String  | Type (pdf, docx, csv...)            |
| file_size    | Integer | Taille en bytes                     |
| num_chunks   | Integer | Nombre de chunks générés            |
| status       | Enum    | PENDING, INDEXING, INDEXED ou ERROR |
| error_msg    | Text    | Message d'erreur si échec           |
| rag_space_id | FK      | Lien vers RAGSpace                  |

### Chunk

| Champ        | Type         | Description                        |
| ------------ | ------------ | ---------------------------------- |
| id           | UUID         | Clé primaire                       |
| content      | Text         | Texte du chunk                     |
| embedding    | Vector(1024) | Vecteur pgvector (1024 dimensions) |
| page         | Integer      | Numéro de page source              |
| type         | String       | "text" ou "table"                  |
| document_id  | FK           | Lien vers Document                 |
| rag_space_id | FK           | Lien vers RAGSpace                 |

---

## API Endpoints

### Authentification — `/api/auth`

| Méthode | URL                         | Description                                 | Auth |
| ------- | --------------------------- | ------------------------------------------- | ---- |
| POST    | `/api/auth/register`        | Inscription + création de l'organisation    | Non  |
| POST    | `/api/auth/login`           | Connexion (retourne JWT en cookie HttpOnly) | Non  |
| POST    | `/api/auth/logout`          | Déconnexion (supprime le cookie)            | Oui  |
| GET     | `/api/auth/me`              | Profil de l'utilisateur connecté            | Oui  |
| POST    | `/api/auth/forgot-password` | Envoi d'un OTP 6 chiffres par email         | Non  |
| POST    | `/api/auth/verify-otp`      | Vérification de l'OTP                       | Non  |
| POST    | `/api/auth/reset-password`  | Réinitialisation du mot de passe            | Non  |

### Utilisateurs — `/api/users`

| Méthode | URL                           | Description                                     | Auth  |
| ------- | ----------------------------- | ----------------------------------------------- | ----- |
| GET     | `/api/users/`                 | Lister tous les utilisateurs de l'organisation  | Oui   |
| POST    | `/api/users/invite`           | Inviter un utilisateur par email                | Admin |
| POST    | `/api/users/activate`         | Activer un compte invité (token + mot de passe) | Non   |
| PUT     | `/api/users/{user_id}`        | Modifier le rôle d'un utilisateur               | Admin |
| DELETE  | `/api/users/{user_id}`        | Supprimer un utilisateur                        | Admin |
| POST    | `/api/users/{user_id}/resend` | Renvoyer l'invitation                           | Admin |

### Départements — `/api/users/departments`

| Méthode | URL                                | Description              | Auth |
| ------- | ---------------------------------- | ------------------------ | ---- |
| GET     | `/api/users/departments`           | Lister les départements  | Oui  |
| POST    | `/api/users/departments`           | Créer un département     | Oui  |
| DELETE  | `/api/users/departments/{dept_id}` | Supprimer un département | Oui  |

### RAG — `/api/rag`

| Méthode | URL                                       | Description                                    | Auth |
| ------- | ----------------------------------------- | ---------------------------------------------- | ---- |
| POST    | `/api/rag/spaces`                         | Créer un espace RAG                            | Oui  |
| GET     | `/api/rag/spaces`                         | Lister les espaces RAG                         | Oui  |
| GET     | `/api/rag/spaces/{id}`                    | Détail d'un espace RAG                         | Oui  |
| PUT     | `/api/rag/spaces/{id}`                    | Modifier un espace RAG                         | Oui  |
| DELETE  | `/api/rag/spaces/{id}`                    | Supprimer un espace RAG (+ documents + chunks) | Oui  |
| POST    | `/api/rag/spaces/{id}/upload`             | Uploader un document (PDF)                     | Oui  |
| GET     | `/api/rag/spaces/{id}/documents`          | Lister les documents d'un espace               | Oui  |
| DELETE  | `/api/rag/spaces/{id}/documents/{doc_id}` | Supprimer un document                          | Oui  |
| POST    | `/api/rag/spaces/{id}/query`              | Poser une question au RAG                      | Oui  |

---

## Pipeline RAG

Le pipeline s'exécute en deux phases :

### Phase d'indexation (à l'upload d'un document)

1. **Extraction** — pdfplumber extrait le texte et les tableaux du PDF. Trois méthodes de détection de tableaux sont essayées (bordures visibles, texte, colonnes). Les tableaux sont convertis en Markdown.

2. **Chunking** — Le texte extrait est découpé en morceaux via `RecursiveCharacterTextSplitter` de LangChain. La taille (`chunk_size`) et le chevauchement (`chunk_overlap`) sont configurables par espace. Les tableaux sont gardés intacts (jamais découpés).

3. **Embedding** — Chaque chunk est transformé en vecteur (1024 dimensions) par le modèle `BGE-M3` de sentence-transformers. Le modèle est chargé une seule fois en mémoire (lazy loading). Fallback : BGE-base (768 dims) puis MiniLM (384 dims).

4. **Stockage** — Les chunks (texte + vecteur) sont insérés dans PostgreSQL via pgvector. Un index IVFFlat est utilisé pour la recherche rapide.

### Phase de requête (à chaque question)

5. **Embed query** — La question est transformée en vecteur avec le même modèle.

6. **Recherche hybride** — Deux scores sont calculés pour chaque chunk :
   - Score sémantique (70%) : distance cosinus via pgvector (`<=>`)
   - Score keyword (30%) : TF basique en Python
   - Score final = 0.70 × sémantique + 0.30 × keyword
   - Les tableaux reçoivent un boost de 15% si la question contient des termes tabulaires

7. **Génération LLM** — Les top-K chunks sont assemblés en contexte et envoyés à Groq (Llama 3.3 70B) avec un prompt système qui force le LLM à ne répondre qu'à partir du contexte fourni et à citer ses sources.

---

## Sécurité

### Authentification

- Mots de passe hachés avec **bcrypt** (passlib), tronqués à 72 bytes
- JWT signé **HS256** avec expiration configurable (défaut: 60 min)
- Token stocké en cookie **HttpOnly** + **Secure** + **SameSite=Lax**
- Rate limiting : 5 tentatives de login par IP, blocage 15 minutes

### OTP (mot de passe oublié)

- Code à 6 chiffres envoyé par email
- Expiration : 15 minutes
- Stocké en mémoire (dict Python — à migrer vers Redis en production)

### Multi-tenant

- Chaque utilisateur appartient à une organisation
- Les RAG spaces sont isolés par organisation (filtrés par `organization_id`)
- Les utilisateurs sont assignés à des départements

---

## Dépendances principales

```
fastapi==0.111.0          # Framework web async
uvicorn==0.29.0           # Serveur ASGI
sqlalchemy==2.0.30        # ORM
psycopg2-binary==2.9.9    # Driver PostgreSQL
alembic==1.13.1           # Migrations DB
python-jose==3.3.0        # JWT
passlib==1.7.4            # Hachage bcrypt
pydantic==2.7.1           # Validation des données
fastapi-mail==1.4.1       # Envoi d'emails SMTP
langchain==0.2.0          # Orchestration RAG
langchain-groq             # Provider LLM Groq
pdfplumber==0.11.0        # Extraction PDF
pypdf==4.2.0              # Fallback PDF
pgvector==0.3.0           # Extension PostgreSQL vectorielle
sentence-transformers      # Modèles d'embedding locaux
```

---

## Variables d'environnement

| Variable                      | Requis | Défaut         | Description                             |
| ----------------------------- | ------ | -------------- | --------------------------------------- |
| `DATABASE_URL`                | Oui    | —              | URL PostgreSQL                          |
| `SECRET_KEY`                  | Oui    | —              | Clé secrète JWT (changer en production) |
| `ALGORITHM`                   | Non    | HS256          | Algorithme JWT                          |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Non    | 60             | Durée de vie du token                   |
| `MAIL_USERNAME`               | Oui    | —              | Email SMTP                              |
| `MAIL_PASSWORD`               | Oui    | —              | Mot de passe SMTP                       |
| `MAIL_FROM`                   | Oui    | —              | Adresse expéditeur                      |
| `MAIL_SERVER`                 | Non    | smtp.gmail.com | Serveur SMTP                            |
| `MAIL_PORT`                   | Non    | 587            | Port SMTP                               |
| `GROQ_API_KEY`                | Oui    | —              | Clé API Groq (gratuit)                  |
| `CHUNK_SIZE`                  | Non    | 512            | Taille de chunk par défaut              |
| `CHUNK_OVERLAP`               | Non    | 50             | Chevauchement par défaut                |
| `TOP_K`                       | Non    | 5              | Nombre de résultats par défaut          |

---

## Exemples de requêtes

### Inscription

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Fedi",
    "last_name": "Khala",
    "email": "fedi@welyne.com",
    "password": "securepassword",
    "org_type": "BUSINESS",
    "org_name": "Welyne"
  }'
```

### Connexion

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email": "fedi@welyne.com", "password": "securepassword"}'
```

### Créer un espace RAG

```bash
curl -X POST http://localhost:8000/api/rag/spaces \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "name": "RAG RH",
    "description": "Documents RH",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "top_k": 5,
    "chunk_strategy": "FIXED"
  }'
```

### Uploader un document

```bash
curl -X POST http://localhost:8000/api/rag/spaces/{space_id}/upload \
  -b cookies.txt \
  -F "file=@politique_rh.pdf"
```

### Poser une question

```bash
curl -X POST http://localhost:8000/api/rag/spaces/{space_id}/query \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"question": "Combien de jours de congé annuel ?"}'
```

---

## Licence

Projet de fin d'études — Welyne Software Engineering, 2026.
