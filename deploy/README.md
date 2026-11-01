# Deploying infiniPresence to Google Cloud

One Compute Engine VM (`infinipresence-test`, London, e2-standard-2) runs Frappe +
ERPNext + Frappe HR + infiniPresence in Docker, behind Caddy for automatic HTTPS
(needed for camera and GPS in phone browsers).

- **Address:** `https://<ip-with-dashes>.sslip.io` (static IP, free wildcard DNS, no domain needed).
- **Auto-stop:** the VM stops itself 4 hours after every start (`--max-run-duration 4h
  --instance-termination-action STOP`). Cost is running hours plus the disk and reserved IP.
- **Start it again:** Google Cloud console (or the Google Cloud phone app) > Compute Engine >
  VM instances > `infinipresence-test` > Start. Or ask Claude. The site is back ~3 minutes later.
- **Continuous deploy:** the VM checks GitHub every 3 minutes and redeploys when the followed
  branch (`main` by default, instance metadata `app-branch`) has a new commit: rebuilds the app
  image (~1-2 min), restarts the containers and runs `bench migrate`. No laptop or SSH needed:
  push to GitHub (for example from a Claude session) and it goes live.
- **Logs:** the deploy log goes to the VM's serial console:
  `gcloud compute instances get-serial-port-output infinipresence-test --zone europe-west2-b`.

## Files
- `create-vm.sh` creates the static IP, firewall rule and VM.
- `startup.sh` is the VM startup script: installs Docker on first boot, installs the
  `infinipresence-update` command and its 3-minute timer, then deploys.
- `vm-deploy.sh` builds the images, starts the stack (`compose.yml`), creates or migrates the
  site, and loads the sample data once.
- `Dockerfile.app` adds this repo on top of the base image.
- `apps.json` lists the Frappe apps in the base image (ERPNext and HRMS, version-15); the
  infinipresence entry is skipped there because the app is layered separately.

## First boot
Takes ~30 minutes: the base image (Frappe, ERPNext, HRMS) is built once on the VM and reused.
