from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re

class ResPartnerEmail(models.Model):
    _name = 'res.partner.email'
    _description = 'Partner Additional Email'
    _order = 'sequence, id'  # This will order by sequence first

    sequence = fields.Integer('Sequence', default=10)
    name = fields.Char('Email', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='cascade')

    @api.constrains('name')
    def _check_email_validity(self):
        for record in self:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", record.name):
                raise ValidationError(_("Please enter a valid email address"))

    _unique_email_partner = models.Constraint(
        'unique(name, partner_id)',
        "This email address already exists for this partner!",
    ) 