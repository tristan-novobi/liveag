# models/res_users.py
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = "res.users"

    clerk_user_id = fields.Char(index=True)
    
    _clerk_user_id_uniq = models.Constraint(
        'unique(clerk_user_id)',
        "Clerk user ID must be unique.",
    )