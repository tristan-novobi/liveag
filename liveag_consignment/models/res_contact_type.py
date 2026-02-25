# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ContractType(models.Model):
    _name = 'res.contact.type'
    _description = 'Contact types'
    _order = "id"

    name = fields.Char('Type')
    active = fields.Boolean('Active',default=True)

    @api.constrains('name')
    def _check_duplicated_contact_type(self):
        for record in self:
            value_esc = record.name.replace('_', '\\_').replace('%', '\\%')
            if self.with_context(active_test=False).search([('id', '!=', record.id), ('name', '=ilike', value_esc)]):
                raise ValidationError(_(f'Contact type {record.name} already exists.'))