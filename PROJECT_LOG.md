# Project Log — Pet Adoption Portal

This file records **everything built, every command run, and the reasoning behind every decision**, in the order it happened. Read this before your viva — if your professor asks "why did you choose X over Y," the answer is in here.

---

## Step 1 — Project structure & Git

**What:** Created the folder skeleton (`app/backend`, `app/frontend`, `terraform`, `ansible`) and empty placeholder files, then ran `git init`, made the first commit, created a GitHub repo, and pushed with `git remote add origin` + `git push -u origin main`.

**Decision — folder layout:** One `app/` folder holding both `backend/` and `frontend/`, kept separate from `terraform/` and `ansible/`. This maps directly onto the 4-person team split (Frontend, Backend, Docker, Cloud/Infra) and matches how the DevOps pipeline itself is structured: app code vs. infrastructure code are different concerns owned by different people.

**Decision — `.gitignore` from day one:** Added `*.pem`, `*.tfstate`, `.terraform/`, `__pycache__/`, `uploads/`, `.env` before writing any real code, specifically to make sure secrets (SSH keys, Terraform state, DB credentials) are never accidentally committed. This is a standard DevOps hygiene practice, not an afterthought.

---

## Step 2 — MySQL Schema (`app/backend/schema.sql`)

**What:** Defined 4 tables: `shelters`, `users`, `pets`, `adoption_requests`, with foreign keys linking pets → shelters and adoption_requests → users/pets.

**Decision — MySQL (relational) over MongoDB:** Chosen explicitly because the data has clear, fixed relationships (a pet belongs to one shelter, a request links one user to one pet) — a textbook case for foreign keys, and it lets us answer real viva questions about joins and relational integrity.

**Decision — `image_filename` column instead of storing the image itself:** Storing binary image data inside MySQL bloats the database and is slow to query. Instead, the actual photo lives on disk (later: in a Docker volume), and MySQL just stores its filename. This single decision is what makes the Docker volume lesson (Step 10) meaningful.

---

## Step 3 — Flask Backend Skeleton

**What:** `app/backend/db.py` (`get_db_connection()`) and `app/backend/app.py` (Flask app + `/api/health` route).

**Decision — Flask over Node/Express:** Chosen by direct preference (asked and confirmed) — Python was the more familiar/taught language for this team.

**Decision — environment variables for DB config, not hardcoded values:** `get_db_connection()` reads `DB_HOST`, `DB_USER`, etc. via `os.environ.get(...)` with local-dev fallbacks. This is what allows the exact same code to work unmodified on: your laptop (`DB_HOST=localhost`), inside Docker Compose (`DB_HOST=db`), and later possibly anywhere else — a core "12-factor app" DevOps principle, without needing to name-drop that term in viva.

**Decision — `host="0.0.0.0"` in `app.run()`:** Binding only to `127.0.0.1` would make the server invisible to anything outside its own container later. `0.0.0.0` was set from the very first version of the code specifically so Dockerizing it later (Step 8) would need zero changes.

---

## Step 4 — Pets API

**What:** `get_pets()` (list/search), `get_pet(id)`, `add_pet()`, `update_pet_status()`.

**Decision — species filter via query string (`?species=Dog`)** rather than separate routes per species — one route, one SQL branch, matches the PDF's required search-by-species feature without extra endpoints.

---

## Step 5 — Users + Adoption Requests API (first version)

**What:** `register_user()`, `login_user()`, `create_adoption_request()`, `get_user_requests()`, `get_shelter_requests()`, `update_request_status()`.

**Decision (later revised in Step 5b):** Initial login had no token — the frontend was just going to remember a plain `user_id`. This was intentionally simple at first, then upgraded once real authorization concerns came up (see below).

---

## Step 5b — JWT Authentication & Authorization (upgrade)

**What:** Added `token_required()` decorator, `register_shelter()`/`login_shelter()`, and rewired every protected route to pull `user_id`/`shelter_id`/`role` from the decoded JWT instead of from the request body or URL.

**Why this changed:** The original design let a client pass any `user_id` in the URL or body (e.g. `GET /api/adoption-requests/user/5`). That meant anyone could view **anyone else's** adoption requests just by changing a number in the URL — a real vulnerability class called **IDOR (Insecure Direct Object Reference)**. Switching to JWT-derived identity closes this: the server now trusts only what it verified via the token's signature, never what the client claims about itself.

**Decision — no separate sessions table / server-side session store:** JWTs are stateless — the server verifies a signature instead of looking up a session in the database on every request. Simpler infrastructure, one less thing to keep synchronized, and there's no requirement in this project for revoking sessions early.

**Decision — passwords hashed with `werkzeug.security` (bundled with Flask), not a separate `bcrypt` package:** Same security property (one-way hash, per-password salt), zero extra dependency.

**Trade-off acknowledged (say this honestly in viva if asked):** Tokens are not revocable before their 6-hour expiry, and there's no refresh-token flow. Deliberately left out to keep the project at "easy-to-mid" difficulty — a valid enhancement to mention if pushed on it.

---

## Step 6 — Image Upload

**What:** `allowed_file()`, `upload_pet_image()`, `get_pet_image()`, plus `UPLOAD_FOLDER`/`ALLOWED_EXTENSIONS` config and `os.makedirs(..., exist_ok=True)`.

**Decision — whitelist of extensions (`png`, `jpg`, `jpeg`, `gif`) instead of trusting the browser's claimed file type:** Basic upload security — never trust client-supplied metadata.

**Decision — `secure_filename()` from Werkzeug:** Prevents path-traversal filenames (e.g. `../../etc/passwd`) from escaping the intended upload folder.

**Why this step matters most for viva:** the `uploads/` folder is **not** part of the Docker image — it's created at runtime and, from Step 10 onward, backed by a named Docker volume. If a container is deleted without its volume, uploaded photos are lost; if the volume is kept, they survive. This is deliberately the same "professor deletes something live" scenario DevOps evaluations often probe.

---

## Step 7 — Frontend

**What:** `index.html`/`pets.js` (browse+search), `pet-details.html`/`pet-details.js` (view+request), `login.html`/`register.html`/`auth.js`, `my-requests.html`/`requests.js`, `admin.html`/`admin.js`, shared `api.js` and `style.css`.

**Decision — plain HTML/CSS/JS, no framework (React/Vue):** Keeps the "app" layer simple enough that any of the 4 teammates can read and explain every line, since the framework itself isn't what's being graded — the DevOps pipeline around it is.

**Decision — role-based route guards done client-side (`if (getRole() !== "shelter") redirect`)** in `admin.js`/`requests.js`, **on top of** the server-side JWT role checks already in the API. The client-side guard is just UX (don't show a shelter dashboard to a logged-out visitor); the *real* security boundary is server-side — worth stating explicitly in viva, since UI-only restrictions are trivially bypassed.

**Design decision — visual redesign:** Initial CSS was bare-minimum. Looked at [adopt-a-pet.in](https://www.adopt-a-pet.in/) for design language only (not copying content/images) and adopted: a warm mustard/gold navbar, cream page background, bold rounded "Baloo 2" display font (Google Fonts) for headings, red pill-shaped buttons, and a soft yellow "hero" band behind page titles.

---

## Step 8 — Dockerize the Backend

**What:** `app/backend/Dockerfile` — `python:3.11-slim` base, install `requirements.txt` first (before copying the rest of the code) for build-cache efficiency, `EXPOSE 5000`, `CMD ["python", "app.py"]`.

**Decision — copy `requirements.txt` before the rest of the code:** Docker caches each instruction as a layer. If only `app.py` changes later, Docker skips re-running `pip install` entirely and rebuilds in seconds — a genuinely useful thing to demonstrate live if asked.

**Decision — kept Flask's built-in dev server (not `gunicorn`) inside the container:** A production WSGI server is the "correct" real-world choice, but adds a second thing to configure and explain for marginal benefit at this project's scale. Documented here as a known, deliberate simplification (matches the "easy-to-mid" difficulty target) rather than an oversight.

---

## Step 9 — Dockerize the Frontend

**What:** `app/frontend/Dockerfile` — `nginx:alpine` base, `COPY . /usr/share/nginx/html`, `EXPOSE 80`.

**Decision — nginx serving static files directly, no reverse proxy to the backend:** Considered adding an nginx reverse-proxy config so the frontend could call `/api/...` on its own origin. Rejected in favor of the simpler option already half-built: the frontend calls the backend **directly** on port 5000 using CORS (already set up in Step 3 via `flask-cors`). This avoids introducing nginx config complexity for a marginal benefit, at the cost of needing port 5000 open on the firewall too (handled in Terraform, Step 13).

**Decision — `api.js`'s `API_BASE_URL` changed from a hardcoded `"http://localhost:5000"` to a dynamic value:**
```javascript
const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:5000`;
```
**Why:** the old hardcoded value would have silently broken the moment the site was opened from the GCP VM's public IP — the browser would still try to reach `localhost:5000`, i.e. the *viewer's own machine*, not the server. Deriving the hostname dynamically means the exact same code works unmodified on `localhost` during development and on the VM's public IP after deployment.

---

## Step 10 — Docker Compose (`docker-compose.yml`)

**What:** Three services — `db` (MySQL 8.0), `backend` (Flask), `frontend` (nginx) — wired together, plus two named volumes: `mysql_data` and `pet_images`.

**Decision — `pet_images` volume mounted at `/app/uploads` in the backend container:** This is the concrete fix for the "uploads folder disappears" problem flagged in Step 6. Without this volume, deleting/recreating the backend container would wipe every uploaded pet photo. With it, photos survive `docker compose down` (but **not** `docker compose down -v`, which explicitly removes volumes too) — a live, demonstrable distinction between a container's disposable filesystem and a volume's persistent one.

**Decision — MySQL's schema auto-loaded via `docker-entrypoint-initdb.d`:** Mounting `schema.sql` into that special MySQL image folder means the tables are created automatically the very first time the `db` container starts, with no manual `mysql` command needed.

**Decision — removed the `3306:3306` port mapping on the `db` service (see incident below).**

**Decision — no `.env` file; DB password inlined directly in `docker-compose.yml` as `password`:** A real production setup would externalize this into a `.env` file or a secrets manager. Left inline here deliberately to avoid adding another moving part for a project of this scope — flagged as a known "if this were production" simplification, same spirit as Step 8's Flask-dev-server decision.

**Incident during testing:** First `docker compose up --build -d` failed with:
```
Error response from daemon: ports are not available: exposing port TCP 0.0.0.0:3306 -> 127.0.0.1:0: listen tcp 0.0.0.0:3306: bind: Only one usage of each socket address...
```
**Cause:** port 3306 was already in use on the host machine (likely a local MySQL installation).
**Fix:** removed the `ports: ["3306:3306"]` mapping from the `db` service entirely. The backend never needed to reach MySQL from *outside* Docker — it talks to `db:3306` over Docker's internal network regardless of any host port mapping. Removing it also means MySQL is never exposed outside the Docker network at all, which is a better security posture once this is deployed to a public GCP VM (nothing to consider "should this firewall port be open" for a database that's never meant to be public).

---

## Step 11 — Full Local Test (verified end-to-end)

**What was actually run and confirmed working, in order:**

1. `docker compose up --build -d` — built and started all 3 containers.
2. `docker compose ps` confirmed all 3 (`db`, `backend`, `frontend`) reached `Up` status with correct port bindings (`0.0.0.0:5000->5000`, `0.0.0.0:80->80`; `db` has no host port, by design — see Step 10).
3. Full API flow tested via `curl` against the running containers:
   - Registered a shelter (`Happy Paws Shelter`) → got a `shelter_id`
   - Logged in as that shelter → received a JWT
   - Added a pet (`Bruno`, Dog) using that JWT → pet created with `status: Available`
   - Registered an adopter (`Rahul Sharma`) → got a `user_id`
   - Logged in as that adopter → received a JWT
   - Submitted an adoption request for Bruno → pet automatically flipped to `status: Pending`
   - Confirmed via `GET /api/adoption-requests/my-requests` (as the adopter) that the request appeared
   - Logged back in as the shelter, called `GET /api/adoption-requests/shelter-requests` → saw Rahul's pending request
   - Approved it via `PUT /api/adoption-requests/1` → pet automatically flipped to `status: Adopted`
4. **Volume persistence test:** ran `docker compose down` (removes containers, keeps volumes) followed by `docker compose up -d` — all 3 containers were fully recreated from scratch, yet `GET /api/pets` still returned Bruno with `status: Adopted` intact. This is the concrete, demonstrated proof of the `mysql_data` volume lesson from Step 10: **container recreated, data survived**, because the data lived in a volume, not in the container's own filesystem.
5. Opened `http://localhost` in a browser and visually confirmed the homepage renders Bruno's card correctly with the "Adopted" status badge, proving the frontend container (nginx) successfully reaches the backend container using the dynamic `API_BASE_URL` from Step 9 — no hardcoded `localhost:5000` was needed for this to work across containers.

**Known incident, encountered and fixed live during this step:** a leftover standalone container from the Step 8 single-container test (`happy_fermat`, still holding port 5000) blocked Compose from starting the `backend` service the first time. Fixed with `docker stop happy_fermat`, then `docker compose up -d --force-recreate backend frontend` to force those two services to pick up the now-free port (Compose does not automatically retry a port bind on a container it already created without one).

---

## Step 12 — Push Everything to GitHub

**What:** Final commit of Docker files, `docker-compose.yml`, the redesigned frontend, this log, and the updated `README.md`.

```bash
git add .
git commit -m "Add Docker Compose setup, Dockerfiles, and full documentation"
git push
```

---

## Step 13 (UX fixes, post-testing) — Admin dashboard corrections

Found while actually using the deployed local stack (you had already started testing it yourself — a second shelter account and pet "tommy" with a real photo showed up in the data, which is how this was caught):

**Issue 1 — Shelters could see "Request to Adopt" on pet-details:** A logged-in shelter/admin account had no business requesting to adopt a pet. Fixed in `pet-details.js`: the button is now only rendered when `getRole() !== "shelter"`; shelters instead see a plain message. The server already rejected such a request via the `role != "user"` check in `create_adoption_request()` — this just makes the UI match what the API already enforced, instead of showing a button that would only fail after clicking it.

**Issue 2 — "Add New Pet" and "Manage Requests" crammed onto one page:** Split into two: `admin.html` (adoption requests only) and a new `add-pet.html` (+ `add-pet.js`) for adding pets and uploading photos. Reasoning: these are two distinct shelter tasks done at different times — bundling them made the dashboard feel cluttered and made per-feature explanation harder for the "4 people explaining their piece" goal.

**Issue 3 — Approved/rejected requests stayed clickable:** The real bug: `get_shelter_requests()` returned *every* request regardless of status, so an already-`Approved` request still rendered with live Approve/Reject buttons — clicking Reject on it afterward would silently flip the pet's status back to `Available` even though it was already adopted. Fixed two ways:
1. **Backend:** `WHERE ... AND ar.status = 'Pending'` added to the query — acted-upon requests simply stop being returned.
2. **Frontend:** `respondToRequest()` now disables both buttons on the specific card immediately (before the network call resolves) and removes that card from the DOM as soon as the response comes back, instead of only relying on a full list reload. Belt-and-suspenders: even a slow network can't create a window for a double-click.

**Addition — Adopted / Not Adopted filter:** Added a second dropdown next to the species filter on the browse page. Implemented as a new `?adopted=yes|no` query parameter on `GET /api/pets` (combinable with `?species=`), rather than a client-side-only filter, so the same filtering logic could later be reused by other clients (e.g. a future mobile app) without duplicating logic in JavaScript.

---

## Commands Reference (everything used so far)

```bash
# Git
git init
git add .
git commit -m "..."
git branch -M main
git remote add origin <url>
git push -u origin main

# Local backend test (pre-Docker)
cd app/backend
pip install -r requirements.txt
python app.py

# Docker — single container
docker build -t pet-adoption-backend .
docker run -p 5000:5000 pet-adoption-backend
docker images
docker ps
docker ps -a

# Docker Compose — full stack
docker compose up --build -d
docker compose ps
docker compose logs backend
docker compose down          # stops containers, KEEPS volumes (photos/DB survive)
docker compose down -v       # stops containers, DELETES volumes (photos/DB lost)
```
