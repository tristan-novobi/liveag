# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BuyerNumber(models.Model):
    _name = 'buyer.number'
    _description = 'Buyer Numbers'
    _order = "id"

    name = fields.Char('Number')
    active = fields.Boolean('Active',default=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Buyer")

    @api.constrains('name')
    def _check_duplicated_buyer_number(self):
        for record in self:
            value_esc = record.name.replace('_', '\\_').replace('%', '\\%')
            if self.with_context(active_test=False).search([('id', '!=', record.id), ('name', '=ilike', value_esc)]):
                raise ValidationError(_(f'Buyer number {record.name} already exists.'))