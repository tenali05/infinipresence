// infiniPresence shared helpers: API calls, camera, face scan, location.
(function () {
	const FACE_API = "/assets/infinipresence/vendor/face-api/face-api.js";
	const MODELS = "/assets/infinipresence/vendor/face-api/model/";

	const P = (window.presence = {});

	P.csrf = () => (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

	P.call = async function (method, args, httpMethod) {
		const post = httpMethod !== "GET";
		let url = "/api/method/" + method;
		const opts = {
			method: post ? "POST" : "GET",
			headers: { Accept: "application/json", "X-Frappe-CSRF-Token": P.csrf() },
			credentials: "same-origin",
		};
		if (post) {
			opts.headers["Content-Type"] = "application/json";
			opts.body = JSON.stringify(args || {});
		} else if (args) {
			url += "?" + new URLSearchParams(args).toString();
		}
		const res = await fetch(url, opts);
		let data = {};
		try {
			data = await res.json();
		} catch (e) {}
		if (!res.ok || data.exc_type) {
			throw new Error(P.errorText(data) || "Something went wrong (" + res.status + ").");
		}
		return data.message;
	};

	P.errorText = function (data) {
		try {
			if (data._server_messages) {
				const msgs = JSON.parse(data._server_messages).map((m) => JSON.parse(m).message);
				return msgs.join(" ").replace(/<[^>]+>/g, " ").trim();
			}
		} catch (e) {}
		return data.message || data.exception || "";
	};

	// ---- face scan -------------------------------------------------------
	let modelsReady = null;
	P.loadFaceModels = function () {
		if (modelsReady) return modelsReady;
		modelsReady = new Promise((resolve, reject) => {
			const s = document.createElement("script");
			s.src = FACE_API;
			s.onload = resolve;
			s.onerror = () => reject(new Error("Could not load the face scanner. Check your connection."));
			document.head.appendChild(s);
		}).then(() =>
			Promise.all([
				faceapi.nets.tinyFaceDetector.loadFromUri(MODELS),
				faceapi.nets.faceLandmark68Net.loadFromUri(MODELS),
				faceapi.nets.faceRecognitionNet.loadFromUri(MODELS),
			])
		);
		modelsReady.catch(() => (modelsReady = null));
		return modelsReady;
	};

	P.startCamera = async function (video) {
		if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
			throw new Error("This browser cannot use the camera. Open the page over https in Chrome or Safari.");
		}
		const stream = await navigator.mediaDevices.getUserMedia({
			video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
			audio: false,
		});
		video.srcObject = stream;
		await video.play();
		return stream;
	};

	P.stopCamera = function (video) {
		const s = video && video.srcObject;
		if (s) s.getTracks().forEach((t) => t.stop());
		if (video) video.srcObject = null;
	};

	// Returns {descriptor: number[128], photo: dataURL} or throws if no single clear face.
	P.scanFace = async function (video) {
		await P.loadFaceModels();
		const sizes = [416, 320, 512, 416, 608];
		let result = null;
		for (let i = 0; i < sizes.length && !result; i++) {
			const opts = new faceapi.TinyFaceDetectorOptions({ inputSize: sizes[i], scoreThreshold: 0.4 });
			result = await faceapi.detectSingleFace(video, opts).withFaceLandmarks().withFaceDescriptor();
			if (!result) await new Promise((r) => setTimeout(r, 200));
		}
		if (!result) throw new Error("No face found. Look straight at the camera in good light.");
		const canvas = document.createElement("canvas");
		const w = 480;
		canvas.width = w;
		canvas.height = Math.round((video.videoHeight / video.videoWidth) * w) || 360;
		canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
		return { descriptor: Array.from(result.descriptor), photo: canvas.toDataURL("image/jpeg", 0.8) };
	};

	// ---- location --------------------------------------------------------
	function position(opts) {
		return new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition((pos) => resolve(pos.coords), reject, opts));
	}
	P.getPosition = async function () {
		if (!navigator.geolocation) throw new Error("This browser cannot share your location.");
		try {
			return await position({ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
		} catch (err) {
			if (err.code === 1) throw new Error("Location is blocked. Allow location for this site in your browser settings.");
			try {
				// GPS fix failed or timed out: accept a recent network-based fix instead.
				return await position({ enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
			} catch (e) {
				throw new Error("Could not get your location. Try again outside or near a window.");
			}
		}
	};

	P.distance = function (lat1, lon1, lat2, lon2) {
		const r = 6371000,
			rad = Math.PI / 180;
		const dp = (lat2 - lat1) * rad,
			dl = (lon2 - lon1) * rad;
		const a =
			Math.sin(dp / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dl / 2) ** 2;
		return 2 * r * Math.asin(Math.sqrt(a));
	};

	P.time = (t) => (t ? String(t).slice(11, 16) : "");
	P.esc = (s) =>
		String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

})();
