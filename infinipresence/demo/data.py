import frappe, random
from frappe.utils import getdate, add_days, get_datetime
LAT, LON = 51.2362, -0.5704
PEOPLE = [("Asha","Patel","Female"),("Tom","Hughes","Male"),("Priya","Nair","Female"),("Daniel","Okafor","Male"),("Emma","Clarke","Female")]
def run():
    co = "Surrey Demo Ltd"
    hs = frappe.get_single("HR Settings"); hs.allow_geolocation_tracking = 1; hs.emp_created_by = "Naming Series"; hs.save()
    if not frappe.db.exists("Shift Location","Guildford Office"):
        frappe.get_doc({"doctype":"Shift Location","location_name":"Guildford Office","latitude":LAT,"longitude":LON,"checkin_radius":200}).insert()
    if not frappe.db.exists("Shift Type","General 9-5:30"):
        frappe.get_doc({"doctype":"Shift Type","name":"General 9-5:30","__newname":"General 9-5:30","start_time":"09:00:00","end_time":"17:30:00",
            "enable_auto_attendance":1,"process_attendance_after":"2026-10-01","last_sync_of_checkin":"2026-11-01 08:00:00",
            "determine_check_in_and_check_out":"Alternating entries as IN and OUT during the same shift",
            "working_hours_calculation_based_on":"First Check-in and Last Check-out","begin_check_in_before_shift_start_time":60,"allow_check_out_after_shift_end_time":120}).insert()
    random.seed(7)
    for i,(fn,ln,g) in enumerate(PEOPLE):
        email = f"{fn.lower()}@example.com"
        if not frappe.db.exists("User", email):
            u = frappe.get_doc({"doctype":"User","email":email,"first_name":fn,"last_name":ln,"send_welcome_email":0,"new_password":"Surrey-Demo-2026!","roles":[{"role":"Employee"},{"role":"Employee Self Service"}]}).insert()
        emp = frappe.db.get_value("Employee",{"user_id":email})
        if not emp:
            e = frappe.get_doc({"doctype":"Employee","first_name":fn,"last_name":ln,"gender":g,"date_of_birth":f"199{i}-0{i+1}-15","date_of_joining":"2025-01-06","company":co,"user_id":email,"status":"Active"}).insert()
            emp = e.name
            sa = frappe.get_doc({"doctype":"Shift Assignment","employee":emp,"shift_type":"General 9-5:30","company":co,"start_date":"2026-10-01","shift_location":"Guildford Office"}); sa.insert(); sa.submit()
        d = getdate("2026-10-26")
        for k in range(5):
            day = add_days(d,k)
            for lt,h,m in (("IN",8,random.randint(40,59)),("OUT",17,random.randint(30,59))):
                ts = get_datetime(f"{day} {h:02d}:{m:02d}:00")
                if frappe.db.exists("Employee Checkin",{"employee":emp,"time":ts}): continue
                frappe.get_doc({"doctype":"Employee Checkin","employee":emp,"log_type":lt,"time":ts,"device_id":"Mobile app",
                    "latitude":LAT+random.uniform(-0.0008,0.0008),"longitude":LON+random.uniform(-0.0008,0.0008)}).insert()
    frappe.db.commit()
    # show the radius check rejecting a far-away check-in
    try:
        frappe.get_doc({"doctype":"Employee Checkin","employee":frappe.db.get_value("Employee",{"user_id":"asha@example.com"}),"log_type":"IN","time":"2026-10-31 09:05:00","latitude":51.5074,"longitude":-0.1278}).insert()
        print("far check-in ACCEPTED (unexpected)")
    except Exception as ex:
        print("far check-in rejected:", ex)
    frappe.db.rollback()
    from hrms.hr.doctype.shift_type.shift_type import process_auto_attendance_for_all_shifts
    process_auto_attendance_for_all_shifts(); frappe.db.commit()
    print("employees", frappe.db.count("Employee"), "checkins", frappe.db.count("Employee Checkin"), "attendance", frappe.db.count("Attendance"))
