# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleType(models.Model):
    _name = 'sale.type'
    _description = 'Sale Type'
    _order = "sequence, id"

    def _default_sequence(self):
        rec = self.search([], limit=1, order="sequence DESC")
        return rec.sequence and rec.sequence + 1 or 1

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer("Sequence", default=_default_sequence)

    @api.constrains('name')
    def _check_duplicated_sale_type(self):
        for record in self:
            value_esc = record.name.replace('_', '\\_').replace('%', '\\%')
            if self.with_context(active_test=False).search([('id', '!=', record.id), ('name', '=ilike', value_esc)]):
                raise ValidationError(_(f'Sale Type {record.name} already exists.'))
