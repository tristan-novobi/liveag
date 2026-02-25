from odoo import api, fields, models
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class MergeOptionContractsWizard(models.TransientModel):
    _name = 'merge.deliveries.wizard'
    _description = 'Merge Deliveries Wizard'

    base_delivery_id = fields.Many2one(comodel_name='consignment.delivery',
        string='Base Delivery')

    option_delivery_ids = fields.Many2many('consignment.delivery',string='Option deliveries')


    def action_merge(self):
        deliveries = self.option_delivery_ids.filtered(lambda delivery: delivery.to_be_merged) + self.base_delivery_id
        deliveries.merge_deliveries(base_delivery_id=self.base_delivery_id)
        
        self.option_delivery_ids.write({'to_be_merged':False})