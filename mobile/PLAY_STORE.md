# Publishing infiniPresence on Google Play

What is ready in this repo: the signed release bundle (`app-release.aab`, built by the Android app workflow),
the privacy policy page (`/presence/privacy`), in-app account deletion, the 512 px icon, the feature graphic and
two screenshots in `store/`. The steps below are the ones only you can do.

## 0. Before you submit: a server that stays on
Google's reviewers open the app and sign in. The test server stops itself after 4 hours and has an IP-style
address (`34-39-66-44.sslip.io`), so:
1. Give the server a proper domain (for example `attendance.yourcompany.com`) and keep it running while the app
   is in review and in use.
2. Build the app for that address: **Actions > Android app > Run workflow**, server `https://attendance.yourcompany.com`,
   version code `2` (or higher).
3. Set who runs the service, so the privacy policy names you:
   `bench --site <site> set-config infinipresence_privacy_org "Your company"` and
   `bench --site <site> set-config infinipresence_privacy_contact "privacy@yourcompany.com"`.

You can still do steps 1 to 4 below with the test server while you sort this out.

## 1. Developer account (about 30 minutes, then a wait for verification)
- Sign up at https://play.google.com/console/signup and pay the one-time **US$25** fee.
- Choose **Personal** or **Organization**.
  - **Organization** needs a D-U-N-S number for your company (free, can take a couple of weeks), but it
    **skips** the 12-tester rule below.
  - **Personal** is faster to open, but a new personal account must run a **closed test with at least 12 testers
    for 14 days in a row** before it can publish to everyone.
- Verify your identity and a phone number when asked.

## 2. Create the app
Play Console > **Create app**: name `infiniPresence`, default language, **App**, **Free**, accept the declarations.
The package name is `com.infinipresence.app`. It is fixed for ever once you upload the first bundle.

## 3. App content (Policy > App content)
- **Privacy policy:** `https://<your-site>/presence/privacy`
- **App access:** "All or some functionality is restricted". Give the reviewers a working login:
  an approved test employee (email + password), assigned to an office with a very large radius
  (for example 20,000,000 m), so their check-in isn't refused for being far away. Say in the notes:
  "Sign in, allow camera and location, tap Check in while facing the camera."
- **Ads:** No.
- **Content rating:** fill in the questionnaire (utility app, no user-generated content shared publicly). Expect "Everyone".
- **Target audience:** 18 and over.
- **Data safety:** answer like this:
  - Data is collected: **Yes**. Shared with third parties: **No**. Encrypted in transit: **Yes**.
    Users can request deletion: **Yes**.
  - Personal info > **Name**, **Email address**: collected, required, purpose *Account management*.
  - Location > **Precise location**: collected, required, purpose *App functionality*.
  - Photos and videos > **Photos**: collected, required, purpose *App functionality* (face check-in photos).
  - Personal info > **Other info**: collected, required, *App functionality* (the face measurement used to
    confirm identity). Mention "face data used only to verify the employee at check-in" where there is a text box.
- **Account deletion:** link `https://<your-site>/presence/privacy` (its "Deleting your account" section explains
  the in-app button, the web option and what is kept).
- **Location permission:** the app uses location only in the foreground, so no special declaration is needed.

## 4. Store listing (Grow > Store presence > Main store listing)
- **Short description** (80 chars max):
  `Check in and out at your office with a quick face scan and your location.`
- **Full description:**
  > infiniPresence is the attendance app for teams that use infiniPresence at work.
  >
  > • Sign in with the account your employer set up, or register and wait for approval.
  > • Register your face once.
  > • Check in and out at your office: the app confirms it's you with a face scan and checks you're within your office's radius.
  > • See today's check-ins at a glance.
  >
  > Your face data is used only to confirm it's you when you check in. Location is used only while the check-in
  > screen is open. You can delete your account and face data from the app at any time.
  >
  > An infiniPresence account from your employer is required.
- **App icon:** `store/play-icon-512.png`. **Feature graphic:** `store/feature-graphic-1024x500.png`.
- **Phone screenshots:** at least 2. `store/screenshots/` has the sign-in and pending screens. For the check-in
  screens, take your own on your phone (use your own face, not the sample photo used in testing).
- **Category:** Business. Contact email: yours.

## 5. Closed test (personal accounts: 12 testers, 14 days)
1. **Test and release > Testing > Closed testing > Create track**. Upload `app-release.aab`.
2. Add testers: create a Google Group or an email list with **at least 12** people who use Android.
   Real employees are ideal: they need accounts on your server and an office assigned.
3. Send them the opt-in link from the track page. Each tester must accept and install the app.
4. Keep at least 12 testers opted in for **14 days in a row**. Ask them to open the app now and then;
   Google asks about tester engagement afterwards.
5. Then **Dashboard > Apply for production** and answer the questions about the test.

Organization accounts can go straight to **Production > Create new release** after the app content is done
(an internal test first is still a good idea).

## 6. Each later update
Build with a higher version code (**Run workflow**, `version_code` = last + 1), then upload the new `.aab` to the track.
Google refuses a bundle whose version code it has seen before.
