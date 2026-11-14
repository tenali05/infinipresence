"""infiniPresence web API.

Employees use the /presence page; admins use /presence/admin. Both call these methods.
Employee check-ins are stored as standard Frappe HR "Employee Checkin" records, so Frappe HR's
own shift and attendance processing keeps working unchanged.
"""

import base64
import json
import math
import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

MANAGER_ROLES = {"Presence Manager", "System Manager"}
DESCRIPTOR_LENGTH = 128
DEVICE_ID = "infiniPresence web"


def _conf(key, default):
	"""Site-level tuning, e.g. `bench --site x set-config infinipresence_face_threshold 0.45`."""
	return frappe.conf.get(f"infinipresence_{key}", default)


def face_threshold():
	return flt(_conf("face_threshold", 0.5))


# ---------------------------------------------------------------------------
# helpers


def _is_manager(user=None):
	return bool(MANAGER_ROLES & set(frappe.get_roles(user)))


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in first."), frappe.PermissionError)


def _require_manager():
	_require_login()
	if not _is_manager():
		frappe.throw(_("Only infiniPresence admins can do this."), frappe.PermissionError)


def _get_profile(user):
	name = frappe.db.exists("Presence Profile", {"user": user})
	return frappe.get_doc("Presence Profile", name) if name else None


def _parse_descriptor(descriptor):
	if isinstance(descriptor, str):
		descriptor = json.loads(descriptor)
	if not isinstance(descriptor, list) or len(descriptor) != DESCRIPTOR_LENGTH:
		frappe.throw(_("No face was detected. Look straight at the camera and try again."))
	values = [float(v) for v in descriptor]
	if not all(math.isfinite(v) for v in values):
		frappe.throw(_("The face scan was not valid. Please try again."))
	return values


def _face_distance(a, b):
	return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def _save_photo(photo, doctype, docname, prefix):
	"""Save a data: URL JPEG as a private file attached to the document. Returns the file URL."""
	if not photo:
		return None
	match = re.match(r"^data:image/(jpeg|png|webp);base64,(.+)$", photo, re.S)
	if not match:
		frappe.throw(_("The photo was not valid. Please try again."))
	content = base64.b64decode(match.group(2))
	if len(content) > 2 * 1024 * 1024:
		frappe.throw(_("The photo is too large."))
	ext = "jpg" if match.group(1) == "jpeg" else match.group(1)
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{prefix}-{frappe.generate_hash(length=8)}.{ext}",
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
			"is_private": 1,
			"content": content,
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	return file.file_url


def _distance_m(lat1, lon1, lat2, lon2):
	r = 6371000
	p1, p2 = math.radians(lat1), math.radians(lat2)
	dp = p2 - p1
	dl = math.radians(lon2 - lon1)
	a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
	return 2 * r * math.asin(math.sqrt(a))


def _location(name):
	if not name:
		return None
	loc = frappe.db.get_value(
		"Shift Location", name, ["name", "location_name", "latitude", "longitude", "checkin_radius"], as_dict=True
	)
	return loc


def _today_logs(employee, day=None):
	if not employee:
		return []
	day = getdate(day or nowdate())
	return frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ["between", [f"{day} 00:00:00", f"{day} 23:59:59"]]},
		fields=["name", "log_type", "time"],
		order_by="time asc",
	)


def _default_company():
	return (
		frappe.defaults.get_global_default("company")
		or frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	)


def _default_shift_type():
	from infinipresence.install import DEFAULT_SHIFT_TYPE

	if frappe.db.exists("Shift Type", DEFAULT_SHIFT_TYPE):
		return DEFAULT_SHIFT_TYPE
	return frappe.db.get_value("Shift Type", {}, "name", order_by="creation asc")


# ---------------------------------------------------------------------------
# guests


@frappe.whitelist(allow_guest=True)
def get_login_options():
	google = frappe.db.get_value("Social Login Key", {"name": "google", "enable_social_login": 1}, "name")
	url = None
	if google:
		from frappe.utils.oauth import get_oauth2_authorize_url

		url = get_oauth2_authorize_url("google", "/presence")
	return {
		"google_login_url": url,
		"signup_enabled": not cint(frappe.db.get_single_value("Website Settings", "disable_signup")),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def register(full_name, email, password):
	"""Simple email + password sign-up. The account stays pending until an admin approves it."""
	if cint(frappe.db.get_single_value("Website Settings", "disable_signup")):
		frappe.throw(_("Sign-up is turned off. Ask your admin for an account."))
	from frappe.utils import validate_email_address

	email = (email or "").strip().lower()
	full_name = (full_name or "").strip()
	if not validate_email_address(email):
		frappe.throw(_("Enter a valid email address."))
	if not full_name:
		frappe.throw(_("Enter your name."))
	if len(password or "") < 8:
		frappe.throw(_("Use a password of at least 8 characters."))
	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists. Sign in instead."))

	first, _sep, last = full_name.partition(" ")
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first,
			"last_name": last,
			"user_type": "Website User",
			"enabled": 1,
			"send_welcome_email": 0,
			"new_password": password,
		}
	)
	user.flags.ignore_permissions = True
	user.flags.no_welcome_mail = True
	user.insert()
	return {"ok": True}


# ---------------------------------------------------------------------------
# employees


@frappe.whitelist()
def get_state():
	_require_login()
	user = frappe.session.user
	profile = _get_profile(user)
	state = {
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
		"is_manager": _is_manager(),
		"status": profile.status if profile else None,
		"has_face": bool(profile and profile.face_descriptor),
		"location": None,
		"logs": [],
		"next_log_type": "IN",
		"face_threshold": face_threshold(),
	}
	if profile and profile.status == "Approved":
		state["location"] = _location(profile.shift_location)
		state["logs"] = _today_logs(profile.employee)
		if state["logs"] and state["logs"][-1].log_type == "IN":
			state["next_log_type"] = "OUT"
	return state


@frappe.whitelist(methods=["POST"])
def enroll_face(descriptor, photo):
	"""Save the user's reference face. Creates their (pending) profile on first use."""
	_require_login()
	user = frappe.session.user
	values = _parse_descriptor(descriptor)
	profile = _get_profile(user)
	if profile and profile.face_descriptor and profile.status == "Approved":
		frappe.throw(_("Your face is already registered. Ask your admin to reset it if needed."))
	if not profile:
		profile = frappe.get_doc(
			{
				"doctype": "Presence Profile",
				"user": user,
				"full_name": frappe.utils.get_fullname(user),
				"status": "Pending",
			}
		)
		profile.flags.ignore_permissions = True
		profile.insert()
	profile.face_descriptor = json.dumps(values)
	profile.face_photo = _save_photo(photo, "Presence Profile", profile.name, "face")
	profile.flags.ignore_permissions = True
	profile.save()
	return get_state()


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def check_in(latitude, longitude, descriptor, photo=None, accuracy=None):
	"""Record a check-in or check-out after checking location and face."""
	_require_login()
	profile = _get_profile(frappe.session.user)
	if not profile or profile.status != "Approved" or not profile.employee:
		frappe.throw(_("Your account is waiting for admin approval."))
	if not profile.face_descriptor:
		frappe.throw(_("Register your face first."))
	loc = _location(profile.shift_location)
	if not loc:
		frappe.throw(_("Your admin has not assigned you an office location yet."))

	latitude, longitude = flt(latitude), flt(longitude)
	if not (latitude or longitude):
		frappe.throw(_("Your location is needed to check in. Allow location access and try again."))
	distance = _distance_m(flt(loc.latitude), flt(loc.longitude), latitude, longitude)
	radius = flt(loc.checkin_radius)
	if radius > 0 and distance > radius:
		frappe.throw(
			_("You are {0} m from {1}. You need to be within {2} m to check in.").format(
				round(distance), loc.location_name or loc.name, round(radius)
			)
		)

	face = _face_distance(_parse_descriptor(descriptor), json.loads(profile.face_descriptor))
	if face > face_threshold():
		frappe.throw(_("Your face did not match the registered face. Try again in better light."))

	logs = _today_logs(profile.employee)
	log_type = "OUT" if logs and logs[-1].log_type == "IN" else "IN"
	if logs and (now_datetime() - get_datetime(logs[-1].time)).total_seconds() < 60:
		frappe.throw(_("You checked {0} less than a minute ago.").format(logs[-1].log_type.lower()))

	checkin = frappe.get_doc(
		{
			"doctype": "Employee Checkin",
			"employee": profile.employee,
			"log_type": log_type,
			"time": now_datetime(),
			"device_id": DEVICE_ID,
			"latitude": latitude,
			"longitude": longitude,
		}
	)
	checkin.flags.ignore_permissions = True
	checkin.insert()
	if photo:
		_save_photo(photo, "Employee Checkin", checkin.name, "checkin")
	return {
		"log_type": log_type,
		"time": checkin.time,
		"distance": round(distance),
		"face_distance": round(face, 3),
		"state": get_state(),
	}


# ---------------------------------------------------------------------------
# admins


@frappe.whitelist()
def admin_overview():
	_require_manager()
	profiles = frappe.get_all(
		"Presence Profile",
		fields=["name", "user", "full_name", "status", "shift_location", "employee", "face_photo", "creation"],
		order_by="creation desc",
	)
	locations = frappe.get_all(
		"Shift Location",
		fields=["name", "location_name", "latitude", "longitude", "checkin_radius"],
		order_by="location_name asc",
	)
	return {"profiles": profiles, "locations": locations}


@frappe.whitelist(methods=["POST"])
def approve(profile, shift_location):
	"""Approve a user: create their Employee record and assign them to an office location."""
	_require_manager()
	doc = frappe.get_doc("Presence Profile", profile)
	if not doc.face_descriptor:
		frappe.throw(_("{0} has not registered their face yet.").format(doc.full_name or doc.user))
	if not frappe.db.exists("Shift Location", shift_location):
		frappe.throw(_("Choose an office location."))

	if not doc.employee:
		doc.employee = _create_employee(doc)
	else:
		frappe.db.set_value("Employee", doc.employee, "status", "Active")
	_assign_location(doc.employee, shift_location)
	doc.status = "Approved"
	doc.shift_location = shift_location
	doc.approved_by = frappe.session.user
	doc.flags.ignore_permissions = True
	doc.save()
	return admin_overview()


@frappe.whitelist(methods=["POST"])
def set_location(profile, shift_location):
	_require_manager()
	doc = frappe.get_doc("Presence Profile", profile)
	if doc.status != "Approved":
		frappe.throw(_("Approve this user first."))
	_assign_location(doc.employee, shift_location)
	doc.shift_location = shift_location
	doc.flags.ignore_permissions = True
	doc.save()
	return admin_overview()


@frappe.whitelist(methods=["POST"])
def reject(profile):
	"""Reject a pending user, or remove access from an approved one. History is kept."""
	_require_manager()
	doc = frappe.get_doc("Presence Profile", profile)
	doc.status = "Rejected"
	if doc.employee:
		frappe.db.set_value("Employee", doc.employee, "status", "Inactive")
	doc.flags.ignore_permissions = True
	doc.save()
	return admin_overview()


@frappe.whitelist(methods=["POST"])
def reset_face(profile):
	"""Let the user register their face again (for example after a bad first photo)."""
	_require_manager()
	doc = frappe.get_doc("Presence Profile", profile)
	doc.face_descriptor = None
	doc.face_photo = None
	doc.flags.ignore_permissions = True
	doc.save()
	return admin_overview()


@frappe.whitelist(methods=["POST"])
def save_location(location_name, latitude, longitude, checkin_radius, name=None):
	_require_manager()
	if name:
		doc = frappe.get_doc("Shift Location", name)
	else:
		doc = frappe.new_doc("Shift Location")
		doc.location_name = (location_name or "").strip()
	doc.latitude = flt(latitude)
	doc.longitude = flt(longitude)
	doc.checkin_radius = cint(checkin_radius) or 100
	if not doc.location_name:
		frappe.throw(_("Give the location a name."))
	doc.flags.ignore_permissions = True
	doc.save()
	return admin_overview()


@frappe.whitelist()
def attendance(date=None, to_date=None):
	"""Who checked in, per person per day, from the check-in log (live, no waiting for processing)."""
	_require_manager()
	start = getdate(date or nowdate())
	end = getdate(to_date or start)
	if (end - start).days > 62:
		frappe.throw(_("Choose a range of at most two months."))
	people = frappe.get_all(
		"Presence Profile",
		filters={"status": "Approved", "employee": ["is", "set"]},
		fields=["employee", "full_name", "user", "shift_location"],
		order_by="full_name asc",
	)
	logs = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": ["in", [p.employee for p in people] or [""]],
			"time": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]],
		},
		fields=["employee", "log_type", "time"],
		order_by="time asc",
	)
	by_key = {}
	for log in logs:
		by_key.setdefault((log.employee, getdate(log.time)), []).append(log)

	rows = []
	day = start
	while day <= end:
		for p in people:
			day_logs = by_key.get((p.employee, day), [])
			ins = [lg.time for lg in day_logs if lg.log_type == "IN"]
			outs = [lg.time for lg in day_logs if lg.log_type == "OUT"]
			hours = None
			if ins and outs and max(outs) > min(ins):
				hours = round((max(outs) - min(ins)).total_seconds() / 3600, 2)
			rows.append(
				{
					"date": day,
					"employee": p.employee,
					"full_name": p.full_name,
					"user": p.user,
					"location": p.shift_location,
					"first_in": min(ins) if ins else None,
					"last_out": max(outs) if outs else None,
					"hours": hours,
					"status": "Present" if day_logs else "Absent",
				}
			)
		day = add_days(day, 1)
	return {"from": start, "to": end, "rows": rows}


def _create_employee(profile):
	company = _default_company()
	if not company:
		frappe.throw(_("Create a company first (finish the setup wizard)."))
	first, _sep, last = (profile.full_name or profile.user).partition(" ")
	emp = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first,
			"last_name": last,
			"company": company,
			"company_email": profile.user,
			"prefered_contact_email": "Company Email",
			"date_of_joining": nowdate(),
			"status": "Active",
		}
	)
	# Gender and date of birth are mandatory in ERPNext but not collected at sign-up.
	emp.flags.ignore_mandatory = True
	emp.flags.ignore_permissions = True
	emp.insert()
	return emp.name


def _assign_location(employee, shift_location):
	"""Give the employee one active Shift Assignment at the chosen location (Frappe HR's geofence)."""
	today = getdate(nowdate())
	for sa in frappe.get_all(
		"Shift Assignment",
		filters={"employee": employee, "docstatus": 1, "status": "Active"},
		fields=["name", "start_date", "shift_location"],
	):
		doc = frappe.get_doc("Shift Assignment", sa.name)
		doc.flags.ignore_permissions = True
		if getdate(sa.start_date) >= today:
			doc.cancel()
		else:
			doc.db_set("end_date", add_days(today, -1))
	shift_type = _default_shift_type()
	if not shift_type:
		frappe.throw(_("No shift type exists. Run the infiniPresence setup."))
	sa = frappe.get_doc(
		{
			"doctype": "Shift Assignment",
			"employee": employee,
			"shift_type": shift_type,
			"company": frappe.db.get_value("Employee", employee, "company"),
			"start_date": today,
			"shift_location": shift_location,
			"status": "Active",
		}
	)
	sa.flags.ignore_permissions = True
	sa.insert()
	sa.submit()
