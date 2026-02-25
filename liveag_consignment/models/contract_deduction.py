from odoo import models, fields, api

class ContractDeduction(models.Model):
    _name = 'contract.deduction'
    _description = 'Deduction of a contract'

    DEDUCTION_TYPE = [
        ('commission', 'Commission'),
        ('part_payment', 'Part Payment'),
        ('consigment_fee', 'Consignment Fee'),
        ('us_beef_checkoff', 'US Beef Checkoff'),
        ('state_beef_checkoff', 'State Beef Checkoff'),
        ('freight_adjustment_amount', 'Freight Adjustment'),
        ('other', 'Other'),
    ]
    name = fields.Char(string='Name')
    deduction_type = fields.Selection(DEDUCTION_TYPE, 
                                      string='Type',
                                      required=True)
    
    contract_id = fields.Many2one(comodel_name='consignment.contract',
                                    copy=False,
                                    string='Contract')
    debit = fields.Float(string='Debit')
    credit = fields.Float(string='Credit')
    state_id = fields.Many2one(comodel_name='res.country.state',
                                 string='State')
    commission = fields.Float(string='Commission')
    state_beef_checkoff = fields.Float(related='state_id.beef_checkoff',)
 