# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WeightStop(models.Model):
    _name = 'weight.stop'
    _description = 'Weight Stop'
    _order = "sequence, id"

    def _default_sequence(self):
        rec = self.search([], limit=1, order="sequence DESC")
        return rec.sequence and rec.sequence + 1 or 1

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer("Sequence", default=_default_sequence)
    value = fields.Integer("Value", required=False, help="If set to 0, this will be the stop value. If left empty (null), this weight stop will not be applied.")
    icon = fields.Many2one(
        comodel_name='program.icon',
        string="Icon")

    @api.constrains('name')
    def _check_duplicated_weight_stop(self):
        for record in self:
            value_esc = record.name.replace('_', '\\_').replace('%', '\\%')
            if self.with_context(active_test=False).search([('id', '!=', record.id), ('name', '=ilike', value_esc)]):
                raise ValidationError(_(f'Weight Stop {record.name} already exists.'))
