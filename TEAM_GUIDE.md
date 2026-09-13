# Team Guide — Pet Adoption Portal

This document exists so that **any of the 4 people on this team** can read it once and understand the whole project — not just your own piece. Read this before the viva even if you didn't touch the code for a particular part.

---

## 1. What This Project Actually Is

**In one sentence:** a website where animal shelters list rescue pets, and people can browse, request to adopt, and track that request — plus the automated pipeline that puts this website on the internet.

**Two kinds of accounts:**
- **Adopter (user)** — browses pets, requests adoption, tracks their own requests
- **Shelter (admin)** — lists pets, uploads photos, manages their own pets, approves/rejects requests

**The important framing for viva:** the *app* (pets, requests, login) is deliberately simple. What's actually being graded is the **DevOps pipeline** — how this code goes from a laptop to a live, internet-reachable server with zero manual server setup, using Terraform + Ansible + Docker.

---

## 2. Walk Through It As A User (do this yourself before viva)

**As an Adopter:**
1. Register on `register.html`, choosing "Adopter"
2. Log in → you land on the homepage, browse pets, filter by species or adoption status
3. Click a pet → "Request to Adopt"
4. Go to "My Requests" → see your request as `Pending`
5. If you change your mind, "Cancel Request" — pet goes back to `Available`

**As a Shelter:**
1. Register choosing "Shelter/Admin"
2. Log in → "Add New Pet" → fill the form → you're redirected to "My Pets"
3. On "My Pets", upload a photo, edit any field, or delete the pet — all usable any time, not just right after adding it
4. Go to "Requests" → see adopters' pending requests for your pets → Approve or Reject
5. Approving sets the pet to `Adopted`; rejecting sets it back to `Available`

Do this full loop yourself at least once — it's the fastest way to actually understand what the code does instead of just reading it.

---

## 3. The Tech Stack, Explained Like You're New To It

| Piece | What it is | Why we picked it |
|---|---|---|
| **HTML/CSS/JavaScript** | The actual pages you see in the browser | No build tools, no framework — every line is readable by anyone on the team |
| **Flask (Python)** | The backend "brain" — receives requests, talks to the database, sends back answers | Small and function-based; each API feature is a short, separate Python function |
| **MySQL** | The database — 4 tables: `shelters`, `users`, `pets`, `adoption_requests` | Real relationships (a pet *belongs to* a shelter, a request *links* a user and a pet) — a textbook case for a relational database |
| **JWT (JSON Web Token)** | How the server remembers who's logged in | After login, you get a signed token; every future request includes it so the server can verify "who is this, and what are they allowed to do" without a database lookup each time |
| **Docker** | Packages the frontend, backend, and database into isolated, portable units | Same app runs identically on a laptop or a cloud server — no "works on my machine" problems |
| **Docker Compose** | Runs all 3 Docker containers together with one command | Instead of starting 3 things by hand with 3 different commands |
| **Terraform** | Creates the actual cloud server (AWS EC2 instance) from code | The server's entire definition lives in a text file — reproducible, no manual console clicking |
| **Ansible** | Logs into that server and installs/configures everything | Automates what would otherwise be a long list of manual SSH commands |
| **AWS (EC2)** | Where the server actually lives, reachable by anyone on the internet | Cloud provider used for this project |

---

## 4. How The Pieces Actually Connect

```
You browse the site
        │
        ▼
  Frontend (HTML/JS) ──fetch()──▶  Backend (Flask API)  ──SQL──▶  MySQL
        │                                  │
        │                                  └─▶ saves/reads uploaded photos on disk
        ▼
  Runs in a Docker container            Runs in a Docker container
  (nginx serves the static files)       (Python + Flask)
        │                                  │
        └──────────── both run on the same AWS EC2 server ────────────┘
```

The frontend never talks to MySQL directly — it always goes through the Flask API. This is the standard 3-tier structure: **presentation (frontend) → logic (backend) → data (database)**.

For the full diagrams (deployment pipeline, database schema, request flows), see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 5. Codebase Map — Where To Find Things

```
app/backend/app.py        → every API route (the whole backend logic lives in ONE file)
app/backend/db.py         → the one function that connects to MySQL
app/backend/schema.sql    → the 4 database tables
app/frontend/*.html       → one file per page
app/frontend/js/*.js      → one JS file per page, plus api.js (shared helpers used by all pages)
app/frontend/css/style.css→ all styling, one file
docker-compose.yml        → wires frontend + backend + database containers together
terraform/*.tf            → defines the AWS server + firewall
ansible/deploy.yml        → the steps that configure that server and deploy the app
```

---

## 6. The 4 Roles — What To Say Is "Yours"

| Role | Files | One sentence to explain your part |
|---|---|---|
| **Frontend** | `app/frontend/` | "I built every page the user sees and the JavaScript that talks to our API." |
| **Backend** | `app/backend/app.py`, `db.py`, `schema.sql` | "I built the API and database — every action (login, add a pet, request adoption) is one function here." |
| **Docker** | Both `Dockerfile`s, `docker-compose.yml` | "I packaged the app into containers and wired them together, including the volumes that keep data safe." |
| **Cloud/Infra** | `terraform/`, `ansible/` | "I wrote the code that creates our cloud server and automatically configures + deploys the app onto it." |

You should still be able to explain the other 3 people's parts at a basic level — that's what this document is for.

---

## 7. Quick Glossary (things faculty love to ask about)

- **DevOps** — combining development and operations so deployment is automated, not manual
- **IaC (Infrastructure as Code)** — describing your server in a file instead of clicking through a cloud console
- **Image vs Container** — an image is the frozen blueprint; a container is a running instance made from it (you can make many containers from one image)
- **Volume** — a storage area outside the container's own filesystem, so data survives even if the container is deleted and recreated
- **JWT** — a signed token proving who you are, without the server needing to store a session
- **IDOR (a bug we actually found and fixed)** — when an app trusts an ID you send it (like `user_id=5` in a URL) instead of verifying who you really are — we found and fixed two of these (see [PROJECT_LOG.md](PROJECT_LOG.md))

For the full list of every decision made and why, read [PROJECT_LOG.md](PROJECT_LOG.md). For the faculty demo script, read [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md).
