from odoo import models, fields, api

class Draft(models.Model):
    _name = 'draft'
    _description = 'Draft of cattle in a contract'
    name = fields.Char(string='Draft Number')
    contract_id = fields.Many2one(comodel_name='consignment.contract',
                                  copy=False,
                                  string='Contract')
    head_count = fields.Integer(string='Head Count')
    weight = fields.Float(string='Weight (lb)')
    weight_average = fields.Float(string='Weight Average (lb)', compute='_compute_weight_average')



    @api.depends('head_count', 'weight')
    def _compute_weight_average(self):
        for record in self:
            record.weight_average = record.weight / record.head_count if record.head_count else 0