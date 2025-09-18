# order_form.py
import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

# Allowed forward-only status transitions
ALLOWED_NEXT = {
    "Pending": ["In Progress"],
    "In Progress": ["Completed"],
    "Completed": ["Delivered"],
    "Delivered": []
}

class OrderForm(Document):
    def before_insert(self):
        # Ensure default status on new docs
        if not self.get("status"):
            self.status = "Pending"

    def validate(self):
        """Enforce forward-only status changes (no skipping)."""
        if not self.is_new():
            old_status = frappe.db.get_value(self.doctype, self.name, "status")
            if old_status and self.status != old_status:
                allowed = ALLOWED_NEXT.get(old_status, [])
                if self.status not in allowed:
                    frappe.throw(
                        f"Invalid status change from <b>{old_status}</b> to <b>{self.status}</b>. "
                        f"Allowed next: {', '.join(allowed) if allowed else 'None'}."
                    )

@frappe.whitelist()
def make_order_form_from_sales_invoice(source_name, target_doc=None):
    """Your existing flow: map one Order Form with ALL items (unchanged)."""
    def _set_parent_vals(source, target):
        target.from_sales_invoice = source.name
        if not target.get("status"):
            target.status = "Pending"

    doc = get_mapped_doc(
        "Sales Invoice",
        source_name,
        {
            "Sales Invoice": {
                "doctype": "Order Form",
                "field_map": {
                    "customer": "customer",
                    "customer_name": "customer_name",
                    "posting_date": "posting_date",
                },
                "validation": {"docstatus": ["=", 1]},
            },
            "Sales Invoice Item": {
                "doctype": "Order Form Item",
                "field_map": {
                    "item_code": "item",
                    "description": "description",
                    "qty": "qty",
                    "measurement": "measurement",
                    "specification": "specification",
                },
            },
        },
        target_doc,
        _set_parent_vals,
    )
    return doc

# ---------------- NEW: dialog helpers for one-Order-Form-per-selected-item ----------------

@frappe.whitelist()
def get_sales_invoice_items(source_name):
    """Return SI items for the dialog; disable those already converted if backlink exists."""
    has_backlink = frappe.db.has_column("Order Form Item", "from_sales_invoice_item")

    already = set()
    if has_backlink:
        already = set(
            frappe.get_all(
                "Order Form Item",
                filters={"from_sales_invoice_item": ["is", "set"]},
                pluck="from_sales_invoice_item",
            )
        )

    rows = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": source_name},
        fields=["name", "idx", "item_code", "description", "qty"],
    )

    for r in rows:
        r["disabled"] = has_backlink and (r["name"] in already)
    return rows


@frappe.whitelist()
def make_order_forms_from_sales_invoice(source_name, selected_child_names: str):
    """
    Create one Order Form per selected Sales Invoice Item row.
    Skips items already converted (when backlink exists).
    Returns list of created Order Form names.
    """
    selected = frappe.parse_json(selected_child_names or "[]")
    if not selected:
        frappe.throw("Please select at least one item.")

    created = []
    has_backlink = frappe.db.has_column("Order Form Item", "from_sales_invoice_item")

    for child_name in selected:
        if has_backlink and frappe.db.exists("Order Form Item", {"from_sales_invoice_item": child_name}):
            continue

        def _set_parent_vals(source, target):
            target.from_sales_invoice = source.name
            if not target.get("status"):
                target.status = "Pending"

        child_field_map = {
            "item_code": "item",
            "description": "description",
            "qty": "qty",
            "measurement": "measurement",
            "specification": "specification",
        }
        if has_backlink:
            child_field_map["name"] = "from_sales_invoice_item"

        doc = get_mapped_doc(
            "Sales Invoice",
            source_name,
            {
                "Sales Invoice": {
                    "doctype": "Order Form",
                    "field_map": {
                        "customer": "customer",
                        "customer_name": "customer_name",
                        "posting_date": "posting_date",
                    },
                    "validation": {"docstatus": ["=", 1]},
                },
                "Sales Invoice Item": {
                    "doctype": "Order Form Item",
                    "field_map": child_field_map,
                    "condition": lambda d: d.name == child_name,
                },
            },
            None,
            _set_parent_vals,
        )

        if not doc.get("items"):
            continue

        try:
            doc.insert(ignore_permissions=True)   # keep Draft; call doc.submit() if needed
            created.append(doc.name)
        except Exception as e:
            # If DB has a UNIQUE constraint on from_sales_invoice_item, ignore duplicate inserts
            if "Duplicate entry" in str(e) or "unique constraint" in str(e).lower():
                continue
            raise

    return created
