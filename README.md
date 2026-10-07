# 🐾 Pet Adoption Portal

Animal shelters often struggle to connect rescued pets with adopters — listings get lost across phone calls, WhatsApp groups, and paper registers. This portal gives shelters a place to list pets and gives adopters a way to browse, request, and track adoptions in one system.

**This is a DevOps project.** The pet-adoption app itself is intentionally simple — the subject being graded is the automated pipeline that takes code from a laptop to a live, monitored server with zero manual steps.

- **FA1** (Units I–II): Git/GitHub, Docker, Docker Compose, Terraform, Ansible
- **FA2** (Units III–IV): CI/CD pipeline, automated testing, security scanning, Kubernetes, Prometheus + Grafana monitoring, centralized logging, SRE practices

**Live demo:** http://13.201.134.98 *(the server now gets a fixed Elastic IP — run `terraform output public_ip` for the current address)*

---

## 1. The Big Picture

```
 Developer
    │  git push
    ▼
 GitHub ──────────────►  GitHub Actions  (CI/CD pipeline)
                           │
   ┌───────────────────────┼──────────────────────────────────────────────┐
   │ 1 TEST      flake8 + 45 unit tests (85% coverage required)           │
   │ 2 SECURITY  Bandit (code) + pip-audit (libraries) + Trivy (images)   │
   │ 3 BUILD     Docker images  ──push──►  GitHub Container Registry      │
   │ 4 VERIFY    Docker Compose test  +  Kubernetes (kind) test           │
   │             Terraform validate  +  Ansible syntax check              │
   │ 5 DEPLOY    Ansible ──SSH──► AWS EC2  (only on main branch)          │
   │ 6 SMOKE     curl-based checks against the live site                  │
   └───────────────────────┼──────────────────────────────────────────────┘
                           ▼
        AWS EC2 server  (created by Terraform, configured by Ansible)
          ├── frontend (nginx)  ── port 80 ──► users' browsers
          ├── backend  (Flask + gunicorn)  ◄── nginx forwards /api here
          ├── db       (MySQL)
          └── monitoring:  Prometheus · Grafana · Alertmanager · Loki · Promtail · node-exporter
                              │
                              └── Grafana dashboard  ── port 3000
```

**House analogy:** Terraform builds the house (the server), Ansible does the wiring and plumbing (installs software), Docker puts the furniture in (runs the app), GitHub Actions is the construction manager who checks everything before anyone moves in, and Prometheus/Grafana are the smoke alarms and the electricity meter.

## 2. FA2 Rubric → Where it is implemented

| Syllabus topic | What we did | Where to look |
|---|---|---|
| CI/CD pipeline fundamentals (Build, Test, Deploy loop) | One pipeline with 7 jobs, runs on every push/PR | `.github/workflows/ci-cd.yml` |
| Pipeline as Code | The whole pipeline is a YAML file in the repo | `.github/workflows/ci-cd.yml` |
| Automating compilation and unit testing | 45 pytest tests, coverage gate of 85% (actual: 99%) | `app/backend/tests/` |
| DevSecOps | Bandit, pip-audit, Trivy scans inside the pipeline; found & fixed 4 vulnerable libraries | `security` + `build` jobs |
| Continuous Deployment, deployment strategies | Auto-deploy to AWS on every merge to `main`; Kubernetes rolling update (zero downtime) | `deploy` job, `k8s/backend.yaml` |
| Container orchestration: Kubernetes | Deployments, Services, ConfigMap/Secret, PVC, probes, HPA | `k8s/` |
| Infrastructure as Code | Terraform (server, firewall, fixed IP) + Ansible (software, deployment) | `terraform/`, `ansible/` |
| Docker / Compose / multi-container | 3 app containers + 6 monitoring containers | `docker-compose*.yml` |
| Monitoring & Observability (metrics, logs) | Prometheus metrics, Loki logs, Grafana dashboard | `monitoring/` |
| Prometheus & Grafana | Backend exposes `/metrics`; one provisioned dashboard | `monitoring/grafana/` |
| Centralized logging (ELK or similar) | Backend logs JSON → Promtail → Loki → Grafana (Loki is the lightweight "similar" to ELK) | `monitoring/loki`, `monitoring/promtail` |
| SRE: SLOs / SLIs, incident management, post-mortems | SLO table, alert rules, runbook, post-mortem | Sections 8–9 below |

## 3. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | HTML, CSS, vanilla JavaScript, served by nginx | No build step; nginx also forwards `/api` to the backend |
| Backend | Python + Flask, run by gunicorn | Small REST API; gunicorn is a production-grade server |
| Database | MySQL 8 | Relational tables: Users / Pets / Adoption Requests / Shelters |
| Auth | JWT + Werkzeug password hashing | Stateless tokens; passwords never stored in plain text |
| Containers | Docker + Docker Compose | Same behaviour on a laptop, in CI, and on the server |
| Orchestration | Kubernetes (manifests in `k8s/`) | Self-healing, scaling, rolling updates |
| CI/CD | GitHub Actions | Already hosts our code; free; pipeline lives in the repo |
| Registry | GitHub Container Registry (ghcr.io) | Stores the built images, tagged with the git commit |
| IaC | Terraform + Ansible | Terraform creates infrastructure; Ansible configures it |
| Cloud | AWS EC2 | Hosts the VM |
| Monitoring | Prometheus, Alertmanager, Grafana, node-exporter | Metrics, alerts, dashboards |
| Logging | Loki + Promtail | Central log storage and search |

## 4. The CI/CD Pipeline in Detail

File: `.github/workflows/ci-cd.yml`. Triggered by every push and pull request to `main`.

| # | Job | What it does | Fails the pipeline if… |
|---|---|---|---|
| 1 | **test** | Installs dependencies, runs `flake8` (style) and `pytest` (45 tests) | a test fails, lint fails, or coverage < 85% |
| 2 | **security** | `bandit` scans our Python for insecure patterns; `pip-audit` checks libraries for known CVEs | any issue is found |
| 3 | **build** | Builds the backend and frontend Docker images, tags them with the short git commit (e.g. `a1b2c3d`) and `latest`, pushes to ghcr.io (main only), then **Trivy** scans the images | the image has a fixable CRITICAL vulnerability |
| 4a | **compose-test** | Starts the full app with Docker Compose, runs `scripts/smoke_test.sh`, then starts the monitoring stack and confirms Prometheus sees the backend | any smoke check fails |
| 4b | **k8s-test** | Creates a temporary Kubernetes cluster (kind), deploys `k8s/`, runs the same smoke test | pods don't become ready, or a check fails |
| 4c | **iac-check** | `terraform fmt` + `terraform validate`, and `ansible-playbook --syntax-check` | infrastructure code is invalid |
| 5 | **deploy** | *Main branch only.* Runs the Ansible playbook against EC2 with the exact image tag that was just tested, then smoke-tests the live site | the deploy or the live smoke test fails |

Key idea: **build once, deploy the same thing everywhere.** The image that passed the tests is the exact image pulled onto the server (identified by the commit tag). To roll back, redeploy an older tag.

### One-time setup for the deploy job
GitHub repo → *Settings → Secrets and variables → Actions → New repository secret*:

| Secret | Value |
|---|---|
| `EC2_HOST` | Public IP from `terraform output public_ip` |
| `EC2_SSH_KEY` | Contents of the private key matching `~/.ssh/pet-adoption-key.pub` |
| `MYSQL_ROOT_PASSWORD` | A strong password |
| `APP_SECRET_KEY` | A long random string (signs login tokens) |
| `GRAFANA_ADMIN_PASSWORD` | A strong password |

Until `EC2_HOST` is set, the deploy job skips itself (with a warning) so the rest of the pipeline stays green. Also create a GitHub *Environment* named `production` (Settings → Environments) — you can add a required reviewer there for manual approval before deploys.

## 5. Project Structure

```
devops-project/
├── .github/workflows/ci-cd.yml   CI/CD pipeline
├── app/
│   ├── backend/                  Flask API, schema.sql, Dockerfile, tests/
│   └── frontend/                 HTML/CSS/JS, nginx.conf, Dockerfile
├── docker-compose.yml            The app (db + backend + frontend)
├── docker-compose.monitoring.yml Prometheus, Grafana, Alertmanager, Loki, Promtail, node-exporter
├── k8s/                          Kubernetes manifests + deploy.sh
├── monitoring/                   Prometheus rules, Alertmanager, Loki, Promtail, Grafana dashboard
├── scripts/smoke_test.sh         End-to-end check used by the pipeline
├── terraform/                    AWS EC2 + security group + Elastic IP
└── ansible/                      Server setup + deployment playbook
```

## 6. Running It

### Locally with Docker Compose
```bash
docker compose up --build -d                                   # the app
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up --build -d   # app + monitoring
./scripts/smoke_test.sh http://localhost                        # verify
```

| URL | What |
|---|---|
| http://localhost | The website |
| http://localhost:3000 | Grafana (login `admin` / `admin`) — dashboard opens by default |
| http://localhost:9090 | Prometheus (try the *Alerts* page) |
| http://localhost:9093 | Alertmanager |
| http://localhost:5000/metrics | Raw metrics from the backend (local only) |

Register a **Shelter** account to add pets and upload photos; register an **Adopter** account to browse and request adoptions. A demo shelter exists: `demo@shelter.com` / `Demo@1234`.

### Running the tests
```bash
cd app/backend
pip install -r requirements-dev.txt
pytest          # 45 tests, shows coverage, fails under 85%
flake8 .        # style check
```
The tests replace MySQL with a fake in-memory database (`tests/conftest.py`), so they run in about 2 seconds with no containers.

### On Kubernetes
Works on any cluster (Docker Desktop with Kubernetes enabled, minikube, kind):
```bash
./k8s/deploy.sh
kubectl get pods -n pet-portal                                    # 2 backend, 2 frontend, 1 mysql
kubectl port-forward -n pet-portal svc/frontend 8080:80           # then open http://localhost:8080
kubectl delete pod -n pet-portal -l app=backend --wait=false      # self-healing: watch new pods appear
kubectl scale deployment backend -n pet-portal --replicas=4       # manual scaling
```
What each file does: `namespace.yaml` (a folder for our objects), `config.yaml` (ConfigMap + Secret), `mysql.yaml` (database + persistent disk), `backend.yaml` (API Deployment with health probes, Service, autoscaler), `frontend.yaml` (nginx Deployment + NodePort Service), `kustomization.yaml` (lists them all so one `apply -k` deploys everything).

### On AWS (full pipeline)
```bash
cd terraform
terraform init
terraform apply            # creates EC2 (t3.medium) + firewall + Elastic IP
terraform output           # prints public_ip, app_url, grafana_url
```
Put `public_ip` into the `EC2_HOST` secret (and `ansible/inventory.ini` for manual runs). After that, **every merge to `main` deploys automatically**. Manual deploy:
```bash
export MYSQL_ROOT_PASSWORD=... APP_SECRET_KEY=... GRAFANA_ADMIN_PASSWORD=...
cd ansible && ansible-playbook -i inventory.ini deploy.yml -e image_tag=<commit-sha>
```
> **Migrating the existing server:** MySQL only reads its root password the first time its data volume is created. The existing server's database was created with the password `password`, so either set the `MYSQL_ROOT_PASSWORD` secret to `password` for the first deploy, or delete the old volume (`docker volume rm devopsproject_mysql_data`, which erases the data) before deploying.

## 7. Monitoring & Logging

**Metrics (Prometheus).** The backend exposes `/metrics` using `prometheus_client`. It records:
- `http_requests_total{method, endpoint, status}` — traffic and errors
- `http_request_duration_seconds` — latency histogram
- Business counters: `pet_portal_adoption_requests_total`, `pet_portal_logins_total`, `pet_portal_registrations_total`, `pet_portal_pets_added_total`

Prometheus scrapes the backend and node-exporter (server CPU/memory) every 15 seconds. `/metrics` is deliberately **not** reachable through nginx, so it is not public.

**Dashboard (Grafana).** Provisioned automatically from `monitoring/grafana/` (no clicking needed). It shows the "golden signals": requests per second, error rate, p95 latency, plus adoption/login business metrics, server CPU/memory, and the live backend logs.

**Logs (Loki).** The backend writes one JSON log line per request (method, path, status, duration, request id). Promtail reads all container logs and ships them to Loki; Grafana's logs panel searches them. (Loki plays the role of the ELK stack from the syllabus, with much lower memory use.)

**Alerts** (`monitoring/prometheus/alerts.yml`, shown in Prometheus → Alerts and Alertmanager):

| Alert | Fires when | Why it matters |
|---|---|---|
| ServiceDown | a monitored service stops responding for 1 min | outage |
| HighErrorRate | more than 5% of requests are 5xx for 2 min | users are seeing errors (SLO 1) |
| HighLatency | p95 latency above 500 ms for 5 min | site is slow (SLO 2) |
| LoginFailureSpike | more than 1 failed login/second for 5 min | possible password guessing |
| HighMemoryUsage | server memory above 90% for 5 min | this is what crashed the old t3.micro |

**Try it yourself (great for the demo):**
```bash
docker compose stop backend      # break the app
# wait ~1.5 minutes → open http://localhost:9093 : ServiceDown is firing
docker compose start backend     # fix it → the alert clears
```
We tested exactly this: `ServiceDown` fires in Alertmanager about 100 seconds after the backend is stopped, and clears after it restarts.

## 8. Site Reliability Engineering (SRE)

**SLI** (Service Level Indicator) = something we measure. **SLO** (Service Level Objective) = the target we promise. **Error budget** = how much failure the SLO allows.

| SLO | SLI (what we measure) | Target | Error budget (30 days) | Alert |
|---|---|---|---|---|
| Availability | share of requests that are not 5xx | 99.5% | ~3.6 hours of failures | HighErrorRate, ServiceDown |
| Latency | share of requests faster than 500 ms | 95% | 5% of requests may be slower | HighLatency |

If the error budget is used up, we stop shipping new features and fix reliability first.

**Incident runbook** (what to do when an alert fires):
1. **Acknowledge** — open the Grafana dashboard; which signal is bad (errors, latency, down)?
2. **Check** — `docker compose ps` on the server (SSH in): is a container down or restarting? Check the backend logs panel in Grafana or `docker compose logs backend`.
3. **Common causes** — database down (`/api/ready` returns 503) → restart `db`; server out of memory → check the memory panel, restart containers; bad deploy → redeploy the previous image tag with Ansible (`-e image_tag=<old-sha>`).
4. **Recover & verify** — run `./scripts/smoke_test.sh http://<server-ip>`.
5. **Write a post-mortem** within 2 days, blameless (about the system, not the person).

## 9. Post-mortem: Repeated EC2 crashes (September 2026)

*(Reconstructed from the project's git history, commit `46808a5`.)*

| | |
|---|---|
| **Impact** | The live site became unresponsive several times and had to be restarted by hand. |
| **Detection** | Noticed manually — there was no monitoring or alerting at the time. |
| **Root cause** | The `t3.micro` server has only 1 GB of RAM. MySQL, Flask and nginx together used up all the memory; the Linux out-of-memory killer then stopped services, and the machine stopped responding (even to SSH). There was no swap space to absorb spikes. |
| **Fix** | Moved to a larger instance (`t3.small`) and added a 2 GB swap file through Ansible (commit `46808a5`). |
| **What went well** | The fix is in code (Terraform + Ansible), so rebuilding the server was a repeatable, one-command job. |
| **What went badly** | We only found out when someone opened the site. |
| **Action items (done in FA2)** | ✅ Prometheus + node-exporter now track server memory; `HighMemoryUsage` and `ServiceDown` alerts. ✅ Instance upgraded to `t3.medium` to fit the monitoring stack. ✅ Containers get health checks and restart automatically. ✅ Smoke test runs after every deploy. |

## 10. API Endpoints

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | none | Liveness: is the process running? (no database check) |
| GET | `/api/ready` | none | Readiness: is the database reachable? (503 if not) |
| GET | `/metrics` | none (internal only) | Prometheus metrics |
| POST | `/api/users/register` | none | Create adopter account |
| POST | `/api/users/login` | none | Adopter login → JWT |
| POST | `/api/shelters/register` | none | Create shelter account |
| POST | `/api/shelters/login` | none | Shelter login → JWT |
| GET | `/api/pets` | none | List/search pets |
| GET | `/api/pets/<id>` | none | One pet's details |
| GET | `/api/pets/my-pets` | shelter | List your own pets |
| POST | `/api/pets` | shelter | Add a new pet |
| PUT | `/api/pets/<id>` | shelter (owner only) | Update a pet |
| DELETE | `/api/pets/<id>` | shelter (owner only) | Delete a pet |
| POST | `/api/pets/<id>/upload-image` | shelter (owner only) | Upload/replace a pet photo |
| GET | `/uploads/<filename>` | none | Serve an uploaded photo |
| POST | `/api/adoption-requests` | user | Request to adopt a pet |
| GET | `/api/adoption-requests/my-requests` | user | Track your own requests |
| GET | `/api/adoption-requests/shelter-requests` | shelter | View pending requests for your pets |
| PUT | `/api/adoption-requests/<id>` | shelter (owner only) | Approve/reject a request |
| DELETE | `/api/adoption-requests/<id>` | user (owner only) | Cancel your own pending request |

## 11. Team Roles

| Person | Owns | Explains in viva |
|---|---|---|
| A — Frontend + Tests | `app/frontend/`, `app/backend/tests/` | How a user browses/adopts pets; what the unit tests check and why they use a fake database |
| B — Backend + Monitoring | `app/backend/`, `monitoring/` | Request → Flask → MySQL → response; what `/metrics` exposes; the dashboard and alerts |
| C — Docker + Kubernetes | Dockerfiles, `docker-compose*.yml`, `k8s/` | Image vs container; why probes, replicas and a PVC exist; rolling updates |
| D — Cloud/Infra + CI/CD | `terraform/`, `ansible/`, `.github/` | How the pipeline runs end to end; Terraform vs Ansible; secrets handling |

## 12. Troubleshooting

| Problem | Cause / fix |
|---|---|
| Pipeline `deploy` job is skipped | The `EC2_HOST` secret isn't set yet (see section 4) |
| Backend keeps restarting after a deploy with a new password | MySQL kept its old password in the data volume — see the migration note in section 6 |
| `port is already allocated` on 80 or 3000 | Something else uses that port; stop it or change the left side of the port mapping |
| Grafana panels show "No data" right after startup | Wait ~30 seconds and generate some traffic (`./scripts/smoke_test.sh`) |
| Site shows 502 | The backend container is down or not ready — `docker compose ps` / `docker compose logs backend` |
| `/api/ready` returns 503 | The backend can't reach MySQL — check the `db` container |
