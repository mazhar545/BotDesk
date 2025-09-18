# bot_desk/customer_dashboard.py
from erpnext.selling.doctype.customer.customer_dashboard import get_data as core_get_data

def get_data(data=None, *args, **kwargs):
    """
    Compatible with Frappe/ERPNext v15 where the override may be called with data=...
    If data is provided, extend it. Otherwise, build from core and extend.
    """
    base = data if isinstance(data, dict) else core_get_data(*args, **kwargs)

    # ensure required keys exist
    base.setdefault("transactions", [])
    base.setdefault("non_standard_fieldnames", {})

    # Put all three under one group (or split into multiple if you prefer)
    section = {"label": "Tailor Module Docs", "items": ["Order Form", "Specification", "Measurement"]}
    # avoid duplicating on repeated calls
    if section not in base["transactions"]:
        base["transactions"].append(section)

    # If your link field isn't exactly 'customer', map it here:
    # base["non_standard_fieldnames"].update({
    #     "Order Form": "customer",
    #     "Specification": "customer",
    #     "Measurement": "customer",
    # })

    return base
