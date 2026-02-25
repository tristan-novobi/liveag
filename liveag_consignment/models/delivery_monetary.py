# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class DeliveryMonetary(models.AbstractModel):
    """Mixin for monetary fields in delivery"""
    _name = 'delivery.monetary.mixin'
    _description = 'Delivery Monetary Fields Mixin'

    # Currency field for monetary fields
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        help='Currency used for monetary fields')
    
    # Monetary fields with currency_id
    price_adjustment_monetary = fields.Monetary(
        string='Price Adjustment',
        compute='_compute_price_adjustment_monetary',
        currency_field='currency_id',
        store=True,
        help='Price adjustment based on slide')
    
    adjusted_price_monetary = fields.Monetary(
        string='Adjusted Price',
        compute='_compute_adjusted_price_monetary',
        currency_field='currency_id',
        store=True,
        help='Price after slide adjustment')
    
    gain_price_monetary = fields.Monetary(
        string='Gain Price',
        currency_field='currency_id',
        help='Price per pound for weight gain')
    
    base_weight_payment_monetary = fields.Monetary(
        string='Base Weight Payment',
        compute='_compute_gain_slide_payments_monetary',
        currency_field='currency_id',
        store=True,
        help='Payment for base weight in gain slide')
    
    weight_gain_payment_monetary = fields.Monetary(
        string='Weight Gain Payment',
        compute='_compute_gain_slide_payments_monetary',
        currency_field='currency_id',
        store=True,
        help='Payment for weight gain in gain slide')
    
    gross_amount_monetary = fields.Monetary(
        string='Gross Amount',
        compute='_compute_gross_amount_monetary',
        currency_field='currency_id',
        store=True,
        help='Total gross amount before deductions')
    
    part_payment_monetary = fields.Monetary(
        string='Part Payment',
        currency_field='currency_id',
        help='Partial payment amount')
    
    gross_commission_monetary = fields.Monetary(
        string='Gross Commission',
        compute='_compute_commissions_monetary',
        currency_field='currency_id',
        store=True,
        help='Gross commission amount')
    
    per_head_commission_monetary = fields.Monetary(
        string='$2 Per Head Commission',
        compute='_compute_commissions_monetary',
        currency_field='currency_id',
        store=True,
        help='Commission calculated per head')
    
    total_commission_monetary = fields.Monetary(
        string='Total Commission Deducted',
        compute='_compute_commissions_monetary',
        currency_field='currency_id',
        store=True,
        help='Total commission amount deducted')
    
    beef_check_off_monetary = fields.Monetary(
        string='Beef Check Off',
        compute='_compute_beef_check_off_monetary',
        currency_field='currency_id',
        store=True,
        help='Beef check off amount')
    
    other_deductions_monetary = fields.Monetary(
        string='Other Deductions',
        currency_field='currency_id',
        help='Any other deductions')
    
    total_deductions_monetary = fields.Monetary(
        string='Total Deductions',
        compute='_compute_total_deductions_monetary',
        currency_field='currency_id',
        store=True,
        help='Sum of all deductions')
    
    net_proceeds_monetary = fields.Monetary(
        string='Net Proceeds',
        compute='_compute_net_proceeds_monetary',
        currency_field='currency_id',
        store=True,
        help='Net amount after all deductions')
    
    # check_amount_monetary = fields.Monetary(
    #     string='Check Amount',
    #     compute='_compute_check_amount_monetary',
    #     currency_field='currency_id',
    #     store=True,
    #     help='Amount of the check')
    
    adjustments_monetary = fields.Monetary(
        string='Adjustments',
        currency_field='currency_id',
        help='Any adjustments to the payment')
    
    gross_amount_due_monetary = fields.Monetary(
        string='Gross Amount Due',
        compute='_compute_gross_amount_monetary',
        currency_field='currency_id',
        store=True,
        help='Gross amount due from buyer')
    
    buyer_part_payment_monetary = fields.Monetary(
        string='Part Payment',
        currency_field='currency_id',
        help='Partial payment from buyer')
    
    buyer_adjustment_monetary = fields.Monetary(
        string='Adjustment',
        currency_field='currency_id',
        help='Adjustment to buyer payment')
    
    total_due_monetary = fields.Monetary(
        string='Total Due',
        compute='_compute_total_due_monetary',
        currency_field='currency_id',
        store=True,
        help='Total amount due from buyer')
    
    # Monetary field computations
    @api.depends('price_adjustment')
    def _compute_price_adjustment_monetary(self):
        for record in self:
            record.price_adjustment_monetary = record.price_adjustment
    
    @api.depends('adjusted_price')
    def _compute_adjusted_price_monetary(self):
        for record in self:
            record.adjusted_price_monetary = record.adjusted_price
    
    @api.depends('base_weight_payment', 'weight_gain_payment')
    def _compute_gain_slide_payments_monetary(self):
        for record in self:
            record.base_weight_payment_monetary = record.base_weight_payment
            record.weight_gain_payment_monetary = record.weight_gain_payment
    
    @api.depends('gross_amount', 'gross_amount_due')
    def _compute_gross_amount_monetary(self):
        for record in self:
            record.gross_amount_monetary = record.gross_amount
            record.gross_amount_due_monetary = record.gross_amount_due
    
    @api.depends('gross_commission', 'per_head_commission', 'total_commission')
    def _compute_commissions_monetary(self):
        for record in self:
            record.gross_commission_monetary = record.gross_commission
            record.per_head_commission_monetary = record.per_head_commission
            record.total_commission_monetary = record.total_commission
    
    @api.depends('beef_check_off')
    def _compute_beef_check_off_monetary(self):
        for record in self:
            record.beef_check_off_monetary = record.beef_check_off
    
    @api.depends('total_deductions')
    def _compute_total_deductions_monetary(self):
        for record in self:
            record.total_deductions_monetary = record.total_deductions
    
    @api.depends('net_proceeds')
    def _compute_net_proceeds_monetary(self):
        for record in self:
            record.net_proceeds_monetary = record.net_proceeds
    
    # @api.depends('check_amount')
    # def _compute_check_amount_monetary(self):
    #     for record in self:
    #         record.check_amount_monetary = record.check_amount
    
    @api.depends('total_due')
    def _compute_total_due_monetary(self):
        for record in self:
            record.total_due_monetary = record.total_due