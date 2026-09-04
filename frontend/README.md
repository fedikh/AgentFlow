# AgentFlow — Frontend (React + Vite)

Single-page app for the AgentFlow platform. One codebase, three role-based
experiences (the role comes from the login and drives routing):

| Role | Landing | What they can do |
|---|---|---|
| **Admin** | `/admin` | Org dashboard · manage users & departments (`/admin/users`) · company LLM/embedding providers & API keys (`/admin/providers`) · RAG oversight (`/admin/rag`) · observability (`/admin/observability`) |
| **IT** | `/it` | IT dashboard · build & tune RAG spaces (`/it/rag`, `/it/rag/:spaceId`: documents, chunking, embeddings, retrieval, evaluation, security) · deployed agents (`/it/agents`) · observability |
| **User** | `/user/agents` | Full-page chat with the department's deployed agents (DeepSeek-style) · agent picker, dashboard and profile open as overlays from the profile ⋯ menu |

Auth pages: `/login`, `/signup` (first signup creates the organization + admin),
`/forgot` (OTP reset), `/activate` (invited users set their password).

> To run the whole stack with one command, see [../DOCKER.md](../DOCKER.md).

---

## Tech stack

- **React 19** + **Vite 8** (dev server & build), React Router 7
- **Tailwind CSS 4** + hand-written CSS per page under `src/styles/`
- **Recharts** (dashboards), **lucide-react** / react-icons (icons),
  **react-markdown** + remark-gfm (chat answers)
- No state library — local state + small fetch wrappers in `src/services/`

## Running locally

### 1. Prerequisites
- Node.js **20+**
- The backend running on **http://localhost:8000** (see [../backend/README.md](../backend/README.md))

### 2. Configure `.env`

Create `frontend/.env`:

| Variable | Required | What it does |
|---|---|---|
| `VITE_API_URL` | ✅ | Backend API base — `http://localhost:8000/api` |
| `VITE_GOOGLE_CLIENT_ID` / `VITE_GOOGLE_API_KEY` / `VITE_GOOGLE_APP_ID` | optional | Google Picker (import documents from Google Drive). Without them everything else works; only the Drive import button won't. |

`VITE_*` values are baked in **at build time** — rebuild after changing them.

### 3. Run

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The dev server **must stay on port 5173** — the backend only allows that origin
in CORS, and auth uses cookies (`credentials: include`).

Other scripts: `npm run build` (production build to `dist/`),
`npm run preview` (serve the build), `npm run lint`.

## Project layout

```
frontend/src/
├── App.jsx                 # All routes + role-based protection
├── main.jsx                # Entry point
├── Startpage.jsx           # Public landing page
├── pages/
│   ├── auth/               # Login, Signup, Forgot (OTP), Activate
│   ├── admin/              # AdminDashboard, UsersPage, ApiProvidersPage, AdminRAGPage
│   ├── it/                 # ITDashboard, RAGSpacesPage (the space builder), ITAgentsPage
│   ├── user/               # UserChatPage (the end-user experience), UserDashboard
│   └── shared/             # ProfilePage, RAGObservabilityPage
├── components/
│   ├── ProtectedRoute.jsx / PublicRoute.jsx
│   ├── layout/             # Sidebar + app shell for admin/IT
│   ├── rag/                # RAG space builder pieces (config, docs, chat test…)
│   ├── it/, user/, dashboard/, auth/, startpage/
├── services/               # authApi, usersApi, ragApi, providersApi, useGooglePicker
└── styles/                 # Page-scoped CSS (e.g. styles/user/userChat.css)
```

## How it talks to the backend

Every service in `src/services/` calls `VITE_API_URL` with
`credentials: "include"` — the JWT lives in an HttpOnly cookie set by
`/api/auth/login`, so there is no token handling in JS. On a `401` the app
redirects to `/login`.
