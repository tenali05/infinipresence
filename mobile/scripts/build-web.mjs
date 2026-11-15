// Builds the app's web layer into www/: bundles src/app.js with the Capacitor plugins,
// and copies the page, styles, icons and the face scanner (shared with the Frappe app).
//
//   PRESENCE_SERVER=https://attendance.example.com npm run build
//
// PRESENCE_SERVER is the infiniPresence (Frappe) site the app talks to. It is baked into the build.
import { build } from "esbuild";
import { cpSync, mkdirSync, rmSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const shared = join(root, "..", "infinipresence", "public");
const out = join(root, "www");
const server = (process.env.PRESENCE_SERVER || "https://34-39-66-44.sslip.io").replace(/\/+$/, "");
if (!/^https:\/\//.test(server)) throw new Error("PRESENCE_SERVER must be an https:// address");

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

await build({
	entryPoints: [join(root, "src", "app.js")],
	bundle: true,
	minify: true,
	format: "iife",
	target: ["chrome90", "safari15"],
	outfile: join(out, "app.js"),
	define: { __SERVER__: JSON.stringify(server) },
	logLevel: "warning",
});

writeFileSync(join(out, "index.html"), readFileSync(join(root, "src", "index.html"), "utf8"));
cpSync(join(shared, "css", "presence.css"), join(out, "presence.css"));
cpSync(join(root, "src", "app.css"), join(out, "app.css"));
cpSync(join(shared, "icons", "icon-192.png"), join(out, "icon.png"));
cpSync(join(shared, "vendor", "face-api"), join(out, "vendor", "face-api"), { recursive: true });
console.log(`Built www/ for ${server}`);
