# 🐾 Pet Adoption Portal

Animal shelters often struggle to connect rescued pets with adopters — listings get lost across phone calls, WhatsApp groups, and paper registers. This portal gives shelters a place to list pets and gives adopters a way to browse, request, and track adoptions in one system.

**This is a DevOps project.** The pet-adoption app itself is intentionally simple — the actual subject being graded is the automated pipeline that takes this code from a laptop to a live server with zero manual server setup:

```
Developer's Laptop
      │  (git push)
      ▼
   GitHub Repository
      │
      ▼
  Terraform  ──creates──▶  AWS EC2 Instance (Ubuntu) + Security Group
      │
      ▼
   Ansible  ──configures──▶  Installs Docker + git, clones this repo,
      │                        builds & starts containers
      ▼
Docker Compose on the VM
      ├── frontend container  (nginx serving HTML/CSS/JS, port 80)
      ├── backend container   (Flask REST API, port 5000)
      └── db container        (MySQL, internal only)
      │
      ▼
  Browser  ──▶  http://<EC2 Public IP>
```

**Live demo:** http://13.201.134.98 *(will change if the EC2 instance is recreated/resized — check `terraform output public_ip`)*

Think of it like moving into a new house: **Terraform** builds the four walls (the server), **Ansible** wires the electricity and plumbing (installs software), **Docker Compose** moves your furniture in ready-to-use (runs the app).

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | HTML, CSS, vanilla JavaScript | No build step — simple enough for every teammate to read and explain |
| Backend | Python + Flask | Small, function-based REST API |
| Database | MySQL | Relational tables matching Users / Pets / Adoption Requests / Shelters |
| Auth | JWT + Werkzeug password hashing | Stateless login tokens; passwords never stored in plain text |
| Containerization | Docker + Docker Compose | Packages frontend, backend, and database so they run identically anywhere |
| Infrastructure as Code | Terraform | Creates the cloud server from code, not manual console clicks |
| Configuration Management | Ansible | Automates installing Docker and deploying the app on the server |
| Cloud Provider | AWS (EC2) | Hosts the VM |

## Team Roles

| Person | Owns | Explains in viva |
|---|---|---|
| A — Frontend | `app/frontend/` | How a user browses/searches/adopts pets |
| B — Backend | `app/backend/` (except Docker files) | How data flows: request → Flask function → MySQL → response |
| C — Docker | Dockerfiles, `docker-compose.yml` | Image vs container, why a volume protects pet photos |
| D — Cloud/Infra | `terraform/`, `ansible/` | How the VM is created and configured automatically |

## Project Structure

```
devops-project/
├── README.md
├── docker-compose.yml
├── app/
│   ├── backend/                Flask API, MySQL schema, Dockerfile
│   └── frontend/                HTML/CSS/JS, Dockerfile
├── terraform/                  AWS EC2 VM + security group (infrastructure)
└── ansible/                    Server configuration + deployment
```

## Running Locally (Docker Compose)

```bash
git clone <this-repo-url>
cd devops-project
docker compose up --build -d
```

Then open:
- `http://localhost` — the app itself
- `http://localhost:5000/api/health` — backend health check

Register a **Shelter** account to add pets and upload photos; register an **Adopter** account to browse and request adoptions.

## Running on AWS (full pipeline)

```bash
cd terraform
terraform init
terraform apply

cd ../ansible
# update inventory.ini with the VM's public IP from the terraform output
ansible all -i inventory.ini -m ping
ansible-playbook -i inventory.ini deploy.yml
```

Then open `http://<EC2_PUBLIC_IP>` in a browser.

## API Endpoints

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | none | Health check |
| POST | `/api/users/register` | none | Create adopter account |
| POST | `/api/users/login` | none | Adopter login → JWT |
| POST | `/api/shelters/register` | none | Create shelter account |
| POST | `/api/shelters/login` | none | Shelter login → JWT |
| GET | `/api/pets` | none | List/search pets |
| GET | `/api/pets/<id>` | none | One pet's details |
| GET | `/api/pets/my-pets` | shelter | List your own pets |
| POST | `/api/pets` | shelter | Add a new pet |
| PUT | `/api/pets/<id>` | shelter (owner only) | Update any of a pet's fields |
| DELETE | `/api/pets/<id>` | shelter (owner only) | Delete a pet |
| POST | `/api/pets/<id>/upload-image` | shelter (owner only) | Upload/replace a pet photo |
| GET | `/uploads/<filename>` | none | Serve an uploaded photo |
| POST | `/api/adoption-requests` | user | Request to adopt a pet |
| GET | `/api/adoption-requests/my-requests` | user | Track your own requests |
| GET | `/api/adoption-requests/shelter-requests` | shelter | View pending requests for your pets |
| PUT | `/api/adoption-requests/<id>` | shelter | Approve/reject a request |
| DELETE | `/api/adoption-requests/<id>` | user (owner only) | Cancel your own pending request |
