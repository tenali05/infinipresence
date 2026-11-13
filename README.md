# infiniPresence

Face-scan and geofenced attendance, built as a Frappe app on top of Frappe HR (version-15).

- Employees check in and out from their phone browser. The phone's GPS must be inside the
  shift location's radius (Frappe HR already enforces this).
- infiniPresence adds a face check with liveness at check-in (planned).

## Phase 1: web app (works on phones, can be added to the home screen)
- **Employees** open `/presence`: sign in with email or Google, or register. They take one face photo,
  then wait for an admin. Once approved, each check-in or check-out needs the phone's location to be
  inside their office radius and a face scan that matches the registered photo.
  Check-ins are saved as standard Frappe HR *Employee Checkin* records (with the photo attached),
  so Frappe HR's shift and attendance processing keeps working.
- **Admins** (role *Presence Manager* or *System Manager*) open `/presence/admin` to approve sign-ups,
  assign each person to an office, add offices, and see who was present for any date range (CSV download).
- Employees are website users: they never see the Frappe desk. Admins can be given the
  *infiniPresence Admin* module profile, which hides every desk module except HR and setup.
- Nothing in Frappe, ERPNext or Frappe HR is modified: everything is in this app, so upstream updates
  can be pulled as usual.

Face matching runs in the browser with the open-source face-api library (vendored under
`public/vendor/face-api`, MIT licence); the server compares the result with the registered face.
Tune the match strictness with `bench --site <site> set-config infinipresence_face_threshold 0.45`
(lower is stricter, default 0.5).

### Turning on "Continue with Google"
1. In Google Cloud console > APIs & Services > Credentials, create an *OAuth client ID* (Web application).
   Authorised redirect URI: `https://<your-site>/api/method/frappe.integrations.oauth2_logins.login_via_google`
2. In the desk, open *Social Login Key* > New > Social Login Provider: Google. Paste the client ID and
   secret, set Base URL to `https://<your-site>`, tick *Enable Social Login*, set *Sign ups* to Allow.
The Google button then appears on `/presence`.

## Layout
- `infinipresence/` the Frappe app (hooks, doctypes, API, frontend)
- `infinipresence/demo/` sample-data loaders: `bench --site <site> execute infinipresence.demo.setup.run`
  then `infinipresence.demo.data.run`
- `deploy/` Google Cloud VM deployment with auto-stop

## Licence
Proprietary. See license.txt.
