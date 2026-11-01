# Deploying infiniPresence to Google Cloud

One Compute Engine VM runs Frappe HR + ERPNext + infiniPresence in Docker,
behind Caddy for automatic HTTPS (needed for camera and GPS in phone browsers).

- The VM stops itself 4 hours after each start (`--max-run-duration`), so cost is
  running hours plus the disk.
- Start it again from the Google Cloud console (Compute Engine > VM instances > Start),
  or ask Claude.
- Address: `https://<ip-with-dashes>.sslip.io` (free wildcard DNS, no domain needed).

Files:
- `create-vm.sh` creates the VM, static IP and firewall rule.
- `startup.sh` runs on every boot: installs Docker on first boot, builds the image from
  `apps.json`, and starts the stack.
- `apps.json` lists the Frappe apps baked into the image.

Status: drafted, not yet run. Needs Google Cloud credentials in the environment (`GCP_SA_KEY`).
