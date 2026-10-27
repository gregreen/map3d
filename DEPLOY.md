# Deploying on AWS

The service is one EC2 instance running two containers: `web` (gunicorn behind Caddy) and
`caddy` (TLS). The maps live on a separate gp3 EBS volume, mounted at `/srv/map3d/data`.

Why this shape:

* **Local disk for the maps.** Memory-mapped HDF5/FITS files must sit on a block device
  attached to the instance. EFS, or Fargate with EFS, would put network latency in the
  path of every query.
* **One instance.** Traffic comes from a modest number of research groups; a load
  balancer and an autoscaling group would cost more than they save. The path to them is
  at the end.
* **Caddy for TLS.** Certificates are obtained and renewed automatically, and HTTP
  redirects to HTTPS, with no certificate files to manage.

Everything below is done through the AWS console and `ssh`/SSM; there is no
infrastructure-as-code in this repository.

## 0. What you need

* An AWS account.
* A domain you control (e.g. `argonaut.skymaps.info`) with access to its DNS records.
* The data volume must hold ~55 GB, of which 20 GB is the Edenhofer 2023 sample file that
  the query page's posterior band is drawn from. A 150 GB volume leaves room for the stamp
  caches and for growth.
* Budget: ≈ $84/month while running, ≈ $33/month stopped (§11). Cap it *before* you launch
  by lowering the vCPU quota (§10) — that is what stops a forgotten instance from billing you
  indefinitely.

## 1. Launch the instance

In EC2 → **Launch instance**:

| Setting | Value |
|---|---|
| AMI | Ubuntu 24.04 LTS, **arm64** |
| Type | `t4g.large` (2 vCPU, 8 GiB). Page cache matters more than CPU. |
| Storage (root) | 30 GB gp3 |
| Security group | inbound 80 and 443 from `0.0.0.0/0`, 22 from your address (or none, using SSM) |
| IAM role | one with `AmazonSSMManagedInstanceCore`, so you can use Session Manager instead of SSH |
| Credit specification | **Standard**, under *Advanced details* — `t4g` otherwise runs in unlimited mode and bills burst CPU as surplus credits (§10) |

Point an `A` record for the site's hostname at the instance's public IP, and attach an
**Elastic IP** so it survives a stop/start.

## 2. Add the data volume

1. EC2 → **Volumes** → **Create volume**: gp3, 150 GB, **6000 IOPS**, same availability
   zone as the instance.
2. Attach it to the instance (`/dev/sdf`).
3. On the instance, format and mount it:

   ```bash
   sudo mkfs.ext4 /dev/nvme1n1          # check with lsblk first
   sudo mkdir -p /srv/map3d/data
   echo "UUID=$(sudo blkid -s UUID -o value /dev/nvme1n1) /srv/map3d/data ext4 defaults,nofail 0 2" \
     | sudo tee -a /etc/fstab
   sudo mount -a
   ```

## 3. Install Docker and the app

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"     # log out and back in
sudo mkdir -p /srv/map3d && sudo chown "$USER" /srv/map3d
git clone https://github.com/gregreen/map3d.git /srv/map3d/app
```

Write `/srv/map3d/app/.env` (see `.env.example` for every variable):

```bash
SITE_ADDRESS=argonaut.skymaps.info
ACME_EMAIL=you@example.org
```

If the domain's DNS is not pointing here yet, put a temporary address in `SITE_ADDRESS`
instead — see §6 — and set the real name at cutover.

`SITE_ADDRESS` and `ACME_EMAIL` are read by the Caddy container; every other setting,
including the log level and the dustmaps ref, is listed in `.env.example`. The data
volume defaults to `/srv/map3d/data`, so it needs setting only if you mounted it
somewhere else.

## 4. Populate the data volume

First boot downloads the maps (tens of GB, tens of minutes) and builds the postage-stamp
caches. Run it in a container that can write to the volume:

```bash
cd /srv/map3d/app
docker compose -f docker/docker-compose.yml build
MAP3D_DATA_MODE=rw docker compose -f docker/docker-compose.yml run --rm --no-deps web \
  sh -c 'python scripts/fetch_maps.py --all && python scripts/build_stamp_images.py --all'
```

Every dustmaps fetcher uses `clobber=False`, so this is a **no-op on a populated volume** —
redeploying never re-downloads maps.

If you already have the data elsewhere, copying it is far faster than downloading:

```bash
rsync -avP --info=progress2 ~/dustmaps_data/ you@<elastic-ip>:/srv/map3d/data/
```

The volume needs `dustmaps_data/images/` (the stamp caches) as well as the maps; the
command above builds it if it is missing.

## 5. Start the service

```bash
cd /srv/map3d/app
docker compose -f docker/docker-compose.yml up -d
```

Caddy obtains a certificate as soon as DNS resolves and port 80 is reachable (with no DNS
yet, use §6 first). Watch it:

```bash
docker compose -f docker/docker-compose.yml logs -f caddy | grep -i certificate
```

## 6. Testing without DNS

You do not need the A record until you cut over to the real hostname: the application
reads no configured hostname (and `sitemap.xml` uses relative URLs unless you set
`PUBLIC_BASE_URL`), so a temporary address is enough to exercise everything else. Two ways,
in order of usefulness.

**A real certificate from a name that needs no DNS administration.** [sslip.io](https://sslip.io)
resolves any IP written into the name, so Let's Encrypt will validate it and you get genuine
HTTPS — the full TLS path (ACME, the HTTP→HTTPS redirect, HSTS and the security headers)
before DNS exists:

```bash
# for an Elastic IP of 18.1.2.3 (the dotted form 18.1.2.3.sslip.io also resolves)
SITE_ADDRESS=18-1-2-3.sslip.io
```

```bash
cd /srv/map3d/app && docker compose -f docker/docker-compose.yml up -d
curl -s https://18-1-2-3.sslip.io/healthz
curl -s https://18-1-2-3.sslip.io/readyz
```

Requirements: an **Elastic IP** attached first (otherwise the address changes on every
stop/start and the certificate is invalidated), and ports 80/443 open to the world. Because
`dustmaps` needs only a base URL, this same hostname works for the API check in §7.

**Plain HTTP on the IP.** Simplest, and enough to validate the container, the maps and the
API, but it does not test TLS:

```bash
SITE_ADDRESS=:80
```

```bash
curl -s http://18.1.2.3/healthz
curl -s http://18.1.2.3/readyz
```

The site still sends `Strict-Transport-Security` from this response; harmless on a throwaway
test, but don't browse it from a profile you care about.

Whichever you pick, switching to production is two lines: set
`SITE_ADDRESS=argonaut.skymaps.info` in `/srv/map3d/app/.env`, point the A record at the
Elastic IP, then `docker compose -f docker/docker-compose.yml up -d` to recreate Caddy. Test
names are throwaway — do not leave a `sslip.io` address in `.env`, and if you reissue
certificates repeatedly while debugging, remember Let's Encrypt's rate limit of five
duplicate certificates per week.

## 7. Verify

```bash
curl -s https://YOUR_DOMAIN/healthz
curl -s https://YOUR_DOMAIN/readyz          # data directory, map count, stamp images
curl -s http://YOUR_IP/ | head -1           # should redirect to https
```

End to end, through `dustmaps`:

```bash
python - <<'EOF'
from astropy import units as u
from astropy.coordinates import SkyCoord
from dustmaps.bayestar import BayestarWebQuery

q = BayestarWebQuery(api_url="https://YOUR_DOMAIN/api/v2/")
c = SkyCoord(150*u.deg, 20*u.deg, distance=1*u.kpc, frame="galactic")
print(q(c, mode="best"))
EOF
```

## 8. Day-2 operations

| Task | How |
|---|---|
| Deploy a new version | `cd /srv/map3d/app && git pull && docker compose -f docker/docker-compose.yml up -d --build` |
| Roll back | `git checkout <previous-commit> && docker compose ... up -d --build` |
| Logs | `docker compose -f docker/docker-compose.yml logs -f web` |
| Add a map | Add the spec in `map3d/maps.py` and a fetcher in `scripts/fetch_maps.py`, then fetch it and rebuild the image |
| Rebuild stamp images | `MAP3D_DATA_MODE=rw docker compose ... run --rm --no-deps web python scripts/build_stamp_images.py --all --force` |
| Aggregate usage stats | `docker compose ... exec web flask --app wsgi stats-summary` |
| Export stats | `docker compose ... exec web flask --app wsgi stats-export --days 365 -o /tmp/usage.csv` |
| Refresh the GeoIP database (monthly) | `docker compose ... run --rm --no-deps --entrypoint python web scripts/update_geoip.py` |
| Back up | The only state is SQLite in the `map3d-state` volume: export the stats, or snapshot the root volume |

The service mounts the data volume **read-only**; anything that writes to it (fetching
maps, rebuilding stamps) needs `MAP3D_DATA_MODE=rw` as above.

## 9. Sizing and cost

| Item | Default | Notes |
|---|---|---|
| `t4g.large` | 2 vCPU, 8 GiB | Random reads hit the page cache first; more RAM beats more CPU. |
| 150 GB gp3, 6000 IOPS | | IOPS are the real bottleneck for cold reads. |
| Elastic IP | | Free while attached to a running instance. |
| Data transfer | | Responses are small and compressed. |

Expect tens of dollars a month — roughly $85/month, or about $1,000/year, broken down in
§11. `c7g.large` (non-burstable, same size) is the calm upgrade if CPU credits run out.

## 10. Capping the compute spend

EC2 bills per vCPU-hour, so the number of vCPUs that can be *running at once* sets the
ceiling. The enforcement point is the **On-Demand vCPU service quota**, which is checked at
launch: anything that would push the account over it is refused with
`VcpuLimitExceeded`, whether it comes from the console, the CLI, or a forgotten script in
another project.

A `t4g.large` is 2 vCPUs, so a quota of 2 vCPUs means exactly one instance of this size and
no second one anywhere in the region.

### Look at the current state

```bash
# what is running, and how many vCPUs each type holds
aws ec2 describe-instances \
  --filters Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].{Instance:InstanceId,Type:InstanceType}' \
  --output table

aws ec2 describe-instance-types --instance-types t4g.large \
  --query 'InstanceTypes[].{Type:InstanceType,vCPUs:VCpuInfo.DefaultVCpus,GiB:MemoryInfo.SizeInMiB}'

# the quota itself (On-Demand Standard covers every family whose type starts with
# A, C, D, H, I, M, R, T or Z, which includes the Graviton t4g)
aws service-quotas list-service-quotas --service-code ec2 \
  --query "Quotas[?contains(QuotaName,'On-Demand Standard')].{name:QuotaName,code:QuotaCode,value:Value}" \
  --output table
```

The quota for "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances" is
usually `L-1216C47A`; confirm it with the command above before using the code below.

### Lower it

Console: **Service Quotas → AWS services → Amazon Elastic Compute Cloud (Amazon EC2) →
Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances → Request quota increase**,
and enter `2`. Despite the menu name, a *decrease* is requested the same way.

```bash
aws service-quotas request-service-quota-increase \
  --service-code ec2 --quota-code L-1216C47A --desired-value 2

# it is a request, so check that it was applied
aws service-quotas get-service-quota --service-code ec2 --quota-code L-1216C47A \
  --query 'Quota.Value'
```

Decreases are normally approved within minutes. Things to know:

* **Per region.** Set it in every region you use, or a stray launch elsewhere is unconstrained.
* **Running vCPUs only.** A *stopped* instance holds no vCPU quota, so stop rather than
  terminate when you are done for the day; only the EBS volumes keep billing.
* **It cannot go below what is already running**, so stop the instance first if the request
  is rejected.
* **It also blocks unrelated launches** in that account and region — usually the point, but it
  will surprise anyone else using the account. Revisit it deliberately before adding the
  load balancer and autoscaling group of §12.
* **Spot is separate.** There is a different quota for Spot requests, so Spot capacity can
  still be launched; don't rely on this if Spot is in play.

### The three things the quota does *not* cap

| Risk | Bound it with |
|---|---|
| **Burstable CPU-credit surplus.** `t4g` defaults to *unlimited* mode: sustained CPU above the 40 % baseline is billed as surplus credits (~$0.05/vCPU-hour). This service is I/O-bound and should never exceed the baseline, but you can make it impossible: stop the instance, then **Actions → Instance settings → Change credit specification → Standard** (CLI: `--credit-specification CpuCredits=standard`), which throttles instead of charging. | Credit specification, plus a CloudWatch alarm on `CPUCreditBalance` |
| **EBS, Elastic IP and egress.** These bill with no instance running at all: ~$29/month for the two volumes and their IOPS, $3.65/month for the address, $0.09/GB out. Stopping the instance for a month still costs ~$33. | Delete the volume and address when done; see §11 for the totals |
| **Total spend.** The quota caps how many instances run, not how much the right one runs. | **AWS Budgets** with a monthly limit (e.g. $50), an email alert at 80 %, and an action that stops the instance if the threshold is passed |

If you need something stricter than a quota — "only this instance type, in this region, from
this account" — the tool is an IAM policy or an Organizations SCP with conditions on
`ec2:InstanceType` and `ec2:Region`. That is more machinery than a single-instance site
needs, but it is the only way to forbid, rather than merely cap, a launch.

## 11. What it costs

List prices for us-east-1, Linux/ARM, on-demand, checked October 2026. Check the
[calculator](https://calculator.aws/) before committing to a savings plan; other regions run
5-15 % higher.

| Item | Rate | Per month | Per year |
|---|---|---|---|
| EC2 `t4g.large`, 730 h | $0.0672/h | $49.06 | $588.67 |
| Data volume, 150 GB gp3 | $0.08/GB-month | $12.00 | $144.00 |
| Data volume, 3000 IOPS above the 3000 included | $0.005/IOPS-month | $15.00 | $180.00 |
| Root volume, 30 GB gp3 | $0.08/GB-month | $2.40 | $28.80 |
| Public IPv4 (the Elastic IP, while attached) | $0.005/h | $3.65 | $43.80 |
| Egress, ~20 GB/month | $0.09/GB | $1.80 | $21.60 |
| CloudWatch Logs, ~20 MB/month | $0.50/GB | $0.01 | $0.12 |
| Route 53 hosted zone, if DNS stays in AWS | $0.50/zone-month | $0.50 | $6.00 |
| **Total** | | **≈ $84** | **≈ $1,013** |

A one-year Compute Savings Plan (no upfront, ~28 % off the instance hour) takes about
$176/year off, for **≈ $840/year**. Snapshots, if you keep one, add ~$3/month for 60 GB of
changed blocks.

With the instance **stopped** — the state it sits in between test sessions — the bill is
≈ $33/month: the two volumes with their provisioned IOPS ($29.40) and the Elastic IP
($3.65). Everything else stops. That is the number to compare against keeping a local copy of
the maps and running the container on your own machine.

A **day-long test** of the same configuration costs about **$2.90**: $1.61 of instance time,
$0.39 + $0.49 for the data volume and its IOPS, $0.08 root, $0.12 address, $0.18 egress. The
cost of a test is not the dollars but the data — a fresh volume means downloading ~55 GB of
maps, so snapshot the volume (or seed it from S3) before terminating if you plan to repeat
the exercise.

Two lines dominate everything else: the instance hour (58 %) and the gp3 volume with its
provisioned IOPS (28 %). The 6000 IOPS is $180/year on its own; with 8 GiB of page cache the
baseline 3000 IOPS is a reasonable first try, which brings the year to ≈ $833.

## 12. When one instance is not enough

1. Put CloudFront in front for `/static/*` — the stamp images and JS are cacheable.
2. Move to an ALB + ACM + an Auto Scaling Group. The app is stateless apart from SQLite,
   so rate limiting and statistics have to move to Postgres or be replaced by ALB/WAF
   rules. Raise the vCPU quota of §10 at the same time, or the group cannot scale.
3. Keep the map data on per-AZ volumes derived from a snapshot; EFS is too slow for mmap.

## 13. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/readyz` 503 with "data directory missing" | the volume is not mounted; check `/etc/fstab` and `mount -a` |
| `/readyz` OK but queries answer 503 "data not available" | a map is missing from the volume; run `scripts/fetch_maps.py --map NAME` with the volume writable |
| Slow queries, high `iowait` | cold page cache: more RAM, more IOPS, or a lower `MAP3D_MAX_SAMPLES` |
| `Warning: this map has not been repacked` in the logs | run `scripts/fetch_maps.py --map NAME` to repack it in place |
| Certificate not issued | DNS is not pointing at the Elastic IP, or port 80 is blocked |
| 429s for a legitimate user | have them batch coordinates, or raise `MAP3D_RATE_LIMIT_API_REQUESTS` / `_WORK` |
| gunicorn worker timeouts on huge requests | lower `MAP3D_MAX_OUTPUT_VALUES` |
