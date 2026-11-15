// infiniPresence phone app. The screens mirror the /presence web page; the differences are:
//  - API calls go through native HTTP with a personal token (no browser cookies or CORS),
//  - location comes from the native Geolocation plugin,
//  - the face scanner ships inside the app, so it works on a slow connection.
import { Capacitor, CapacitorHttp } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";
import { Preferences } from "@capacitor/preferences";
import { SplashScreen } from "@capacitor/splash-screen";

/* global __SERVER__, faceapi */
const SERVER = __SERVER__;
const SOURCE = Capacitor.getPlatform() === "ios" ? "ios" : "android";
const TOKEN_KEY = "presence.token";

const $ = (id) => document.getElementById(id);
const esc = (s) =>
	String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const hhmm = (t) => (t ? String(t).slice(11, 16) : "");

// ---------------------------------------------------------------- API
let token = null;

class ApiError extends Error {
	constructor(message, status) {
		super(message);
		this.status = status;
	}
}

function errorText(data) {
	try {
		if (data && data._server_messages) {
			return JSON.parse(data._server_messages)
				.map((m) => JSON.parse(m).message)
				.join(" ")
				.replace(/<[^>]+>/g, " ")
				.trim();
		}
	} catch (e) {}
	return (data && (data.message || data.exception)) || "";
}

async function call(method, args, httpMethod) {
	const post = httpMethod !== "GET";
	const headers = { Accept: "application/json" };
	if (token) headers.Authorization = "token " + token;
	if (post) headers["Content-Type"] = "application/json";
	let res;
	try {
		res = await CapacitorHttp.request({
			url: SERVER + "/api/method/" + method,
			method: post ? "POST" : "GET",
			headers,
			params: !post && args ? args : undefined,
			data: post ? args || {} : undefined,
			connectTimeout: 20000,
			readTimeout: 45000,
		});
	} catch (e) {
		throw new ApiError("Can't reach the server. Check your internet connection and try again.", 0);
	}
	let data = res.data;
	if (typeof data === "string") {
		try {
			data = JSON.parse(data);
		} catch (e) {
			data = {};
		}
	}
	data = data || {};
	if (res.status < 200 || res.status >= 300 || data.exc_type) {
		throw new ApiError(errorText(data) || "Something went wrong (" + res.status + ").", res.status);
	}
	return data.message;
}

async function setToken(value) {
	token = value;
	if (value) await Preferences.set({ key: TOKEN_KEY, value });
	else await Preferences.remove({ key: TOKEN_KEY });
}

// ---------------------------------------------------------------- face scan
let modelsReady = null;
function loadFaceModels() {
	if (modelsReady) return modelsReady;
	modelsReady = new Promise((resolve, reject) => {
		const s = document.createElement("script");
		s.src = "vendor/face-api/face-api.js";
		s.onload = resolve;
		s.onerror = () => reject(new Error("Could not load the face scanner."));
		document.head.appendChild(s);
	}).then(() => {
		const models = "vendor/face-api/model/";
		return Promise.all([
			faceapi.nets.tinyFaceDetector.loadFromUri(models),
			faceapi.nets.faceLandmark68Net.loadFromUri(models),
			faceapi.nets.faceRecognitionNet.loadFromUri(models),
		]);
	});
	modelsReady.catch(() => (modelsReady = null));
	return modelsReady;
}

async function startCamera(video) {
	if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
		throw new Error("This phone can't use the camera here.");
	}
	let stream;
	try {
		stream = await navigator.mediaDevices.getUserMedia({
			video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
			audio: false,
		});
	} catch (e) {
		throw new Error("Camera access is off. Allow the camera for infiniPresence in your phone's settings.");
	}
	video.srcObject = stream;
	await video.play();
	return stream;
}

function stopCamera(video) {
	const s = video && video.srcObject;
	if (s) s.getTracks().forEach((t) => t.stop());
	if (video) video.srcObject = null;
}

// Returns {descriptor: number[128], photo: dataURL} or throws if no single clear face.
async function scanFace(video) {
	await loadFaceModels();
	const sizes = [416, 320, 512, 416, 608];
	let result = null;
	for (let i = 0; i < sizes.length && !result; i++) {
		const opts = new faceapi.TinyFaceDetectorOptions({ inputSize: sizes[i], scoreThreshold: 0.4 });
		result = await faceapi.detectSingleFace(video, opts).withFaceLandmarks().withFaceDescriptor();
		if (!result) await new Promise((r) => setTimeout(r, 200));
	}
	if (!result) throw new Error("No face found. Look straight at the camera in good light.");
	const canvas = document.createElement("canvas");
	canvas.width = 480;
	canvas.height = Math.round((video.videoHeight / video.videoWidth) * 480) || 360;
	canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
	return { descriptor: Array.from(result.descriptor), photo: canvas.toDataURL("image/jpeg", 0.8) };
}

// ---------------------------------------------------------------- location
async function ensureLocationPermission() {
	if (!Capacitor.isNativePlatform()) return;
	let p = await Geolocation.checkPermissions();
	if (p.location !== "granted") p = await Geolocation.requestPermissions({ permissions: ["location"] });
	if (p.location !== "granted") {
		throw new Error("Location access is off. Allow precise location for infiniPresence in your phone's settings.");
	}
}

async function getPosition() {
	await ensureLocationPermission();
	try {
		return (await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 })).coords;
	} catch (err) {
		if (/denied|permission/i.test(String(err && err.message))) {
			throw new Error("Location access is off. Allow precise location for infiniPresence in your phone's settings.");
		}
		try {
			return (await Geolocation.getCurrentPosition({ enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 })).coords;
		} catch (e) {
			throw new Error("Could not get your location. Turn on location, or try again outside or near a window.");
		}
	}
}

function distance(lat1, lon1, lat2, lon2) {
	const r = 6371000,
		rad = Math.PI / 180;
	const dp = (lat2 - lat1) * rad,
		dl = (lon2 - lon1) * rad;
	const a = Math.sin(dp / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dl / 2) ** 2;
	return 2 * r * Math.asin(Math.sqrt(a));
}

// ---------------------------------------------------------------- screens
const views = ["loading", "v-guest", "v-enroll", "v-pending", "v-rejected", "v-checkin"];
let state = null;
let watchId = null;
let lastCoords = null;

function show(id) {
	views.forEach((v) => $(v).classList.toggle("hidden", v !== id));
	if (id !== "v-enroll") stopCamera($("enroll-video"));
	if (id !== "v-checkin") {
		stopCamera($("checkin-video"));
		stopWatch();
	}
	const signedIn = id !== "v-guest" && id !== "loading";
	$("logout-link").classList.toggle("hidden", !signedIn);
	$("delete-start").classList.toggle("hidden", !signedIn);
	if (!signedIn) {
		$("admin-link").classList.add("hidden");
		$("delete-box").classList.add("hidden");
	}
}
function msg(el, text, kind) {
	$(el).innerHTML = text ? '<div class="msg ' + (kind || "bad") + '">' + esc(text) + "</div>" : "";
}
async function busy(btn, label, fn) {
	const old = btn.textContent;
	btn.disabled = true;
	btn.textContent = label;
	try {
		return await fn();
	} finally {
		btn.disabled = false;
		btn.textContent = old;
	}
}
function stopWatch() {
	if (watchId != null && watchId !== "pending") {
		Geolocation.clearWatch({ id: watchId }).catch(() => {});
	}
	watchId = null;
}
function openExternal(path) {
	// Navigating to another site makes Capacitor open it in the phone's browser.
	window.location.href = SERVER + path;
}
document.querySelectorAll(".policy-link").forEach((a) =>
	a.addEventListener("click", (e) => {
		e.preventDefault();
		openExternal("/presence/privacy");
	})
);
$("admin-link").onclick = (e) => {
	e.preventDefault();
	openExternal("/presence/admin");
};

// ---------- guest
function tab(which) {
	$("t-login").classList.toggle("on", which === "login");
	$("t-register").classList.toggle("on", which === "register");
	$("f-login").classList.toggle("hidden", which !== "login");
	$("f-register").classList.toggle("hidden", which !== "register");
	msg("guest-msg", "");
}
$("t-login").onclick = () => tab("login");
$("t-register").onclick = () => tab("register");

async function login(email, pwd) {
	const res = await call("infinipresence.api.app_login", { usr: email, pwd });
	await setToken(res.token);
	await load();
}
$("f-login").onsubmit = (e) => {
	e.preventDefault();
	busy(e.target.querySelector("button"), "Signing in…", () => login($("l-email").value.trim(), $("l-pwd").value)).catch(
		(err) => msg("guest-msg", err.message)
	);
};
$("f-register").onsubmit = (e) => {
	e.preventDefault();
	busy(e.target.querySelector("button"), "Creating account…", async () => {
		const email = $("r-email").value.trim();
		await call("infinipresence.api.register", { full_name: $("r-name").value, email, password: $("r-pwd").value });
		await login(email, $("r-pwd").value);
	}).catch((err) => msg("guest-msg", err.message));
};
$("logout-link").onclick = async (e) => {
	e.preventDefault();
	try {
		await call("infinipresence.api.app_logout", {});
	} catch (err) {}
	await setToken(null);
	tab("login");
	show("v-guest");
};

// ---------- face registration
$("enroll-consent").onchange = () => ($("enroll-start").disabled = !$("enroll-consent").checked);
$("enroll-start").onclick = async () => {
	msg("enroll-msg", "");
	try {
		await busy($("enroll-start"), "Starting camera…", async () => {
			await startCamera($("enroll-video"));
			loadFaceModels().catch(() => {});
		});
		$("enroll-start").classList.add("hidden");
		$("enroll-take").classList.remove("hidden");
	} catch (e) {
		msg("enroll-msg", e.message);
	}
};
$("enroll-take").onclick = () => {
	msg("enroll-msg", "");
	busy($("enroll-take"), "Scanning…", async () => {
		const scan = await scanFace($("enroll-video"));
		state = await call("infinipresence.api.enroll_face", scan);
		render();
	}).catch((e) => msg("enroll-msg", e.message));
};
$("pending-refresh").onclick = () => load();
$("pending-retake").onclick = () => {
	resetEnroll();
	show("v-enroll");
};
function resetEnroll() {
	$("enroll-start").classList.remove("hidden");
	$("enroll-take").classList.add("hidden");
	$("enroll-start").disabled = !$("enroll-consent").checked;
}

// ---------- check in
async function startWatch(loc) {
	if (watchId != null) return;
	const pending = (watchId = "pending");
	try {
		await ensureLocationPermission();
		const id = await Geolocation.watchPosition({ enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }, (pos, err) => {
			if (err || !pos) {
				$("office-distance").textContent = "Location off";
				return;
			}
			lastCoords = { coords: pos.coords, at: Date.now() };
			const d = distance(loc.latitude, loc.longitude, pos.coords.latitude, pos.coords.longitude);
			const inside = !loc.checkin_radius || d <= loc.checkin_radius;
			$("office-distance").innerHTML =
				'<span class="pill ' + (inside ? "ok" : "no") + '">' +
				(d < 1000 ? Math.round(d) + " m" : (d / 1000).toFixed(1) + " km") +
				(inside ? " · in range" : " away") +
				"</span>";
		});
		if (watchId === pending) watchId = id;
		else Geolocation.clearWatch({ id }).catch(() => {}); // screen was left while starting
	} catch (e) {
		if (watchId === pending) watchId = null;
		$("office-distance").textContent = "Location off";
		msg("checkin-msg", e.message, "warn");
	}
}

function renderCheckin() {
	$("hello").textContent = "Hi " + (state.full_name || "").split(" ")[0];
	const loc = state.location;
	$("office-name").textContent = loc ? loc.location_name || loc.name : "Not assigned";
	$("no-office").classList.toggle("hidden", !!loc);
	$("checkin-btn").textContent = state.next_log_type === "OUT" ? "Check out" : "Check in";
	$("checkin-btn").disabled = !loc;
	const logs = state.logs || [];
	$("logs").innerHTML = logs.length
		? logs
				.map((l) => "<li><span>" + (l.log_type === "IN" ? "Checked in" : "Checked out") + "</span><b>" + hhmm(l.time) + "</b></li>")
				.join("")
		: '<li class="muted">No check-ins yet today.</li>';
	if (loc) startWatch(loc);
	if (loc && !$("checkin-video").srcObject) {
		startCamera($("checkin-video")).catch((e) => msg("checkin-msg", e.message));
		loadFaceModels().catch(() => {});
	}
}
$("checkin-btn").onclick = () => {
	msg("checkin-msg", "");
	const label = state.next_log_type === "OUT" ? "Checking out…" : "Checking in…";
	busy($("checkin-btn"), label, async () => {
		if (!$("checkin-video").srcObject) await startCamera($("checkin-video"));
		const fresh = lastCoords && Date.now() - lastCoords.at < 20000 ? Promise.resolve(lastCoords.coords) : getPosition();
		const [coords, scan] = await Promise.all([fresh, scanFace($("checkin-video"))]);
		const res = await call("infinipresence.api.check_in", {
			latitude: coords.latitude,
			longitude: coords.longitude,
			accuracy: coords.accuracy,
			descriptor: scan.descriptor,
			photo: scan.photo,
			source: SOURCE,
		});
		state = res.state;
		msg("checkin-msg", (res.log_type === "IN" ? "Checked in" : "Checked out") + " at " + hhmm(res.time) + ".", "good");
	})
		.then(() => renderCheckin())
		.catch((e) => msg("checkin-msg", e.message));
};

// ---------- account deletion (required by Google Play for apps with sign-up)
$("delete-start").onclick = () => $("delete-box").classList.remove("hidden");
$("delete-no").onclick = () => $("delete-box").classList.add("hidden");
$("delete-yes").onclick = () => {
	busy($("delete-yes"), "Deleting…", async () => {
		await call("infinipresence.api.delete_my_account", {});
		await setToken(null);
		$("delete-box").classList.add("hidden");
		show("v-guest");
		msg("guest-msg", "Your account and face data were deleted.", "good");
	}).catch((e) => msg("delete-msg", e.message));
};

function render() {
	$("admin-link").classList.toggle("hidden", !state.is_manager);
	if (!state.has_face && state.status !== "Rejected") {
		resetEnroll();
		return show("v-enroll");
	}
	if (state.status === "Approved") {
		show("v-checkin");
		return renderCheckin();
	}
	if (state.status === "Rejected") return show("v-rejected");
	show("v-pending");
}

async function load() {
	if (!token) return show("v-guest");
	show("loading");
	$("loading").textContent = "Loading…";
	try {
		state = await call("infinipresence.api.get_state", null, "GET");
		render();
	} catch (e) {
		if (e.status === 401 || e.status === 403) {
			// Token replaced (signed in elsewhere) or account closed.
			await setToken(null);
			show("v-guest");
			msg("guest-msg", "Please sign in again.", "warn");
			return;
		}
		$("loading").innerHTML = esc(e.message) + '<button id="retry" class="secondary" type="button">Try again</button>';
		$("retry").onclick = () => load();
	}
}

// Stop the camera and GPS when the app goes to the background; resume when it comes back.
document.addEventListener("visibilitychange", () => {
	if (document.hidden) {
		stopCamera($("checkin-video"));
		stopCamera($("enroll-video"));
		stopWatch();
		if (!$("v-enroll").classList.contains("hidden")) resetEnroll();
	} else if (state && !$("v-checkin").classList.contains("hidden")) {
		renderCheckin();
	}
});

(async function start() {
	try {
		token = (await Preferences.get({ key: TOKEN_KEY })).value || null;
	} catch (e) {}
	await load();
	SplashScreen.hide().catch(() => {});
})();
