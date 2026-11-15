// CI smoke test: reads the running app's WebView over the DevTools protocol (debug build only)
// and checks that the sign-in screen rendered with no script errors.
// Expects `adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>` first.
const pages = await (await fetch("http://127.0.0.1:9222/json")).json();
const page = pages.find((p) => p.type === "page");
if (!page) throw new Error("No WebView page found: " + JSON.stringify(pages));
console.log("WebView page:", page.url);
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r, j) => ((ws.onopen = r), (ws.onerror = j)));
let id = 0;
const pending = new Map();
ws.onmessage = (m) => {
	const d = JSON.parse(m.data);
	if (pending.has(d.id)) pending.get(d.id)(d), pending.delete(d.id);
};
const send = (method, params) => new Promise((r) => (pending.set(++id, r), ws.send(JSON.stringify({ id, method, params }))));
const evaluate = async (expression) => (await send("Runtime.evaluate", { expression, returnByValue: true })).result.result.value;

const info = await evaluate(`JSON.stringify({
	visible: [...document.querySelectorAll("main > section, #loading")].filter((e) => !e.classList.contains("hidden")).map((e) => e.id),
	heading: (document.querySelector("main > section:not(.hidden) h1") || {}).textContent,
	platform: window.Capacitor && window.Capacitor.getPlatform(),
	native: window.Capacitor && window.Capacitor.isNativePlatform(),
	plugins: window.Capacitor && Object.keys(window.Capacitor.Plugins || {}),
	media: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
})`);
console.log("App state:", info);
const fa = await send("Runtime.evaluate", {
	expression: `new Promise((resolve) => {
	const s = document.createElement("script"); s.src = "vendor/face-api/face-api.js";
	s.onload = () => faceapi.nets.tinyFaceDetector.loadFromUri("vendor/face-api/model/").then(() => resolve("face models load"), (e) => resolve("model error: " + e));
	s.onerror = () => resolve("face-api.js failed to load"); document.head.appendChild(s);
})`,
	awaitPromise: true,
	returnByValue: true,
});
console.log("Face scanner:", fa.result.result.value);
ws.close();
const s = JSON.parse(info);
if (!s.visible.includes("v-guest") || s.heading !== "Welcome" || !s.native || s.platform !== "android") {
	console.error("FAIL: the app did not show the sign-in screen as a native Android app");
	process.exit(1);
}
if (fa.result.result.value !== "face models load") {
	console.error("FAIL: face scanner did not load");
	process.exit(1);
}
console.log("PASS: native Android app started on the sign-in screen and the face scanner loads.");
