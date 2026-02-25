from odoo import api, fields, models, _

class DeliveryAdjustment(models.Model):
    """Model for individual adjustment entries in a delivery"""
    _name = 'consignment.delivery.adjustment'
    _description = 'Delivery Adjustment Entry'
    
    delivery_id = fields.Many2one(
        comodel_name='consignment.delivery',
        string='Delivery',
        required=True,
        ondelete='cascade')
    
    currency_id = fields.Many2one(
        related='delivery_id.currency_id',
        readonly=True)
        
    adjustment_type = fields.Selection(
        string='Adjustment Type',
        selection=[
            ('rep', 'Rep Adjustment'),
            ('company', 'Company Adjustment'),
            ('seller', 'Seller Adjustment')
        ],
        help='Type of adjustment')
    
    adjustment_amount = fields.Float(
        string='Amount',
        help='Amount of the adjustment')
    
    adjustment_description = fields.Char(
        string='Description',
        help='Description of the adjustment')
    
    adjustment_type_display = fields.Char(
        string='Adjustment Type Display',
        compute='_compute_adjustment_type_display',
        store=False)
    
    @api.depends('adjustment_type')
    def _compute_adjustment_type_display(self):
        """Compute the display name for adjustment type"""
        for record in self:
            if record.adjustment_type:
                selection_dict = dict(record._fields['adjustment_type'].selection)
                record.adjustment_type_display = selection_dict.get(record.adjustment_type, record.adjustment_type)
            else:
                record.adjustment_type_display = ''
    
