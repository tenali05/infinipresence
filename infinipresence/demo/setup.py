import frappe
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
def run():
    if not frappe.db.get_single_value("System Settings","setup_complete"):
        setup_complete({"language":"English","country":"United Kingdom","timezone":"Europe/London","currency":"GBP",
            "full_name":"Demo Admin","email":"admin@example.com","password":"admin",
            "company_name":"Surrey Demo Ltd","company_abbr":"SDL","chart_of_accounts":"Standard",
            "fy_start_date":"2026-04-01","fy_end_date":"2027-03-31","setup_demo":0})
    frappe.db.commit()
    print("setup", frappe.db.get_single_value("System Settings","setup_complete"), frappe.get_all("Company", pluck="name"))
