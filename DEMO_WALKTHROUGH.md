# Faculty Demo Walkthrough — Pet Adoption Portal

A cue-sheet for presenting this project live. Each section has a speaker line and the exact commands to run. Practice this end-to-end at least once before the actual viva.

---

## 1. Introduce the Problem (30 seconds)

> "Animal shelters often struggle to connect rescued pets with adopters — listings get lost across phone calls, WhatsApp groups, and paper registers. Our Pet Adoption Portal gives shelters a place to list pets with photos, and gives adopters a way to browse, request, and track adoptions in one system. But the app itself isn't the focus of this evaluation — what we're actually demonstrating is the automated DevOps pipeline that takes this code from a laptop to a live server with zero manual setup."

## 2. Show the Architecture

Open [ARCHITECTURE.md](ARCHITECTURE.md) on GitHub (the diagrams render automatically) and point to the pipeline diagram:

> "Terraform creates our AWS server from code. Ansible then logs in and installs Docker, pulls our code from GitHub, and starts everything. Docker Compose runs three containers — frontend, backend, and database — wired together."

## 3. Show Terraform (Infrastructure as Code)

```bash
cd terraform
terraform plan
```
**Expected output:** `No changes. Your infrastructure matches the configuration.`

> "This confirms our live AWS infrastructure exactly matches what's defined in our `.tf` files — that's the core idea of Infrastructure as Code: the code is the single source of truth, not whatever happens to exist in the cloud console."

If asked to show it building something from scratch:
```bash
terraform destroy    # only if you want to show a full rebuild live - takes ~1 min to recreate after
terraform apply
```

## 4. Show Ansible (Configuration Management)

```bash
cd ansible
ansible all -i inventory.ini -m ping
```
**Expected output:** `pong`

> "This confirms Ansible can reach and manage our server over SSH." Then open `deploy.yml` and point out: it updates packages, installs Docker and git, clones our repository directly from GitHub, and starts the containers — one command, `ansible-playbook -i inventory.ini deploy.yml`, does all of that.

## 5. Show Docker on the Server

```bash
ssh -i ~/.ssh/pet-adoption-key ubuntu@<EC2_PUBLIC_IP>
docker compose ps
```
**Expected output:** 3 containers, all `Up` — `frontend`, `backend`, `db`.

> "All three services run in isolated containers on this one server. The database isn't exposed outside Docker's internal network at all — only the frontend and backend ports are open."

## 6. Demo the Live Application

Open `http://<EC2_PUBLIC_IP>` in a browser.

**As an Adopter:**
1. Register a new account, choosing "Adopter"
2. Browse pets, use the species filter and the Adopted/Not Adopted filter
3. Click a pet → view details → "Request to Adopt"
4. Go to "My Requests" → show it as `Pending`

**As a Shelter:**
5. Log out, register a new account choosing "Shelter/Admin"
6. "Add New Pet" → fill the form → automatically redirected to "My Pets"
7. On "My Pets" → upload a photo, edit a field, show it saves immediately
8. Go to "Requests" → find the adopter's request → click Approve
9. Point out: the pet's status instantly changes to `Adopted` everywhere (browse page, pet details, My Pets)

**Back as the Adopter:**
10. Refresh "My Requests" → show the status now says `Approved`

> "Notice the role-based access — a shelter account can't see the 'Request to Adopt' button at all, and an adopter can't reach the Add Pet or Requests pages. That's enforced both in the interface and, more importantly, in the API itself."

## 7. Show the Docker Volume Concept Live (this is the part faculty often probes)

```bash
# On the server, or ask us to demonstrate:
docker compose down      # removes containers
docker compose up -d     # recreates them fresh
```
Then refresh the browser — **all pets and photos are still there.**

> "The containers were just deleted and recreated from scratch, but the data survived, because it lives in Docker volumes — `mysql_data` and `pet_images` — which are separate from the containers' own disposable filesystem. This is the difference between a container's filesystem and a volume."

If asked "what if you delete the volume too":
```bash
docker compose down -v   # this DOES delete the data - only do this if you want to show data loss deliberately
```

See [FACULTY_CHALLENGE_SCENARIOS.md](FACULTY_CHALLENGE_SCENARIOS.md) for a full list of "what if you do X live" scenarios and how to respond to each.

## 8. Show the GitHub Repository

Open the repo in a browser. Point out:
- Clean folder structure: `app/frontend`, `app/backend`, `terraform`, `ansible`
- Both Dockerfiles
- `docker-compose.yml`
- A `.gitignore` that keeps secrets (SSH keys, Terraform state, `.env`) out of version control
- [PROJECT_LOG.md](PROJECT_LOG.md) — every decision made and why, plus real bugs found and fixed during development

> "Everything here is version-controlled and reproducible — anyone could clone this repo and stand up the exact same system."

---

## 9. Quick Viva Answers (memorize these)

| Question | Answer |
|---|---|
| What is DevOps? | Combining development and operations through automation, so deployment isn't a manual, error-prone process |
| What is IaC? | Describing infrastructure in code instead of clicking through a cloud console — repeatable, version-controlled |
| Terraform vs Ansible? | Terraform **creates** infrastructure (does the server exist, with what settings); Ansible **configures** infrastructure that already exists (is the right software installed and running) |
| Image vs Container? | Image = frozen blueprint; Container = a running instance made from it. Many containers can come from one image |
| Why Docker Compose? | Runs multiple containers together with one config file and one command, and gives them a shared network so they can reach each other by service name |
| Why a volume for photos? | Without it, deleting/recreating the backend container would permanently lose every uploaded photo |
| What is JWT? | A signed token proving identity, given after login; the server verifies its signature on each request instead of storing server-side sessions |
| Why MySQL and not MongoDB? | Our data has fixed relationships (a pet belongs to a shelter, a request links a user and a pet) — a textbook case for foreign keys |
| What real bugs did you find? | Two ownership/IDOR bugs — a client could act on another user's/shelter's data by just changing an ID; fixed by deriving identity from the verified JWT instead of trusting the request |
| What would you improve given more time? | Token revocation before expiry, a production WSGI server instead of Flask's dev server, externalizing secrets into a `.env`/secrets manager |
