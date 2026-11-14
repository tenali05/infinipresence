import frappe

no_cache = 1
sitemap = 0


def get_context(context):
	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else ""
	context.is_guest = frappe.session.user == "Guest"
	return context
