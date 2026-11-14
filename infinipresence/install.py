"""One-time and every-migrate setup. Only touches site settings and records, never upstream code."""

import frappe

DEFAULT_SHIFT_TYPE = "Office Hours"
MANAGER_ROLE = "Presence Manager"
MODULE_PROFILE = "infiniPresence Admin"

# Modules admins keep in the desk. Everything else is hidden for users given the module profile.
# Administrator and System Managers without the profile still see everything.
VISIBLE_MODULES = {"infiniPresence", "HR", "Setup", "Desk", "Core"}


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	_ensure_role()
	_ensure_hr_settings()
	_ensure_shift_type()
	_sync_module_profile()
	_ensure_signup_once()
	frappe.db.commit()


def _ensure_role():
	if not frappe.db.exists("Role", MANAGER_ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": MANAGER_ROLE, "desk_access": 1, "home_page": "/presence/admin"}
		).insert(ignore_permissions=True)


def _ensure_hr_settings():
	# Frappe HR's own geofence check on Employee Checkin.
	if not frappe.db.get_single_value("HR Settings", "allow_geolocation_tracking"):
		frappe.db.set_single_value("HR Settings", "allow_geolocation_tracking", 1)


def _ensure_shift_type():
	if frappe.db.exists("Shift Type", DEFAULT_SHIFT_TYPE):
		return
	frappe.get_doc(
		{
			"doctype": "Shift Type",
			"__newname": DEFAULT_SHIFT_TYPE,
			"name": DEFAULT_SHIFT_TYPE,
			"start_time": "09:00:00",
			"end_time": "18:00:00",
			"begin_check_in_before_shift_start_time": 180,
			"allow_check_out_after_shift_end_time": 360,
			"determine_check_in_and_check_out": "Alternating entries as IN and OUT during the same shift",
			"working_hours_calculation_based_on": "First Check-in and Last Check-out",
			"enable_auto_attendance": 1,
			"process_attendance_after": frappe.utils.nowdate(),
		}
	).insert(ignore_permissions=True)


def _sync_module_profile():
	"""Keep the admin module profile blocking every module except VISIBLE_MODULES,
	including modules that future upstream updates add."""
	modules = frappe.get_all("Module Def", pluck="name")
	blocked = sorted(m for m in modules if m not in VISIBLE_MODULES)
	if frappe.db.exists("Module Profile", MODULE_PROFILE):
		doc = frappe.get_doc("Module Profile", MODULE_PROFILE)
		if sorted(b.module for b in doc.block_modules) == blocked:
			return
		doc.block_modules = []
	else:
		doc = frappe.new_doc("Module Profile")
		doc.module_profile_name = MODULE_PROFILE
	for m in blocked:
		doc.append("block_modules", {"module": m})
	doc.save(ignore_permissions=True)


def _ensure_signup_once():
	"""Turn on self sign-up the first time only, so an admin can switch it off later."""
	if frappe.db.get_default("infinipresence_signup_set"):
		return
	frappe.db.set_single_value("Website Settings", "disable_signup", 0)
	frappe.db.set_default("infinipresence_signup_set", "1")


def website_user_home_page(user):
	return "presence"
