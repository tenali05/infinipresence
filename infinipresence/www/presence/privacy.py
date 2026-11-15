import frappe

no_cache = 1
sitemap = 1


def get_context(context):
	"""Public privacy policy for the infiniPresence app (linked from Google Play and the app).

	Set the operator's name and contact with
	`bench --site <site> set-config infinipresence_privacy_org "Acme Ltd"` and
	`bench --site <site> set-config infinipresence_privacy_contact "privacy@acme.com"`.
	"""
	conf = frappe.conf
	company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	context.no_cache = 1
	context.org = conf.get("infinipresence_privacy_org") or company or "the operator of this service"
	context.contact = conf.get("infinipresence_privacy_contact") or ""
	context.updated = conf.get("infinipresence_privacy_updated") or "15 November 2026"
	return context
