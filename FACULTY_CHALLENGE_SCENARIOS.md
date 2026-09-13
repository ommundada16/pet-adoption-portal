# Faculty "Live Change" Scenarios

Faculty evaluating DevOps projects often don't just watch a demo — they break something live and ask you to explain or fix it, to check you actually understand the system instead of having memorized a script. This document lists the scenarios most likely to come up, what actually happens, and exactly how to respond.

Read this the night before viva. If sir does something not listed here, the general approach is always: **stay calm, explain what you'd check first, and use the relevant command from [PROJECT_LOG.md](PROJECT_LOG.md)'s command reference.**

---

## 1. "Delete the uploaded pet images and show me what happens"

**What they might do:** delete files from inside the container, or run `docker compose down -v` (which deletes volumes).

**What actually happens:**
- If they delete files *from inside a running container* (`docker exec backend rm -rf /app/uploads/*`) — the volume itself still exists, but its contents are gone. Photos disappear from the site immediately, `image_filename` in MySQL still points to a file that no longer exists (broken image icon).
- If they run `docker compose down -v` — this removes the volumes entirely, meaning MySQL data *and* photos are both gone. A fresh `docker compose up -d` starts a completely empty system.

**How to respond:**
> "This shows the difference between a container and a volume. The photo files live in a Docker volume specifically so they survive a container restart — but a volume can still be deleted directly, or wiped along with `-v`. In production you'd want a backup strategy for volumes; we didn't implement one since it's out of scope for this project, but I can explain what that would look like: periodic `docker run --rm -v pet_images:/data -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz /data` style snapshots, or storing images in cloud object storage (like S3) instead of a local volume."

**Fix (make it work again):**
```bash
# If just files were deleted but the pet rows still exist:
# re-upload photos via the "My Pets" page - the app handles it normally

# If -v was run (full wipe):
docker compose up --build -d
# system is now empty and functional - re-register accounts and re-add pets to demo again
```

---

## 2. "Stop/kill one of the containers"

**What they might do:** `docker stop pet-adoption-backend` or kill the container's process.

**What actually happens:** Because `docker-compose.yml` sets `restart: unless-stopped` on every service, Docker itself will usually restart it automatically within seconds.

**How to respond:**
> "We set `restart: unless-stopped` in our compose file specifically so a crashed or manually-stopped container comes back automatically without us intervening. If it doesn't restart, it's because it was stopped deliberately with `docker stop`, which Docker respects as intentional — running `docker compose up -d` brings it back."

**Fix:**
```bash
docker compose ps          # confirm which container is down
docker compose up -d       # brings any stopped service back
docker compose logs backend --tail 50   # check why it crashed, if it did
```

---

## 3. "Change a pet's status directly in the database"

**What they might do:** `docker exec -it <db-container> mysql -u root -p` then manually `UPDATE pets SET status='Adopted' WHERE pet_id=1;`

**What actually happens:** The frontend reflects it immediately on next page load/refresh, since it always reads live from MySQL — there's no caching layer.

**How to respond:**
> "Our frontend never caches data — every page load calls the API fresh, which queries MySQL directly. So a direct database change shows up immediately on refresh, which is expected behavior, not a bug."

---

## 4. "Stop or terminate the EC2 instance"

**What they might do:** stop the instance from the AWS Console, or ask you to.

**What actually happens:** The site becomes completely unreachable (connection refused/timeout).

**How to respond and fix:**
```bash
# If just STOPPED (not terminated):
# restart it from the AWS Console, or:
aws ec2 start-instances --instance-ids <instance-id>
# wait ~30s, then containers should already be running if Docker's own
# restart policy + the VM's own boot process brought them back
# (note: our current setup does NOT have a systemd service auto-starting
# docker compose on VM boot - mention this honestly if it comes up)

ssh -i ~/.ssh/pet-adoption-key ubuntu@<ip>
cd pet-adoption-portal && docker compose up -d

# If TERMINATED (fully deleted):
cd terraform
terraform apply             # creates a brand new instance, new public IP
terraform output public_ip  # get the new IP
# update ansible/inventory.ini with the new IP, then:
cd ../ansible
ansible-playbook -i inventory.ini deploy.yml
```

**Good honest answer if asked "does it come back automatically on VM reboot":**
> "Not fully automatically right now — Docker's own restart policy brings containers back if the Docker daemon restarts, but if the whole VM reboots we currently SSH in and run `docker compose up -d` manually. A production setup would add a systemd service or `docker` itself enabled to start on boot — that's a valid improvement we'd make with more time."

---

## 5. "Remove the firewall rule for port 80" (or block a port)

**What they might do:** edit the security group in the AWS Console to remove the port 80 rule.

**What actually happens:** The site becomes unreachable, but the containers themselves are still running fine on the server — this is purely a network-access issue, not an application issue.

**How to respond:**
```bash
cd terraform
terraform plan
```
**Expected output:** shows a diff — Terraform detects the security group in AWS no longer matches what's defined in `main.tf` (this is called **configuration drift**).

> "This is exactly why Infrastructure as Code matters — someone changed our infrastructure outside of Terraform, and `terraform plan` immediately shows the drift. Running `terraform apply` restores it to match our code."

```bash
terraform apply
```

---

## 6. "Add a new pet species, like Fish"

**What they might do:** ask you to extend the app live.

**What to actually do:**
1. Edit `app/backend/schema.sql` — add `'Fish'` to the `species` ENUM in the `pets` table (note: an existing live database needs an `ALTER TABLE` since `schema.sql` only runs on first creation)
2. Edit the species `<select>` dropdowns in `app/frontend/index.html`, `admin.html`/`add-pet.html`, `my-pets.js`
3. Commit, push to GitHub
4. Re-run: `ansible-playbook -i inventory.ini deploy.yml` — this re-clones the latest code and rebuilds

> "This demonstrates our deployment is repeatable — any code change just needs a git push and one Ansible command to go live again."

---

## 7. "Why is the pet list empty right after a fresh deployment?"

**Expected — not a bug.** A brand-new EC2 instance gets a brand-new, empty MySQL database (the schema is created, but no rows exist yet). This is different from your local Docker Compose setup, which has its own separate database with whatever test data you added there.

> "Each environment has its own database. We'd populate this with real shelters/pets before a demo, the same way you'd seed any fresh production database."

---

## 8. "Try to edit another shelter's pet" (testing your security)

**What they might do:** log in as Shelter A, get Shelter B's pet ID from the browse page, and try `PUT /api/pets/<B's pet id>` via browser dev tools or curl.

**Expected result:** `403 Forbidden — "You can only update your own pets"`.

> "We specifically check pet ownership server-side before allowing any edit, delete, or photo upload — this was actually a real bug we found and fixed during development (see PROJECT_LOG.md, Step 13b), where any shelter could originally edit any other shelter's pets."

---

## 9. "What if two people request the same pet at the same time?"

**Honest answer:** our current logic doesn't lock against this — both requests would be created as `Pending`, and whichever the shelter approves first sets the pet to `Adopted`; the other request stays `Pending` forever (the shelter should reject it manually). This is a known simplification appropriate for the project's scope, not something we tried to hide.

---

## 10. "Roll back to a previous version of the code"

```bash
git log --oneline              # find the commit hash to roll back to
git checkout <commit-hash> -- .
git commit -m "Rollback to <commit-hash>"
git push
# then redeploy:
cd ansible && ansible-playbook -i inventory.ini deploy.yml
```

> "Because every change is a Git commit, rolling back is just checking out an older commit and redeploying — the same Ansible command handles both forward and backward changes."

---

## General Principle To State If Something Unexpected Breaks

> "Our deployment isn't magic — it's a documented, repeatable sequence: Terraform creates infrastructure, Ansible configures it, Docker Compose runs it. If something's broken, the fix is always to check which of those three layers is affected, and re-run the corresponding step — `terraform apply` for infrastructure drift, `ansible-playbook` for configuration/deployment issues, or `docker compose` commands for the running containers themselves."
