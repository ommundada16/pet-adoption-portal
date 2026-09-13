# How To Run This Project

A practical, copy-paste reference for running this project — locally, and on AWS. For *why* things are built this way, see [PROJECT_LOG.md](PROJECT_LOG.md). For diagrams, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Prerequisites

| Tool | Needed for | Install |
|---|---|---|
| Docker Desktop | Running locally | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Terraform | Creating the AWS server | `winget install --id Hashicorp.Terraform -e --source winget` |
| AWS CLI | Talking to your AWS account | `winget install --id Amazon.AWSCLI -e` |
| WSL (Ubuntu) + Ansible | Configuring/deploying to the server | `wsl --install -d Ubuntu`, then inside it: `sudo apt update && sudo apt install -y ansible` |
| Git | Version control | Usually already installed |

**Note on Ansible + Windows:** Ansible has no official support running directly on Windows as a control machine — all `ansible`/`ansible-playbook` commands in this guide must run inside WSL. Terraform and the AWS CLI run fine natively on Windows.

---

## A. Run It Locally (Docker Compose)

```bash
git clone https://github.com/ommundada16/pet-adoption-portal.git
cd pet-adoption-portal
docker compose up --build -d
```

Open:
- `http://localhost` — the app
- `http://localhost:5000/api/health` — backend health check

**Check status / logs:**
```bash
docker compose ps
docker compose logs backend --tail 50
```

**Stop it (keeps your data):**
```bash
docker compose down
```

**Full reset (wipes database + uploaded photos):**
```bash
docker compose down -v
docker compose up --build -d
```

**Rebuild after changing code** (e.g. edited `app.py` or a frontend file):
```bash
docker compose up -d --build backend frontend
```

---

## B. Deploy To AWS From Scratch

### 1. One-time AWS account setup
1. Create an IAM user (e.g. `terraform-deployer`) with the `AmazonEC2FullAccess` policy — **not root credentials**
2. Generate an access key for that user (Security credentials tab → Create access key → "Command Line Interface")
3. Configure your machine:
   ```bash
   aws configure
   # AWS Access Key ID: <paste>
   # AWS Secret Access Key: <paste>
   # Default region name: ap-south-1
   # Default output format: json
   ```
4. Confirm it worked:
   ```bash
   aws sts get-caller-identity
   ```

### 2. Generate an SSH key (one-time)
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/pet-adoption-key -N "" -C "ubuntu"
```
Terraform will inject the public half into AWS automatically — no manual key pair creation needed in the console.

### 3. Create the server with Terraform
```bash
cd terraform
terraform init
terraform plan
terraform apply
terraform output public_ip
```
Note the printed IP — you'll need it next.

### 4. Configure and deploy with Ansible (run from WSL)
```bash
wsl -d Ubuntu
```
Inside WSL:
```bash
cd /mnt/d/devops\ project/ansible   # adjust path to wherever your project sits on Windows

# copy the SSH key into WSL's own filesystem with correct permissions
# (Windows-mounted paths under /mnt/ don't preserve the strict permissions SSH requires)
cp /mnt/c/Users/<you>/.ssh/pet-adoption-key ~/.ssh_pet_key
chmod 600 ~/.ssh_pet_key
```
Edit `inventory.ini` and put the real IP in place of the placeholder, pointing at that copied key:
```
[web]
<EC2_PUBLIC_IP> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh_pet_key ansible_ssh_common_args='-o StrictHostKeyChecking=no'
```
Then:
```bash
ansible all -i inventory.ini -m ping         # should return "pong"
ansible-playbook -i inventory.ini deploy.yml
```

### 5. Verify it's live
```bash
curl http://<EC2_PUBLIC_IP>/
curl http://<EC2_PUBLIC_IP>:5000/api/health
```
Or just open `http://<EC2_PUBLIC_IP>` in a browser.

---

## C. Redeploy After A Code Change

```bash
git add .
git commit -m "your change"
git push
```
Then, from WSL:
```bash
cd /mnt/d/devops\ project/ansible
ansible-playbook -i inventory.ini deploy.yml
```
This re-clones the latest code from GitHub onto the server and re-runs `docker compose up --build -d` — safe to run again even if nothing changed.

---

## D. Checking On The Live Server

```bash
ssh -i ~/.ssh/pet-adoption-key ubuntu@<EC2_PUBLIC_IP>
cd pet-adoption-portal
docker compose ps
docker compose logs backend --tail 50
```

---

## E. Tearing Down (after faculty verification, to stop AWS charges)

```bash
cd terraform
terraform destroy
```
Type `yes` to confirm. This deletes the EC2 instance and security group entirely. To bring it back later, just run `terraform apply` again (you'll get a new public IP — update `inventory.ini` and re-run Ansible).

---

## Quick Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `port is already allocated` on `docker compose up` | Another container or local service is already using that port | `docker ps` to find it, `docker stop <name>`, then retry |
| `Bind for 0.0.0.0:3306 failed` | A local MySQL install is already using port 3306 | Not an issue for us — we deliberately don't expose MySQL's port at all |
| SSH `Permission denied (publickey)` | Wrong key path, or key permissions too open (common with Windows-mounted paths in WSL) | Copy the key into WSL's native filesystem and `chmod 600` it |
| `terraform apply` fails with `InvalidParameterCombination... Free Tier` | The instance type isn't free-tier eligible on this account/region | Run `aws ec2 describe-instance-types --filters "Name=free-tier-eligible,Values=true" --region ap-south-1` and use one of the listed types |
| Site loads but pets don't (frontend can't reach backend) | `API_BASE_URL` mismatch | Should auto-resolve via `window.location.hostname` — confirm you're accessing via the IP/domain, not `file://` |
| Fresh deploy shows no pets | Expected — a new server has a new, empty database | Register a shelter account and add pets to seed it |
