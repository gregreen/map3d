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

## 1. Launch the instance

In EC2 → **Launch instance**:

| Setting | Value |
|---|---|
| AMI | Ubuntu 24.04 LTS, **arm64** |
| Type | `t4g.large` (2 vCPU, 8 GiB). Page cache matters more than CPU. |
| Storage (root) | 30 GB gp3 |
| Security group | inbound 80 and 443 from `0.0.0.0/0`, 22 from your address (or none, using SSM) |
| IAM role | one with `AmazonSSMManagedInstanceCore`, so you can use Session Manager instead of SSH |

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

Caddy obtains a certificate as soon as DNS resolves and port 80 is reachable. Watch it:

```bash
docker compose -f docker/docker-compose.yml logs -f caddy | grep -i certificate
```

## 6. Verify

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

## 7. Day-2 operations

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

## 8. Sizing and cost

| Item | Default | Notes |
|---|---|---|
| `t4g.large` | 2 vCPU, 8 GiB | Random reads hit the page cache first; more RAM beats more CPU. |
| 150 GB gp3, 6000 IOPS | | IOPS are the real bottleneck for cold reads. |
| Elastic IP | | Free while attached to a running instance. |
| Data transfer | | Responses are small and compressed. |

Expect tens of dollars a month. `c7g.large` (non-burstable, same size) is the calm upgrade
if CPU credits run out.

## 9. When one instance is not enough

1. Put CloudFront in front for `/static/*` — the stamp images and JS are cacheable.
2. Move to an ALB + ACM + an Auto Scaling Group. The app is stateless apart from SQLite,
   so rate limiting and statistics have to move to Postgres or be replaced by ALB/WAF
   rules.
3. Keep the map data on per-AZ volumes derived from a snapshot; EFS is too slow for mmap.

## 10. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/readyz` 503 with "data directory missing" | the volume is not mounted; check `/etc/fstab` and `mount -a` |
| `/readyz` OK but queries answer 503 "data not available" | a map is missing from the volume; run `scripts/fetch_maps.py --map NAME` with the volume writable |
| Slow queries, high `iowait` | cold page cache: more RAM, more IOPS, or a lower `MAP3D_MAX_SAMPLES` |
| `Warning: this map has not been repacked` in the logs | run `scripts/fetch_maps.py --map NAME` to repack it in place |
| Certificate not issued | DNS is not pointing at the Elastic IP, or port 80 is blocked |
| 429s for a legitimate user | have them batch coordinates, or raise `MAP3D_RATE_LIMIT_API_REQUESTS` / `_WORK` |
| gunicorn worker timeouts on huge requests | lower `MAP3D_MAX_OUTPUT_VALUES` |
