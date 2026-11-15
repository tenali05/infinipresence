# infiniPresence Android app

The employee check-in app for Android (iOS later from the same code). It is a [Capacitor](https://capacitorjs.com)
app: a native Android shell with its own screens inside, talking to the infiniPresence Frappe site.

What employees can do: sign in or register, register their face (one photo, with consent), wait for approval,
then check in and out with a face scan plus their location. A wrong face or being outside the office radius is
refused by the server. They can also delete their account from the app.

## How it works
- **Screens** live in `src/` (`index.html`, `app.js`, `app.css`) and reuse the web page's styles
  (`infinipresence/public/css/presence.css`). They ship inside the app, so nothing loads from a website.
- **Face scan** uses the same open-source face-api library and models as the web page
  (copied from `infinipresence/public/vendor/face-api` at build time). The camera runs inside the app with a live preview.
- **Location** comes from the native Geolocation plugin (precise GPS, foreground only).
- **Sign-in:** `infinipresence.api.app_login` returns a personal API token, kept on the phone and sent as
  `Authorization: token ...` over native HTTPS. Signing in on another phone, signing out, or deleting the account
  replaces the token. System Manager accounts can't sign in to the app; they use `/presence/admin` in a browser.
- **Server address** is fixed at build time with `PRESENCE_SERVER` (default: the test server
  `https://34-39-66-44.sslip.io`). Build again after you move to a permanent domain.

## Building

### On GitHub (no setup on your laptop)
Every push that touches `mobile/` runs the **Android app** workflow (`.github/workflows/android.yml`).
Open the run in the repo's **Actions** tab and download **infinipresence-android**:
- `app-debug.apk`: install it straight on an Android phone to try the app.
- `app-release.aab`: the file for Google Play. It is signed if the signing secrets below are set.

To build for another server or version, use **Actions > Android app > Run workflow** and fill in the server,
`version_code` (must be higher than any upload before) and `version_name`.

Signing secrets (repo **Settings > Secrets and variables > Actions > New repository secret**):

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | the upload keystore as base64. In Windows PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("infinipresence-upload.jks")) \| Set-Clipboard` |
| `ANDROID_KEYSTORE_PASSWORD` | `storePassword` from keystore.properties |
| `ANDROID_KEY_ALIAS` | `upload` |
| `ANDROID_KEY_PASSWORD` | `keyPassword` from keystore.properties |

### On your own computer
Needs Node 22+, JDK 21 and Android Studio (for the Android SDK).
```
cd mobile
npm install
PRESENCE_SERVER=https://your-site npm run sync     # Windows PowerShell: $env:PRESENCE_SERVER="https://your-site"; npm run sync
cd android
./gradlew bundleRelease -PversionCode=2 -PversionName=1.0.1   # Windows: gradlew.bat ...
```
For a signed bundle, copy `android/keystore.properties.example` to `android/keystore.properties` and fill it in.
`npm run open` opens the project in Android Studio.

### Signing an unsigned bundle by hand
```
jarsigner -keystore infinipresence-upload.jks -signedjar app-release-signed.aab app-release.aab upload
```

## Upload key
The upload key is **not** in this repo. Keep `infinipresence-upload.jks` and its passwords backed up.
Google Play App Signing holds the real app signing key, so if the upload key is ever lost Google can reset it,
but that takes a few days.

## Icons and store graphics
`python3 scripts/make-icons.py` draws `assets/` (app icon, adaptive icon, splash) and `store/`
(512 px Play icon, 1024x500 feature graphic). `npm run assets` turns `assets/` into Android resources.

## Server-side pieces this app needs (in the Frappe app)
- `infinipresence.api.app_login`, `app_logout`, `delete_my_account`, and `check_in(..., source="android")`.
- The public privacy policy at `/presence/privacy`. Set who runs the service with
  `bench --site <site> set-config infinipresence_privacy_org "Your company"` and
  `bench --site <site> set-config infinipresence_privacy_contact "privacy@yourcompany.com"`.
