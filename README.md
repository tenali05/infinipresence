# infiniPresence

Face-scan and geofenced attendance, built as a Frappe app on top of Frappe HR (version-15).

- Employees check in and out from their phone browser. The phone's GPS must be inside the
  shift location's radius (Frappe HR already enforces this).
- infiniPresence adds a face check with liveness at check-in (planned).

## Layout
- `infinipresence/` the Frappe app (hooks, doctypes, API, frontend)
- `infinipresence/demo/` sample-data loaders: `bench --site <site> execute infinipresence.demo.setup.run`
  then `infinipresence.demo.data.run`
- `deploy/` Google Cloud VM deployment with auto-stop

## Licence
Proprietary. See license.txt.
