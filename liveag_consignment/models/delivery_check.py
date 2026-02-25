# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class DeliveryCheck(models.Model):
    """Model for individual check entries in a delivery"""
    _name = 'consignment.delivery.check'
    _description = 'Delivery Check Entry'
    
    delivery_id = fields.Many2one(
        comodel_name='consignment.delivery',
        string='Delivery',
        required=True,
        ondelete='cascade')
    
    check_number = fields.Char(
        string='Check #',
        help='Check number for payment')
    
    payable_to = fields.Char(
        string='Payable to Whom & Lienholder',
        help='Entity to whom payment is made')
    
    check_amount = fields.Float(
        string='Check Amount',
        help='Amount of the check')
    
    currency_id = fields.Many2one(
        related='delivery_id.currency_id',
        readonly=True)
    
    is_primary = fields.Boolean(
        string='Is Primary Check',
        default=False,
        help='Indicates if this is the primary check calculated from contract information')