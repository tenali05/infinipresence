import frappe

from infinipresence.api import _is_manager

no_cache = 1
sitemap = 0


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/presence/admin"
		raise frappe.Redirect
	if not _is_manager():
		frappe.local.flags.redirect_location = "/presence"
		raise frappe.Redirect
	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	return context
