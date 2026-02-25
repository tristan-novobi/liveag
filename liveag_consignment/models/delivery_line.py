# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging
from ..tools import round_half_up

_logger = logging.getLogger(__name__)

class DeliveryLine(models.Model):
    """Model for individual line items in a delivery"""
    _name = 'consignment.delivery.line'
    _description = 'Delivery Line Item'
    _order = 'sequence, id'
    _inherit = [
        'mail.thread', 
        'mail.activity.mixin',
        'delivery.weight.mixin',
        'delivery.slide.mixin'
    ]
    
    sequence = fields.Integer(
        string='Sequence',
        default=lambda self: self._get_default_sequence(),
        store=True,
        help='Order of the line items')
    
    delivery_id = fields.Many2one(
        comodel_name='consignment.delivery',
        string='Delivery',
        required=True,
        ondelete='cascade')
    
    head_group = fields.Selection(
        [('1', 'Head 1'), ('2', 'Head 2')],
        string='Head Group',
        help="Indicates which head group from the contract this line corresponds to. Leave empty for lines not tied to a specific head group.")
    
    head_count = fields.Integer(
        string='# Head',
        help='Number of head in this line')
    
    description = fields.Char(
        string='Description',
        help='Description of the line item')
    
    gross_weight = fields.Float(
        string='Gross Wt',
        help='Total gross weight of this line')
    
    def _get_default_shrink(self):
        """Get default shrink percentage from delivery's contract"""
        delivery_id = self.env.context.get('default_delivery_id')
        
        if not delivery_id:
            delivery_id = self.env.context.get('active_id')
        
        if delivery_id:
            delivery = self.env['consignment.delivery'].browse(delivery_id)
            if delivery.exists() and delivery.contract_id:
                if delivery.contract_id.shrink_percentage is not False and delivery.contract_id.shrink_percentage is not None:
                    return delivery.contract_id.shrink_percentage
        return 0.0

    shrink_percentage = fields.Float(
        string='Shrink %',
        digits=(5, 1),
        store=True,
        readonly=False,
        default=lambda self: self._get_default_shrink(),
        help='Shrink percentage for this line')
    
    @api.onchange('delivery_id')
    def _onchange_delivery_id(self):
        """Auto-populate shrink percentage when delivery is set"""
        if self.delivery_id and self.delivery_id.contract_id:
            if not self.shrink_percentage and not self.is_gain_line:
                if self.delivery_id.contract_id.shrink_percentage is not False and self.delivery_id.contract_id.shrink_percentage is not None:
                    self.shrink_percentage = self.delivery_id.contract_id.shrink_percentage
                else:
                    self.shrink_percentage = 0.0
    
    net_weight = fields.Float(
        string='Net Weight',
        compute='_compute_net_weight',
        store=True,
        readonly=False,
        help='Net weight after shrink')
    
    average_weight = fields.Float(
        string='Avg. Wt.',
        compute='_compute_average_weight',
        store=True,
        readonly=False,
        help='Average weight per head')
        
    capped_average_weight = fields.Float(
        string='Capped Avg. Wt.',
        compute='_compute_capped_weights',
        store=True,
        readonly=False,
        help='Capped average weight per head based on weight stop')
        
    capped_net_weight = fields.Float(
        string='Capped Net Weight',
        compute='_compute_capped_weights',
        store=True,
        readonly=False,
        help='Capped net weight based on weight stop')
    
    display_weight = fields.Char(
        string='Net Weight',
        compute='_compute_display_weight',
        store=True,
        help='Display net weight with max payable weight in parentheses when applicable')

    display_average_weight = fields.Char(
        string='Avg. Wt.',
        compute='_compute_display_average_weight',
        store=True,
        help='Display average weight with max payable weight in parentheses when applicable')

    price = fields.Monetary(
        string='Price',
        currency_field='currency_id',
        compute='_compute_slide_price',
        store=True,
        readonly=False,
        help='Price')
    
    is_per_pound = fields.Boolean(
        string='Is Per Pound',
        default=False,
        help='If true, the price is per pound')
    
    is_price_back = fields.Boolean(
        string='Is Price Back',
        default=False,
        help='If true, the price is a price back')
    
    is_gain_line = fields.Boolean(
        string='Is Gain Line',
        default=False,
        help='If true, this line represents gain weight for a gain slide')
    
    gross_amount = fields.Monetary(
        string='Gross Amount',
        compute='_compute_gross_amount',
        store=True,
        currency_field='currency_id',
        help='Total gross amount for this line')
    
    currency_id = fields.Many2one(
        related='delivery_id.currency_id',
        store=True)
    
    # Computed fields
    @api.depends('gross_weight', 'shrink_percentage')
    def _compute_net_weight(self):
        """Calculate net weight after applying shrink percentage
        Round to 2 decimal places for precise weight calculations"""
        for record in self:
            # For gain lines, always use 0 shrink percentage
            shrink_percentage = 0 if record.is_gain_line else record.shrink_percentage
            raw_net_weight = round_half_up(record.gross_weight * (1 - shrink_percentage / 100), 2)
            record.net_weight = round_half_up(raw_net_weight)
    
    @api.depends('net_weight', 'head_count')
    def _compute_average_weight(self):
        """Calculate average weight per head using 2-decimal precision then rounding to whole number
        This matches back office calculator behavior: divide, round to 2 decimals, then round to whole number"""
        for record in self:
            divisor = record.head_count or 1  # Avoid division by zero
            # Step 1: Calculate raw average to two decimals (e.g., 846.50)
            two_decimal_average = round_half_up(record.net_weight / divisor, 2)
            # Step 3: Round to whole number (e.g., 847)
            record.average_weight = round_half_up(two_decimal_average)
    
    @api.depends('net_weight', 'price', 'capped_net_weight', 'delivery_id.slide_type', 'delivery_id.slide_over', 
                'delivery_id.slide_under', 'delivery_id.weight_stop_id', 'is_gain_line', 'delivery_id.sell_by_head')
    def _compute_gross_amount(self):
        """Calculate gross amount based on capped net weight and price
        
        When actual average weight exceeds the weight stop, payment is calculated
        using the maximum payable weight allowed.
        """
        for record in self:
            # If sell_by_head is True, multiply price by head count
            if record.delivery_id.sell_by_head:
                record.gross_amount = record.price * record.head_count
                continue

            # If capped_net_weight is 0 (indicating no weight stop), use actual net weight
            weight_to_use = record.net_weight if record.capped_net_weight == 0 else record.capped_net_weight
            
            # For gain lines, multiply price directly by weight
            if record.is_gain_line:
                gross_amount = weight_to_use * record.price
            else:
                # For regular lines, divide by 100 if not per pound
                if record.is_per_pound:
                    gross_amount = weight_to_use * record.price
                else:
                    gross_amount = weight_to_use * record.price / 100
                
            record.gross_amount = gross_amount

    @api.depends('net_weight', 'head_count', 'head_group', 'is_price_back', 'delivery_id.weight_stop_id',
                 'delivery_id.contract_weight', 'delivery_id.contract_weight2', 'delivery_id.contract_id.weight1',
                 'delivery_id.contract_id.weight2', 'average_weight', 'delivery_id.is_gain_slide',
                 'delivery_id.weight_stop_id.name', 'delivery_id.weight_stop_id.value')
    def _compute_capped_weights(self):
        """Calculate capped weights based on weight stop and slide type"""
        for record in self:
            # Skip calculations for gain lines as they don't need capping
            if record.is_gain_line:
                record.capped_average_weight = 0
                record.capped_net_weight = record.net_weight
                continue

            # Get the appropriate contract weight based on head_group
            contract_weight = 0
            if record.head_group:
                # If head_group is set, use the corresponding weight from the contract
                if record.head_group == '1':
                    contract_weight = max(0, record.delivery_id.contract_weight or 0)
                elif record.head_group == '2':
                    contract_weight = max(0, record.delivery_id.contract_weight2 or 0)
            else:
                # If head_group is not set, fall back to the delivery's contract_weight
                contract_weight = max(0, record.delivery_id.contract_weight or 0)

            # For gain slides, main line is always capped at contract weight
            if record.delivery_id and record.delivery_id.is_gain_slide:
                # Main line is always capped at contract weight * head_count
                max_base_weight = contract_weight * record.head_count
                record.capped_net_weight = round_half_up(min(record.net_weight, max_base_weight))
                record.capped_average_weight = record.capped_net_weight / record.head_count if record.head_count else 0
            else:
                # For non-gain slides, handle weight stop normally
                if record.delivery_id and record.delivery_id.weight_stop_id.name == 'None':
                    record.capped_average_weight = 0
                    record.capped_net_weight = 0
                    continue

                # Get the weight stop value
                weight_stop = record.delivery_id.weight_stop_id.value if record.delivery_id else 0
                
                # Calculate the maximum payable weight (contract weight + weight stop)
                max_payable_weight = contract_weight + weight_stop
                
                # For True Stop, cap at contract weight
                if record.delivery_id and record.delivery_id.weight_stop_id.name == 'True Stop':
                    max_payable_weight = contract_weight
                
                # Calculate capped average weight
                if record.average_weight > max_payable_weight:
                    record.capped_average_weight = max_payable_weight
                else:
                    record.capped_average_weight = record.average_weight
                    
                if record.average_weight > max_payable_weight:
                    # For other slide types, cap at max_payable_weight if over
                    record.capped_net_weight = round_half_up(max_payable_weight * record.head_count)
                else:
                    # Otherwise use actual net weight
                    record.capped_net_weight = record.net_weight

    def _manage_gain_lines(self):
        """Manage creation, update, or removal of gain lines based on slide type and weight stop"""
        if not self.delivery_id:
            return
        
        if self.delivery_id.is_gain_slide:
            # Calculate gain weight with cap
            contract_weight = max(0, self.delivery_id.contract_weight2 if self.head_group == '2' else self.delivery_id.contract_weight or 0)
            potential_gain_weight = self.net_weight - (contract_weight * self.head_count)
            
            # Check if weight stop is "None" (no cap) or has a value
            if self.delivery_id.weight_stop_id and self.delivery_id.weight_stop_id.name == 'None':
                # No cap on gain weight
                gain_weight = potential_gain_weight if potential_gain_weight > 0 else 0
            else:
                # Cap gain weight based on weight stop value
                weight_stop = self.delivery_id.weight_stop_id.value if self.delivery_id.weight_stop_id else 0
                max_gain_weight = weight_stop * self.head_count
                gain_weight = min(potential_gain_weight, max_gain_weight) if potential_gain_weight > 0 else 0
            
            if gain_weight > 0 and self.delivery_id.slide_over:
                # Find or create gain line
                gain_line = self.delivery_id.line_ids.filtered(lambda l: l.head_group == self.head_group and l.is_gain_line)
                vals = {
                    'head_group': self.head_group,
                    'head_count': 0,
                    'description': f"Gain Slide",
                    'gross_weight': gain_weight,
                    'net_weight': gain_weight,
                    'average_weight': 0,
                    'price': self.delivery_id.slide_over / 100,
                    'is_gain_line': True,
                    'shrink_percentage': 0,
                    'sequence': self.sequence + 1,
                }
                if gain_line:
                    gain_line.with_context(managing_gain=True).write(vals)
                else:
                    self.delivery_id.write({'line_ids': [(0, 0, vals)]})
            else:
                # Remove gain line if no gain or no slide_over
                gain_line = self.delivery_id.line_ids.filtered(lambda l: l.head_group == self.head_group and l.is_gain_line)
                if gain_line:
                    gain_line.unlink()
        else:
            # Remove all gain lines for non-gain slides
            gain_lines = self.delivery_id.line_ids.filtered(lambda l: l.is_gain_line)
            if gain_lines:
                gain_lines.unlink()

    @api.onchange('gross_weight', 'shrink_percentage', 'head_count')
    def _onchange_weight(self):
        """Trigger gain line management when weight or head count changes"""
        if self.delivery_id and self.delivery_id.slide_type:
            self._manage_gain_lines()

    @api.depends('average_weight', 'delivery_id.base_price', 'delivery_id.slide_type',
                'delivery_id.slide_type.name', 'delivery_id.slide_over',
                'delivery_id.slide_under', 'delivery_id.slide_both',
                'delivery_id.contract_weight', 'delivery_id.contract_weight2', 'delivery_id.slide_type.above',
                'delivery_id.slide_type.under', 'delivery_id.slide_type.both',
                'net_weight', 'head_count', 'gross_weight', 'shrink_percentage',
                'delivery_id.weight_stop_id', 'delivery_id.weight_stop_id.name',
                'delivery_id.weight_stop_id.value', 'capped_average_weight', 'capped_net_weight',
                'delivery_id.price_back', 'head_group', 'is_gain_line',
                'delivery_id.sell_by_head')
    def _compute_slide_price(self):
        """Calculate the price based on the slide type"""
        for record in self:
            # If sell_by_head is True, use base price
            if record.delivery_id.sell_by_head:
                record.price = record.delivery_id.base_price
                continue
            
            # For gain lines, update price from slide_over
            if record.is_gain_line:
                if record.delivery_id and record.delivery_id.slide_over:
                    record.price = record.delivery_id.slide_over / 100  # Convert cents to dollars
                else:
                    record.price = 0.0
                continue
                
            base_price = record.delivery_id.base_price

            if not record.delivery_id or not record.delivery_id.slide_type:
                record.price = base_price
                continue

            # Use capped average weight for calculations if it's set
            weight_to_use = record.capped_average_weight if record.capped_average_weight > 0 else record.average_weight
            
            # Get the appropriate contract weight based on head_group
            contract_weight = max(0, record.delivery_id.contract_weight2 if record.head_group == '2' else record.delivery_id.contract_weight or 0)
            
            # Calculate weight difference
            weight_diff = weight_to_use - contract_weight
            is_overweight = weight_diff > 0
            is_underweight = weight_diff < 0
            
            # Get price adjustment from mixin
            price_adjustment = record._calculate_price_adjustment(
                record.delivery_id.slide_type.name,
                record.delivery_id.slide_over,
                record.delivery_id.slide_under,
                record.delivery_id.slide_both,
                abs(weight_diff),
                is_overweight,
                is_underweight,
                record.delivery_id.contract_weight,
                record.delivery_id.weight_stop_id.name if record.delivery_id.weight_stop_id else None,
                record.delivery_id.weight_stop_id.value if record.delivery_id.weight_stop_id else None
            )
            
            # Apply price adjustment
            if is_overweight:
                record.price = round_half_up(base_price - price_adjustment, 2)
            elif is_underweight:
                record.price = round_half_up(base_price + price_adjustment, 2)
            else:
                record.price = base_price
                
            # Apply price back adjustment for head group 2
            if record.head_group == '2' and record.delivery_id.price_back:
                record.price = record.price - record.delivery_id.price_back

    @api.model
    def _get_default_sequence(self):
        """Get the next sequence number in increments of 10 for normal lines
        Gain lines will get parent_sequence + 1 when created"""
        # Try to get delivery_id from context first
        delivery_id = self.env.context.get('default_delivery_id')
        
        if delivery_id:
            # Find the last normal line (not gain line) in this delivery
            last_line = self.search([
                ('delivery_id', '=', delivery_id),
                ('is_gain_line', '=', False)
            ], order='sequence desc', limit=1)
            return (last_line.sequence + 10) if last_line else 10
        else:
            # Fallback: find the highest sequence across all normal lines
            last_line = self.search([
                ('is_gain_line', '=', False)
            ], order='sequence desc', limit=1)
            return (last_line.sequence + 10) if last_line else 10
        
    def _compute_sequence(self):
        """Recompute sequences for all lines to ensure proper ordering
        Normal lines get sequences of 10, 20, 30, etc.
        Gain lines get parent_sequence + 1 to appear directly under their parent line"""
        for record in self:
            if not record.delivery_id:
                continue    
            
            # Get all lines sorted by current sequence
            lines = record.delivery_id.line_ids.sorted('sequence')
            
            # Group lines by head_group to handle parent/gain relationships
            normal_lines = lines.filtered(lambda l: not l.is_gain_line)
            gain_lines = lines.filtered(lambda l: l.is_gain_line)
            
            # Assign sequences to normal lines in increments of 10
            sequence_counter = 10
            for line in normal_lines:
                line.sequence = sequence_counter
                
                # Find any gain lines for this parent and assign parent_sequence + 1
                related_gain_lines = gain_lines.filtered(lambda gl: gl.head_group == line.head_group)
                for gain_line in related_gain_lines:
                    gain_line.sequence = line.sequence + 1
                
                sequence_counter += 10

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle sequence for new lines"""
        for vals in vals_list:
            if 'sequence' not in vals:
                vals['sequence'] = self._get_default_sequence()
            # Ensure gain lines always have 0 shrink percentage
            if vals.get('is_gain_line'):
                vals['shrink_percentage'] = 0
        return super().create(vals_list)

    def write(self, vals):
        """Override write to ensure gain lines always have 0 shrink percentage and manage gain lines"""
        result = super().write(vals)
        
        # Check if any fields that affect gain lines have changed, but avoid recursion
        if not self.env.context.get('managing_gain'):
            gain_triggering_fields = ['gross_weight', 'shrink_percentage', 'net_weight', 'head_count', 'head_group']
            if any(field in vals for field in gain_triggering_fields):
                for record in self:
                    if record.delivery_id:
                        record.with_context(managing_gain=True)._manage_gain_lines()
        
        return result

    @api.depends('net_weight', 'capped_net_weight', 'delivery_id.weight_stop_id', 'delivery_id.is_gain_slide')
    def _compute_display_weight(self):
        """Compute display weight showing max payable weight in parentheses when applicable"""
        for record in self:
            # For gain lines, show actual weight only
            if record.is_gain_line:
                record.display_weight = f"{record.net_weight:,.0f}"
            # For gain slides, always show capped weight when different from actual (base weight always capped)
            elif (record.delivery_id and record.delivery_id.is_gain_slide and 
                  record.capped_net_weight and record.net_weight != record.capped_net_weight):
                record.display_weight = f"{record.net_weight:,.0f} ({record.capped_net_weight:,.0f}*)"
            # For non-gain slides, check weight stop
            elif record.delivery_id and record.delivery_id.weight_stop_id.name == 'None':
                record.display_weight = f"{record.net_weight:,.0f}"
            elif record.capped_net_weight and record.net_weight > record.capped_net_weight:
                record.display_weight = f"{record.net_weight:,.0f} ({record.capped_net_weight:,.0f}*)"
            else:
                record.display_weight = f"{record.net_weight:,.0f}"

    @api.depends('average_weight', 'capped_average_weight', 'delivery_id.weight_stop_id', 'delivery_id.is_gain_slide')
    def _compute_display_average_weight(self):
        """Compute display average weight showing max payable weight in parentheses when applicable"""
        for record in self:
            # For gain slides, always show capped weight when different from actual (base weight always capped)
            if (record.delivery_id and record.delivery_id.is_gain_slide and 
                record.capped_average_weight and record.average_weight != record.capped_average_weight):
                record.display_average_weight = f"{record.average_weight:,.0f} ({record.capped_average_weight:,.0f}*)"
            # For non-gain slides, check weight stop
            elif record.delivery_id and record.delivery_id.weight_stop_id.name == 'None':
                record.display_average_weight = f"{record.average_weight:,.0f}"
            elif record.capped_average_weight and record.average_weight > record.capped_average_weight:
                record.display_average_weight = f"{record.average_weight:,.0f} ({record.capped_average_weight:,.0f}*)"
            else:
                record.display_average_weight = f"{record.average_weight:,.0f}"
                
    @api.onchange('head_group')
    def _compute_is_price_back(self):
        """Compute is_price_back based on head_group and is_price_back"""
        for record in self:
            if record.head_group == '2' and record.is_price_back:
                record.is_price_back = True
            else:
                record.is_price_back = False
    
    @api.onchange('is_price_back')
    def _compute_head_group(self):
        """Compute head_group based on is_price_back"""
        for record in self:
            if record.is_price_back:
                record.head_group = '2'
            else:
                record.head_group = '1'

    @api.onchange('is_gain_line')
    def _onchange_is_gain_line(self):
        """Ensure gain lines always have 0 shrink percentage"""
        for record in self:
            if record.is_gain_line:
                record.shrink_percentage = 0