# infiniPresence on top of the Frappe + ERPNext + HRMS base image built by vm-deploy.sh.
FROM infinipresence-base:v15

USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:0 . apps/infinipresence

# Install the app and expose its public/ folder as /assets/infinipresence.
# Built assets live in /home/frappe/frappe-bench/assets (see frappe_docker's
# layered image); sites/assets is linked to it only while building.
RUN env/bin/pip install --no-cache-dir -e apps/infinipresence
RUN grep -qx infinipresence sites/apps.txt || echo infinipresence >> sites/apps.txt
RUN ln -sfn /home/frappe/frappe-bench/assets sites/assets \
  && (bench build --app infinipresence \
      || ln -sfn /home/frappe/frappe-bench/apps/infinipresence/infinipresence/public assets/infinipresence) \
  && rm -f sites/assets
