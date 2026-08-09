import frappe
from frappe import _
from frappe.utils import validate_email_address
from buildpolaris_bff.infrastructure.crypto_utils import generate_secure_token
from buildpolaris_bff.infrastructure.security_log import log_security_event
from buildpolaris_bff.infrastructure.erpnext_bridge import sudo_as_administrator
from buildpolaris_bff.install import get_platform_role_names
import hashlib

def register_tenant(company_name: str, admin_email: str, admin_first_name: str):
    validate_email_address(admin_email, throw=True)
    
    if frappe.db.exists("Company", company_name):
        frappe.throw(_("Company already exists"))
        
    raw_token, hashed_token = generate_secure_token()
    
    with sudo_as_administrator():
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": company_name,
            "default_currency": "USD",
            "country": "United States",
        }).insert(ignore_permissions=True)
        
        user = frappe.get_doc({
            "doctype": "User",
            "email": admin_email,
            "first_name": admin_first_name,
            "company": company.name,
            "enabled": 0,
            "user_type": "System User"
        })
        user.insert(ignore_permissions=True)
        
        # Store hashed token in Redis cache with 24h expiry (86400 seconds)
        frappe.cache().set_value(f"bp_activation:{hashed_token}", admin_email, expires_in_sec=86400)
        
        log_security_event("Token Issued", "Success", user=admin_email, details=f"Tenant registration for {company_name}")
        
        # TODO: Integrate email service to send the raw_token to admin_email
        
    return {"status": "pending_activation", "company": company.name, "token": raw_token} # Returning token for local dev testing

def activate_account(token: str, password: str = None):
    hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
    email = frappe.cache().get_value(f"bp_activation:{hashed_token}")
    
    if not email:
        log_security_event("Token Consumed", "Failure", details="Invalid or expired activation token")
        frappe.throw(_("Invalid or expired token"))
        
    with sudo_as_administrator():
        user = frappe.get_doc("User", email)
        user.enabled = 1
        if password:
            user.new_password = password
            
        platform_roles = get_platform_role_names()
        if platform_roles and not any(r.role == platform_roles[0] for r in user.roles):
            user.append("roles", {"role": platform_roles[0]})
            
        user.save(ignore_permissions=True)
        frappe.cache().delete_value(f"bp_activation:{hashed_token}")
        log_security_event("Token Consumed", "Success", user=email, details="Account activated")
        
    return {"status": "activated"}

def resend_activation(email: str):
    # Placeholder for resend logic
    return {"status": "resent"}
