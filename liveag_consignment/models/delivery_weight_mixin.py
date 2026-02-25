# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class DeliveryWeightMixin(models.AbstractModel):
    """Mixin for weight-related calculations in delivery"""
    _name = 'delivery.weight.mixin'
    _description = 'Delivery Weight Calculation Mixin'

    # Weight Fields
    gross_weight = fields.Float(
        string='Gross Weight',
        help='Total gross weight of the delivery')
    
    shrink_percentage = fields.Float(
        string='Shrink %',
        default=2.0)
    
    net_weight = fields.Float(
        string='Net Weight',
        compute='_compute_net_weight',
        store=True,
        help='Net weight after shrink')
    
    average_weight = fields.Float(
        string='Average Weight',
        compute='_compute_average_weight',
        store=True,
        help='Average weight per head')
    
    weight_stop_id = fields.Many2one(
        comodel_name='weight.stop',
        string="Weight Stop")
    
    weight_difference = fields.Float(
        string='Weight Difference',
        compute='_compute_weight_difference',
        store=True,
        help='Difference between average weight and contract weight')
    
    is_overweight = fields.Boolean(
        string='Is Overweight',
        compute='_compute_weight_difference',
        store=True,
        help='True if actual weight is over contract weight')
    
    is_underweight = fields.Boolean(
        string='Is Underweight',
        compute='_compute_weight_difference',
        store=True,
        help='True if actual weight is under contract weight')
    
    capped_net_weight = fields.Float(
        string='Capped Net Weight',
        compute='_compute_totals',
        help='Total capped net weight including split lines')
    
    max_weight_adjustment = fields.Float(
        string='Max Weight Adjustment',
        default=25.0,
        help='Maximum weight adjustment in pounds (typically 25 lbs)')
    
    adjusted_weight_difference = fields.Float(
        string='Adjusted Weight Difference',
        compute='_compute_adjusted_weight_difference',
        store=True,
        help='Weight difference after applying max adjustment')
    
    # Computed Methods
    @api.depends('gross_weight', 'shrink_percentage')
    def _compute_net_weight(self):
        """Calculate net weight after shrink"""
        for record in self:
            record.net_weight = record.gross_weight * (1 - record.shrink_percentage / 100)
    
    @api.depends('net_weight', 'head_count')
    def _compute_average_weight(self):
        """Calculate average weight per head"""
        for record in self:
            divisor = record.head_count or 1  # Avoid division by zero
            record.average_weight = record.net_weight / divisor
    
    def _compute_weight_stop(self):
        """This method should be implemented in the main model"""
        pass
    
    def _compute_weight_difference(self):
        """This method should be implemented in the main model"""
        pass
    
    @api.depends('weight_difference', 'max_weight_adjustment', 'is_overweight', 'is_underweight')
    def _compute_adjusted_weight_difference(self):
        """Calculate adjusted weight difference with max cap for overweight"""
        for record in self:
            # For overweight, cap at max_weight_adjustment
            overweight_adjustment = min(record.weight_difference, record.max_weight_adjustment) if record.is_overweight else 0
            
            # For underweight, use actual difference (negative value)
            underweight_adjustment = record.weight_difference if record.is_underweight else 0
            
            # Use the appropriate adjustment based on weight status
            record.adjusted_weight_difference = overweight_adjustment + underweight_adjustment