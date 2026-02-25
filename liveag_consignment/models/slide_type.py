# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SlideType(models.Model):
    _name = 'slide.type'
    _description = 'Slide Type'
    _order = "sequence, id"

    def _default_sequence(self):
        rec = self.search([], limit=1, order="sequence DESC")
        return rec.sequence and rec.sequence + 1 or 1

    name = fields.Char(string='Name', required=True)
    label = fields.Char(string='Display Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer("Sequence", default=_default_sequence)
    above = fields.Boolean(string='Over', default=False)
    under = fields.Boolean(string='Under', default=False)
    both = fields.Boolean(string='Both', default=False)
    sell_by_head = fields.Boolean(string="Sell By Head")
    description = fields.Text(string="Description")
    