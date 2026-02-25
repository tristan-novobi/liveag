# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from ..tools import round_half_up

class DeliveryFinancialMixin(models.AbstractModel):
    """Mixin for financial calculations in delivery"""
    _name = 'delivery.financial.mixin'
    _description = 'Delivery Financial Calculation Mixin'

    # Financial Information
    gross_amount = fields.Float(
        string='Gross Amount',
        compute='_compute_gross_amount',
        store=True,
        help='Total gross amount before deductions')
    
    # Payment Information
    part_payment = fields.Float(
        string='Part Payment',
        help='Partial payment amount')

    is_gross_commission_per_head = fields.Boolean(
        string='Gross Commission Per Head',
        default=False,
        help='Whether gross commission is calculated per head')
    
    gross_commission = fields.Float(
        string='Gross Commission',
        compute='_compute_commissions',
        store=True,
        help='Gross commission amount')
    
    commission_rate = fields.Float(
        string='Commission Rate',
        default=2.00,
        digits=(16, 2),
        help='Commission rate percentage')
    
    per_head_commission = fields.Float(
        string='Consignment Fee',
        compute='_compute_commissions',
        store=True,
        help='Commission calculated per head')
    
    per_head_fee = fields.Float(
        string='Per Head Fee',
        default=2.0,
        help='Fee per head')
    
    total_commission = fields.Float(
        string='Total Commission Deducted',
        compute='_compute_commissions',
        store=True,
        help='Total commission amount deducted')
    
    # National Beef Checkoff
    national_beef_check_off_amount = fields.Float(
        string='National Beef Check Off Amount Per Head',
        help='National beef check off amount per head ($1.00 in most states, $0.00 in some)')
    
    national_beef_check_off = fields.Float(
        string='National Beef Check Off',
        compute='_compute_national_beef_check_off',
        store=True,
        help='Total national beef check off amount')
        
    national_beef_check_off_rate_override = fields.Float(
        string='Nat\'l Rate Override',
        digits=(16, 2),
        help='Manually override the national beef check off rate per head. Clears if state changes.')
    
    # State Beef Checkoff
    beef_check_off_state_id = fields.Many2one(
        comodel_name='res.country.state',
        string='Beef Check Off State',
        domain="[('country_id.code', '=', 'US')]",  # Only US states
        help='State for beef check off')
        
    state_beef_check_off_amount = fields.Float(
        string='State Beef Check Off Amount Per Head',
        default=0.0,
        help='State-specific beef check off amount per head (varies by state)')
        
    state_beef_check_off = fields.Float(
        string='State Beef Check Off',
        compute='_compute_state_beef_check_off',
        store=True,
        help='Total state beef check off amount')
        
    state_beef_check_off_rate_override = fields.Float(
        string='State Rate Override',
        digits=(16, 2),
        help='Manually override the state beef check off rate per head. Clears if state changes.')
        
    # Other state fees
    other_state_fees_amount = fields.Float(
        string='Other State Fees Amount Per Head',
        default=0.0,
        help='Other state-specific fees per head (varies by state)')
        
    other_state_fees_total = fields.Float(
        string='Other State Fees Total',
        compute='_compute_other_state_fees',
        store=True,
        help='Total other state fees amount')
        
    state_fee_description = fields.Text(
        string='State Fee Description',
        help='Description of state-specific fees')
        
    # Brand inspector fees
    brand_inspector_national_amount = fields.Float(
        string='Brand Inspector National Amount Per Head',
        default=0.0,
        help='National brand inspector fee per head')
        
    brand_inspector_national_total = fields.Float(
        string='Brand Inspector National Total',
        compute='_compute_brand_inspector_fees',
        store=True,
        help='Total national brand inspector fees')
        
    brand_inspector_state_amount = fields.Float(
        string='Brand Inspector State Amount Per Head',
        default=0.0,
        help='State brand inspector fee per head')
        
    brand_inspector_state_total = fields.Float(
        string='Brand Inspector State Total',
        compute='_compute_brand_inspector_fees',
        store=True,
        help='Total state brand inspector fees')
        
    # For backward compatibility
    beef_check_off_head_count = fields.Integer(
        string='Beef Check Off Head Count',
        compute='_compute_national_beef_check_off_head_count',
        store=True,
        help='Head count used for beef check off calculations')
    
    beef_check_off = fields.Float(
        string='Beef Check Off',
        compute='_compute_beef_check_off',
        store=True,
        help='Total beef check off amount (national + state)')
    
    freight_adjustment = fields.Float(
        string="Freight Adjustment",
        help='Freight adjustment amount')
    
    other_deductions = fields.Float(
        string='Other Deductions',
        help='Any other deductions')
        
    other_deductions_description = fields.Char(
        string='Other Deductions Description',
        help='Description for other deductions (e.g., Freight Adj)')
    
    total_deductions = fields.Float(
        string='Total Deductions',
        compute='_compute_total_deductions',
        store=True,
        help='Sum of all deductions')
    
    net_proceeds = fields.Float(
        string='Net Proceeds',
        compute='_compute_net_proceeds',
        store=True,
        help='Net amount after all deductions')
    
    # Payment Details
    check_ids = fields.One2many(
        comodel_name='consignment.delivery.check',
        inverse_name='delivery_id',
        string='Check Entries',
        help='Individual check entries for this delivery')
    
    check_total = fields.Float(
        string='Check Total',
        compute='_compute_check_total',
        store=True,
        help='Total amount of all checks')
    
    # Keep these fields for backward compatibility
    # check_number = fields.Char(
    #     string='Check #',
    #     help='Check number for payment')
    
    # payable_to = fields.Char(
    #     string='Payable to Whom & Lienholder',
    #     compute='_compute_payable_to',
    #     store=True,
    #     help='Entity to whom payment is made')
    
    # check_amount = fields.Float(
    #     string='Check Amount',
    #     compute='_compute_check_amount',
    #     store=True,
    #     help='Amount of the check')
    
    # Adjustments
    adjustment_ids = fields.One2many(
        comodel_name='consignment.delivery.adjustment',
        inverse_name='delivery_id',
        string='Adjustment Entries',
        help='Individual adjustment entries for this delivery')
    
    adjustments = fields.Float(
        string='Adjustments',
        compute='_compute_adjustments',
        store=True,
        help='Any adjustments to the payment')
    
    adjustments_balance = fields.Float(
        string="Balance",
        compute='_compute_adjustments_balance',
        store=True,
        help='Balance of adjustments'
    )
    
    # Display fields for absolute values (for UI display without negative signs)
    adjustments_display = fields.Float(
        string="Adjustments Display",
        compute='_compute_adjustments_display',
        store=False,
        help='Absolute value of adjustments for display purposes'
    )
    
    adjustments_balance_display = fields.Float(
        string="Balance Display",
        compute='_compute_adjustments_display',
        store=False,
        help='Absolute value of adjustments balance for display purposes'
    )

    @api.depends('adjustments', 'adjustments_balance')
    def _compute_adjustments_display(self):
        """Compute absolute values for display fields"""
        for record in self:
            record.adjustments_display = abs(record.adjustments)
            record.adjustments_balance_display = abs(record.adjustments_balance)
    
    @api.depends('net_proceeds', 'check_total')
    def _compute_adjustments(self):
        """Calculate total adjustments"""
        for record in self:
            # Round to 2 decimal places to avoid floating point precision issues
            adjustment_value = round_half_up(record.net_proceeds - record.check_total, 2)
            # Convert -0.00 to 0.00
            record.adjustments = 0.0 if adjustment_value == -0.0 else adjustment_value

    @api.depends("adjustment_ids", 'adjustment_ids.adjustment_amount', 'adjustments')
    def _compute_adjustments_balance(self):
        for record in self:
            # Get all of the adjustment amounts from the adjustment lines (seller adjustment is positive, company & rep adjustment is negative)
            adjustment_total = 0.0
            for adj in record.adjustment_ids:
                if adj.adjustment_type == 'seller':
                    adjustment_total += adj.adjustment_amount
                else:
                    adjustment_total -= adj.adjustment_amount
            # Calculate balance as adjustments field minus the sum of adjustment lines
            balance_value = round_half_up(record.adjustments - adjustment_total, 2)
            record.adjustments_balance = 0.0 if balance_value == -0.0 else balance_value

    
    # Buyer Payment Information
    gross_amount_due = fields.Float(
        string='Gross Amount Due',
        compute='_compute_gross_amount',
        store=True,
        help='Gross amount due from buyer')
    
    buyer_part_payment = fields.Float(
        string='Part Payment',
        help='Partial payment from buyer')
        
    buyer_adjustment = fields.Float(
        string='Other Adjustments',
        help='Other adjustments to buyer payment')
    
    buyer_adjustments_description = fields.Char(
        string='Other Adjustments Description',
        help='Description for other adjustments (e.g., Seller Discount)')
    
    total_due = fields.Float(
        string='Total Due',
        compute='_compute_total_due',
        store=True,
        help='Total amount due from buyer')
    
    # Computed Methods
    def _compute_gross_amount(self):
        """This method should be implemented in the main model"""
        pass

    @api.depends('check_ids', 'check_ids.check_amount')
    def _compute_check_total(self):
        """Calculate total check amount"""
        for record in self:
            record.check_total = sum(record.check_ids.mapped('check_amount'))

    @api.onchange('check_total', 'net_proceeds')
    def _onchange_check_total(self):
        """Handle changes to check_total and net_proceeds"""
        for record in self:
            record._compute_check_total()

    @api.onchange('contract_id', 'sell_by_head')
    def _onchange_contract_commission_rate(self):
        """Set default commission rate based on contract sell_by_head"""
        for record in self:
            if record.contract_id and record.sell_by_head:
                record.commission_rate = 3.0
            else:
                record.commission_rate = 2.0
    
    @api.depends('gross_amount', 'commission_rate', 'head_count', 'per_head_fee', 'is_gross_commission_per_head')
    def _compute_commissions(self):
        """Calculate commission amounts"""
        for record in self:
            # Calculate gross commission based on percentage
            if record.is_gross_commission_per_head:
                record.gross_commission = round_half_up(record.head_count * record.commission_rate, 2)
            else:
                record.gross_commission = round_half_up(record.gross_amount * (record.commission_rate / 100), 2)

            # Calculate per head commission
            record.per_head_commission = round_half_up(record.head_count * record.per_head_fee, 2)
            
            # Calculate total commission
            record.total_commission = round_half_up((record.gross_commission + record.per_head_commission), 2)

    @api.depends('line_ids', 'line_ids.head_count', 'line_ids.description')
    def _compute_national_beef_check_off_head_count(self):
        """Set beef_check_off_head_count to head_count for backward compatibility"""
        for record in self:
            total_head_count = 0
            for line in record.line_ids:
                if line.description and 'pair' in line.description.lower():
                    total_head_count += line.head_count * 2
                else: 
                    total_head_count += line.head_count
            record.beef_check_off_head_count = total_head_count

    @api.depends('beef_check_off_head_count', 'national_beef_check_off_amount', 'national_beef_check_off_rate_override')
    def _compute_national_beef_check_off(self):
        """Calculate national beef check off amount"""
        for record in self:
            # Use override if provided and > 0, otherwise use the default/state-loaded amount
            rate = record.national_beef_check_off_rate_override \
                if record.national_beef_check_off_rate_override > 0 \
                else record.national_beef_check_off_amount
            checkoff_raw = record.beef_check_off_head_count * rate
            record.national_beef_check_off = round_half_up(checkoff_raw, 2)
    
    @api.depends('beef_check_off_head_count', 'state_beef_check_off_amount', 'state_beef_check_off_rate_override')
    def _compute_state_beef_check_off(self):
        """Calculate state beef check off amount"""
        for record in self:
            # Use override if provided and > 0, otherwise use the default/state-loaded amount
            rate = record.state_beef_check_off_rate_override \
                if record.state_beef_check_off_rate_override > 0 \
                else record.state_beef_check_off_amount
            checkoff_raw = record.beef_check_off_head_count * rate
            record.state_beef_check_off = round_half_up(checkoff_raw, 2)

    @api.depends('national_beef_check_off', 'state_beef_check_off')
    def _compute_beef_check_off(self):
        """Calculate total beef check off amount (national + state)"""
        for record in self:
            checkoff_raw = record.national_beef_check_off + record.state_beef_check_off
            record.beef_check_off = round_half_up(checkoff_raw, 2)
    
    @api.depends('beef_check_off_head_count', 'other_state_fees_amount')
    def _compute_other_state_fees(self):
        """Calculate other state fees"""
        for record in self:
            other_fees_raw = record.beef_check_off_head_count * record.other_state_fees_amount
            record.other_state_fees_total = round_half_up(other_fees_raw, 2)
    
    @api.depends('beef_check_off_head_count', 'brand_inspector_national_amount', 'brand_inspector_state_amount')
    def _compute_brand_inspector_fees(self):
        """Calculate brand inspector fees"""
        for record in self:
            record.brand_inspector_national_total = round_half_up(record.beef_check_off_head_count * record.brand_inspector_national_amount, 2)
            record.brand_inspector_state_total = round_half_up(record.beef_check_off_head_count * record.brand_inspector_state_amount, 2)

    @api.onchange('beef_check_off_state_id')
    def _onchange_beef_check_off_state(self):
        """Auto-fill beef checkoff amounts based on selected state"""
        for record in self:
            # Reset all fields to default values first
            record.national_beef_check_off_rate_override = 0.0
            record.state_beef_check_off_rate_override = 0.0
            record.national_beef_check_off_amount = 0.0
            record.state_beef_check_off_amount = 0.0
            record.other_state_fees_amount = 0.0
            record.state_fee_description = False
            record.brand_inspector_national_amount = 0.0
            record.brand_inspector_state_amount = 0.0
            
            # If no state selected, keep defaults
            if not record.beef_check_off_state_id:
                continue
                
            # Get state code
            state_code = record.beef_check_off_state_id.code
            if not state_code:
                continue
                
            checkoff = self.env['beef.checkoff'].search([('state_code', '=', state_code)], limit=1)
            
            if checkoff:
                # Update all amounts from beef.checkoff model
                record.national_beef_check_off_amount = checkoff.national_beef_checkoff or 0.0
                record.state_beef_check_off_amount = checkoff.state_beef_checkoff or 0.0
                record.other_state_fees_amount = checkoff.other_state_fees or 0.0
                record.state_fee_description = checkoff.description or False
                record.brand_inspector_national_amount = checkoff.brand_inspector_national or 0.0
                record.brand_inspector_state_amount = checkoff.brand_inspector_state or 0.0
    
    @api.depends('total_commission', 'national_beef_check_off', 'state_beef_check_off',
                'other_state_fees_total', 'brand_inspector_national_total',
                'brand_inspector_state_total', 'other_deductions', 'part_payment', 'freight_adjustment')
    def _compute_total_deductions(self):
        """Calculate total deductions"""
        for record in self:
            total_deductions = (record.total_commission +
                                      record.national_beef_check_off +
                                      record.state_beef_check_off +
                                      record.other_state_fees_total +
                                      record.brand_inspector_national_total +
                                      record.brand_inspector_state_total +
                                      record.freight_adjustment +
                                      record.other_deductions +
                                      record.part_payment)
            record.total_deductions = round_half_up(total_deductions, 2)

    @api.depends('gross_amount', 'total_deductions')
    def _compute_net_proceeds(self):
        """Calculate net proceeds after deductions"""
        for record in self:
            net_proceeds = record.gross_amount - record.total_deductions
            record.net_proceeds = round_half_up(net_proceeds, 2)

    def _compute_payable_to(self):
        """This method should be implemented in the main model"""
        pass

    @api.depends('gross_amount_due', 'buyer_part_payment', 'buyer_adjustment', 'freight_adjustment')
    def _compute_total_due(self):
        """Calculate total amount due from buyer"""
        for record in self:
            total_due = record.gross_amount_due - record.buyer_part_payment - record.freight_adjustment + record.buyer_adjustment
            record.total_due = round_half_up(total_due, 2)