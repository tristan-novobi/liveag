# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import datetime
from ..tools import round_half_up

_logger = logging.getLogger(__name__)
READONLY_FIELDS_IN_MERGED_STATE = [
    'seller_id',
    'sell_by_head',
    'buyer_id',
    'lot_number',
    'contract_weight',
    'contract_weight2',
    'base_price',
    'slide_over',
    'slide_under',
]
class Delivery(models.Model):
    _name = 'consignment.delivery'
    # joe: added onchange methods to auto-fill fields from contract
    _inherit = [
        'mail.thread', 
        'mail.activity.mixin',
        'delivery.weight.mixin',
        'delivery.slide.mixin',
        'delivery.financial.mixin',
        'delivery.monetary.mixin',
    ]
    _description = 'Consignment Delivery'
    _order = 'delivery_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Delivery Reference', 
        required=True, 
        copy=False, 
        readonly=True, 
        default=lambda self: _('New'))
    
    to_be_merged = fields.Boolean(string="Merge",default=False)
    
    merged_delivery_id = fields.Many2one('consignment.delivery',
                                         string="Merged Delivery",
                                         help='This record is the result of merge the current delivery and others'
                                         )

    source_delivery_ids = fields.One2many('consignment.delivery',
                                          'merged_delivery_id',
                                          string='Source Deliveries',
                                          help="This is the list of deliveries that got merged to create this record")
    active = fields.Boolean('Active', default=True)
    
    # Contract Information
    contract_id = fields.Many2one(
        comodel_name='consignment.contract',
        string='Contract',
        required=False,
        domain=[('state', 'in', ['sold', 'delivery_ready'])])

    contract_ids = fields.One2many('consignment.contract',
                                   'delivery_id',
                                   string='Contracts',
                                   help='List of contracts handled in this')
    sell_by_head = fields.Boolean(
        string="Sell By Head",
        store=True,
        readonly=False)

    # Constraints
    @api.constrains('contract_id')
    def _check_contract_uniqueness(self):
        """
        Ensure that a contract can only be selected in one active delivery.
        """
        for record in self:
            if record.contract_id and record.state != 'canceled':
                # Search for other active deliveries with the same contract
                other_deliveries = self.search([
                    ('id', '!=', record.id),
                    ('contract_id', '=', record.contract_id.id),
                    ('state', '!=', 'canceled'),
                    ('active', '=', True)
                ])
                
                if other_deliveries:
                    # Use contract ID instead of name to avoid AttributeError
                    raise ValidationError(_(
                        "Contract #%s is already used in another delivery (%s). "
                        "A contract can only be selected in one active delivery."
                    ) % (record.contract_id.id, other_deliveries[0].name))
    
    lot_number = fields.Char(
        string='Lot Number',
        store=True)
    
    # Contract-related fields
    contract_weight = fields.Integer(
        string='Contract Weight',
        store=True,
        readonly=False,
        help='Average weight specified in the contract')
    contract_weight2 = fields.Integer(
        string='Contract Weight 2',
        store=True,
        readonly=False,
        help='Average weight specified in the contract')
    
    base_price = fields.Monetary(
        string='Base Price',
        currency_field='currency_id',
        store=True,
        readonly=False,
        help='Base price per cwt from contract')
    
    slide_type = fields.Many2one(
        comodel_name='slide.type',
        string='Slide Type',
        store=True)
    
    display_slide_over = fields.Boolean(related='slide_type.above', store=False)
    display_slide_under = fields.Boolean(related='slide_type.under', store=False)
    display_slide_both = fields.Boolean(related='slide_type.both', store=False)
    
    slide_type_name = fields.Char(
        related='slide_type.name',
        string='Slide Type Name',
        store=True,
        readonly=True)
    
    slide_over = fields.Integer(
        string='Slide Over',
        store=True,
        readonly=False,
        help='Slide amount for overweight')
    
    slide_under = fields.Integer(
        string='Slide Under',
        store=True,
        readonly=False,
        help='Slide amount for underweight')
    
    slide_both = fields.Integer(
        string='Slide Both',
        store=True,
        readonly=False,
        help='Slide amount for both over and under')
        
    price_back = fields.Integer(
        string='Price Back',
        store=True,
        readonly=False,
        help='Price back amount for second group')
    contract_head1 = fields.Integer(
        string='Contract Head 1',
        store=True,
        readonly=False,
        help='Head count from contract')
    contract_head2 = fields.Integer(
        string='Contract Head 2',
        store=True,
        readonly=False,
        help='Head count from contract')
    
    # Seller Discount
    seller_discount = fields.Float(
        string='Seller Discount (%)',
        store=False,
        readonly=True,
        help='Discount percentage from the seller')
    
    # Seller and Buyer Information
    seller_id = fields.Many2one(
        comodel_name='res.partner',
        string='Seller',
        store=True,
        readonly=True)
    
    buyer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Buyer',
        store=True,
        readonly=True)
    
    buyer_number = fields.Char(
        related='buyer_id.name',
        string='Buyer Number',
        store=True,
        readonly=True)
    
    # Delivery Information
    delivery_date = fields.Date(
        string='Delivery Date',
        required=True,
        default=fields.Date.context_today)
    
    scheduled_delivery_date = fields.Date(
        string='Scheduled Delivery')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('delivered', 'Delivered'),
        ('canceled', 'Canceled'),
        ('merged', 'Merged')
    ], string='Status', default='draft', tracking=True)
    
    # Delivery Line Items
    line_ids = fields.One2many(
        comodel_name='consignment.delivery.line',
        inverse_name='delivery_id',
        string='Delivery Lines',
        help='Individual line items for this delivery')
    
    # Delivery Details - Computed from line items
    head_count = fields.Integer(
        string='Head Count',
        compute='_compute_totals',
        store=True,
        help='Total number of head delivered')
    
    description = fields.Char(
        string='Description',
        help='Brief description of the delivery')
    
    @api.depends('line_ids.head_count', 'line_ids.gross_weight', 'line_ids.net_weight',
                'line_ids.gross_amount')
    def _compute_totals(self):
        """Compute all totals from line items with consistent rounding"""
        for record in self:
            # Filter out gain lines for weight calculations
            non_gain_lines = record.line_ids.filtered(lambda l: not l.is_gain_line)
            
            record.head_count = sum(non_gain_lines.mapped('head_count')) or 0
            
            # Calculate actual net weight from delivery lines
            record.net_weight = round_half_up(sum(non_gain_lines.mapped('net_weight'))) if non_gain_lines else 0.0
            
            # Calculate capped net weight - same as net weight unless it exceeds the cap
            actual_net_weight = record.net_weight
            if hasattr(record, 'weight_cap') and record.weight_cap and actual_net_weight > record.weight_cap:
                record.capped_net_weight = round_half_up(record.weight_cap)
            else:
                record.capped_net_weight = actual_net_weight
            
            # Recalculate average weight if there are line items
            if record.head_count:
                record.average_weight = round_half_up(record.net_weight / record.head_count)
            
            # Calculate gross weight from non-gain lines only
            record.gross_weight = round_half_up(sum(non_gain_lines.mapped('gross_weight'))) if non_gain_lines else 0.0

    # Buyer Information
    buyer_called = fields.Char(
        string='Buyer Called',
        help='Person who was called regarding the delivery')
    
    destination = fields.Char(
        string='Destination',
        help='Delivery destination')
    
    paid_at_delivery = fields.Boolean(
        string='Paid @ Delivery',
        help='Whether payment was made at delivery')
    
    funds_sent_via = fields.Char(
        string='Funds Sent via',
        help='Method by which funds were sent')
    
    # Rep Information
    rep_id = fields.Many2one(
        comodel_name='res.partner',
        string='Rep',
        store=True,
        readonly=True)
    
    rep_ids = fields.One2many(
        'res.rep',
        'delivery_id',
        string='Reps',
        help='Representatives associated with this delivery through the contract')
    
    # Additional Information
    comments = fields.Text(
        string='Comments',
        help='Additional comments about the delivery')
    
    buyer_comments = fields.Text(
        string='Buyer Comments',
        help='Additional comments from the buyer')
    
    taken_by = fields.Char(
        string='Taken by',
        help='Person who took the delivery')
    
    taken_date = fields.Date(
        string='Date',
        help='Date when delivery was taken')
    
    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company)
    
    # Override the currency_id field from the mixin
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        store=True)
    
    # Override mixin methods
    @api.depends('contract_id', 'contract_id.weight_stop', 'contract_id.slide_type')
    def _compute_weight_stop(self):
        """Get weight stop value from contract"""
        for record in self:
            if record.contract_id and record.contract_id.weight_stop:
                try:
                    _logger.info(f"================ Weight stop: {record.contract_id.weight_stop.name}")
                    record.weight_stop_id = record.contract_id.weight_stop.id
                    record.slide_type = record.contract_id.slide_type
                except (ValueError, AttributeError):
                    # Find and set the "None" weight stop
                    none_weight_stop = self.env['weight.stop'].search([('name', '=', 'None')], limit=1)
                    record.weight_stop_id = none_weight_stop.id if none_weight_stop else None
            else:
                # Find and set the "None" weight stop when no weight stop from contract
                none_weight_stop = self.env['weight.stop'].search([('name', '=', 'None')], limit=1)
                record.weight_stop_id = none_weight_stop.id if none_weight_stop else None
    
    @api.depends('average_weight', 'contract_weight')
    def _compute_weight_difference(self):
        """Calculate weight difference and determine if over/underweight"""
        for record in self:
            record.weight_difference = record.average_weight - float(record.contract_weight or 0)
            record.is_overweight = record.weight_difference > 0
            record.is_underweight = record.weight_difference < 0
    
    @api.depends('slide_type_name')
    def _compute_is_gain_slide(self):
        """Determine if this is a gain slide"""
        for record in self:
            record.is_gain_slide = record.slide_type_name == 'Gain Slide'
            
    @api.depends('is_gain_slide', 'head_count', 'contract_weight', 'base_price', 
                 'net_weight', 'gain_price_monetary')
    def _compute_gain_slide_payments(self):
        """Calculate payments for gain slide"""
        for record in self:
            if not record.is_gain_slide or not record.head_count or not record.contract_weight:
                record.base_weight_payment = 0.0
                record.weight_gain = 0.0
                record.weight_gain_payment = 0.0
                continue
                
            # Calculate base weight total
            base_weight_total = record.head_count * float(record.contract_weight)
            
            # Calculate payment for base weight
            record.base_weight_payment = base_weight_total * record.base_price / 100
            
            # Calculate weight gain (ensure non-negative)
            record.weight_gain = max(0, record.net_weight - base_weight_total)
            
            # Calculate payment for weight gain
            record.weight_gain_payment = record.weight_gain * record.gain_price_monetary
    
    # @api.depends('adjusted_weight_difference', 'slide_over', 'slide_under', 'slide_both', 
    #              'slide_type_name', 'is_overweight', 'is_underweight')
    # def _compute_price_adjustment(self):
    #     """Calculate price adjustment based on slide type and weight difference"""
    #     for record in self:
    #         record.price_adjustment = self._calculate_price_adjustment(
    #             record.slide_type_name, 
    #             record.slide_over, 
    #             record.slide_under, 
    #             record.slide_both, 
    #             record.adjusted_weight_difference, 
    #             record.is_overweight, 
    #             record.is_underweight
    #         )

    @api.depends('base_price', 'price_adjustment', 'is_overweight')
    def _compute_adjusted_price(self):
        """Calculate adjusted price after slide adjustment"""
        for record in self:
            adjustment_factor = -1 if record.is_overweight else 1
            record.adjusted_price = record.base_price + (adjustment_factor * record.price_adjustment)
    
    @api.depends('line_ids.gross_amount')
    def _compute_gross_amount(self):
        """Calculate gross amount from delivery lines"""
        for record in self:
            record.gross_amount = round_half_up(sum(record.line_ids.mapped('gross_amount')), 2)
            record.gross_amount_due = record.gross_amount
    

    # CRUD Methods
    @api.model
    def create(self, vals_list):
        """Create a new delivery record with a unique sequence and ensure primary check entry.
        Supports both single dict (legacy) and list of dicts (batch create).
        """
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('consignment.delivery') or _('New')

            # Copy values from Float fields to Monetary fields
            if 'gain_price' in vals:
                vals['gain_price_monetary'] = vals['gain_price']
            if 'part_payment' in vals:
                vals['part_payment_monetary'] = vals['part_payment']
            if 'other_deductions' in vals:
                vals['other_deductions_monetary'] = vals['other_deductions']
            if 'adjustments' in vals:
                vals['adjustments_monetary'] = vals['adjustments']
            if 'buyer_part_payment' in vals:
                vals['buyer_part_payment_monetary'] = vals['buyer_part_payment']
            if 'buyer_adjustment' in vals:
                vals['buyer_adjustment_monetary'] = vals['buyer_adjustment']

        result = super(Delivery, self).create(vals_list)
        return result
    
    def check_fields(self,vals):
        "Remove fields that cannot be edited in merged state"

        vals = {k: v for k, v in vals.items() if k not in READONLY_FIELDS_IN_MERGED_STATE}

        return vals

    def write(self, vals):
        """Update record and sync Float and Monetary fields"""
        # Sync values between Float fields and Monetary fields
        for delivery in self:
            if delivery.state == 'merged':
                vals = delivery.check_fields(vals)
                
        if 'gain_price' in vals:
            vals['gain_price_monetary'] = vals['gain_price']
        elif 'gain_price_monetary' in vals:
            vals['gain_price'] = vals['gain_price_monetary']

        if 'part_payment' in vals:
            vals['part_payment_monetary'] = str(vals['part_payment'])
        elif 'part_payment_monetary' in vals:
            vals['part_payment'] = vals['part_payment_monetary']

        if 'other_deductions' in vals:
            vals['other_deductions_monetary'] = vals['other_deductions']
        elif 'other_deductions_monetary' in vals:
            vals['other_deductions'] = vals['other_deductions_monetary']

        if 'adjustments' in vals:
            vals['adjustments_monetary'] = vals['adjustments']
        elif 'adjustments_monetary' in vals:
            vals['adjustments'] = vals['adjustments_monetary']

        if 'buyer_part_payment' in vals:
            vals['buyer_part_payment_monetary'] = vals['buyer_part_payment']
        elif 'buyer_part_payment_monetary' in vals:
            vals['buyer_part_payment'] = vals['buyer_part_payment_monetary']

        if 'buyer_adjustment' in vals:
            vals['buyer_adjustment_monetary'] = vals['buyer_adjustment']
        elif 'buyer_adjustment_monetary' in vals:
            vals['buyer_adjustment'] = vals['buyer_adjustment_monetary']
            
        result = super(Delivery, self).write(vals)
        
        # Trigger gain line management if relevant fields changed
        delivery_triggering_fields = ['weight_stop_id', 'is_gain_slide', 'contract_weight', 'contract_weight2']
        if any(field in vals for field in delivery_triggering_fields):
            for record in self:
                # Manage gain lines for all lines in this delivery
                for line in record.line_ids.filtered(lambda l: not l.is_gain_line):
                    line._manage_gain_lines()
        
        return result
    
    # Domain methods (not working in Odoo 17)
    # @api.model
    # def _get_used_contract_ids(self):
    #     """
    #     Get IDs of contracts that are already used in active deliveries.
    #     """
    #     used_contracts = self.search([
    #         ('state', '!=', 'canceled'),
    #         ('active', '=', True)
    #     ]).mapped('contract_id').ids
    #     return used_contracts or [0]  # Return [0] if no contracts to avoid empty domain
    
    # @api.model
    # def get_contract_domain(self):
    #     """
    #     Get domain for contract_id field to exclude already used contracts.
    #     """
    #     used_contract_ids = self._get_used_contract_ids()
    #     return [
    #         ('state', 'in', ['sold', 'delivery_ready']),
    #         ('id', 'not in', used_contract_ids)
    #     ]
    
    # Constraints
    @api.constrains('contract_id')
    def _check_contract_uniqueness(self):
        """
        Ensure that a contract can only be selected in one active delivery.
        """
        for record in self:
            if record.contract_id and record.state != 'canceled':
                # Search for other active deliveries with the same contract
                other_deliveries = self.search([
                    ('id', '!=', record.id),
                    ('contract_id', '=', record.contract_id.id),
                    ('state', '!=', 'canceled'),
                    ('active', '=', True)
                ])
                
                if other_deliveries:
                    # Use contract ID instead of name to avoid AttributeError
                    raise ValidationError(_(
                        "Contract #%s is already used in another delivery (%s). "
                        "A contract can only be selected in one active delivery."
                    ) % (record.contract_id.id, other_deliveries[0].name))
    def merge(self,base_delivery_id=None):
        # Merging logic to combine deliveries into base_delivery_id
        # This is a placeholder for the actual merging logic
        
        vals = {
                'seller_id': base_delivery_id.seller_id.id,
                'sell_by_head': base_delivery_id.sell_by_head,
                'buyer_id': base_delivery_id.buyer_id.id,
                'lot_number': str(self.mapped('lot_number')),
                'contract_weight': sum(self.mapped('contract_weight')),
                'contract_weight2': sum(self.mapped('contract_weight2')),
                'base_price': base_delivery_id.base_price,
                'slide_over': base_delivery_id.slide_over,
                'slide_under': base_delivery_id.slide_under,
                'slide_both': base_delivery_id.slide_both,
                'price_back': base_delivery_id.price_back,
                'contract_head1': sum(self.mapped('contract_head1')),
                'contract_head2': sum(self.mapped('contract_head2')),
                'seller_discount': base_delivery_id.seller_id.discount,
                # 'rep_id': base_delivery_id.primary_rep.id,
            }
        delivery = self.env['consignment.delivery'].create(vals)
        self.write({'merged_delivery_id': delivery.id,
                    'state':'merged'})
        delivery.message_post(body=_("Deliveries merged: %s") % (self.mapped('lot_number'),))
        self.mapped('contract_ids').write({'delivery_id':delivery.id})

        
    def validate_merged_deliveries(self):
        merged_deliveries = (self).filtered(lambda c : c.merged_delivery_id )
        if merged_deliveries:
            error = f"Deliveries :{merged_deliveries.mapped('lot_number')} \n where already merged"
            return error
        
        return '' 
        
    def validate_status(self):
        cancel_delivered_records = self.filtered(lambda d: d.state in ['canceled','delivered'])
        error = ''
        if cancel_delivered_records:
            error += f'''Delivered/Canceled Deliveries can not be Merge, please remove this records 
                        Deliveries: {cancel_delivered_records.mapped('lot_number')}
                        from the selected itmes'''
            error += '\n'

        return error
    
    def create_error_list(self,errors):
        # Start the unordered list
        msg = ""
        # Loop through each error and add it as a list item
        for error in errors:
            if error:
                msg += f"- {error}\n"
                msg += "---------------------------------------- \n"
        
        return msg


    def merge_deliveries(self,base_delivery_id=None):
        # Collect errors from various validation functions
        errors_to_fix = [
            self.validate_merged_deliveries(),
            self.validate_status(),
            self.mapped('contract_ids').validate_header_info(),
        ]
        # Filter out any empty (falsy) errors
        errors_to_fix = [error for error in errors_to_fix if error]

        # Raise an error if there are any issues to fix
        if errors_to_fix:
            error_message = self.create_error_list(errors_to_fix)
            raise ValidationError(error_message)

        # Proceed to create the new contract if no errors
        self.merge(base_delivery_id=base_delivery_id)
            
    

    # Action Methods

    def action_merge(self):
        deliveries = self.env['consignment.delivery'].search([('seller_id','=',self.seller_id.id),('id','!=',self.id)])
        return {
            'name': _('Merge option Deliveries'),
            'res_model': 'merge.deliveries.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {
                'default_base_delivery_id': self.id,
                'default_option_delivery_ids': deliveries.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def action_confirm(self):
        """Confirm the delivery"""
        self.write({'state': 'confirmed'})
    
    def action_deliver(self):
        """Mark the delivery as delivered and update contract state"""
        for record in self:
            record.state = 'delivered'
            # Update the related contract state
            record.contract_ids.write({'state':'delivered'})
    
    def action_cancel(self):
        """Cancel the delivery"""
        self.write({'state': 'canceled'})
    
    def action_draft(self):
        """Reset the delivery to draft state"""
        self.write({'state': 'draft'})

    def get_default_shrink(self):
        """Auto-fill shrink_percentage from contract or seller's discount but keep it editable"""
        for record in self:
            if record.contract_id and record.contract_id.shrink_percentage:
                record.shrink_percentage = record.contract_id.shrink_percentage
            elif record.contract_id and record.contract_id.seller_id and record.contract_id.seller_id.discount:
                record.shrink_percentage = record.contract_id.seller_id.discount
                
    def get_default_head_count(self):
        """Auto-fill head count from contract"""
        for record in self:
            if record.contract_id and record.contract_id.head1:
                record.contract_head1 = record.contract_id.head1
            if record.contract_id and record.contract_id.head2:
                record.contract_head2 = record.contract_id.head2
        
    def get_default_part_payment(self):
        """Auto-fill part_payment from contract's seller_part_payment and buyer_part_payment if available"""
        for record in self:
            if not record.contract_id:
                continue
                
            # Try to get seller_part_payment from contract
            if hasattr(record.contract_id, 'seller_part_payment') and record.contract_id.seller_part_payment:
                record.part_payment = record.contract_id.seller_part_payment
                
            # Try to get buyer_part_payment from contract
            if hasattr(record.contract_id, 'buyer_part_payment') and record.contract_id.buyer_part_payment:
                record.buyer_part_payment = record.contract_id.buyer_part_payment
                
    def get_default_lines(self):
        """Auto-create line items for Head 1 and Head 2 when contract is selected"""
        for record in self:
            if record.contract_id and not record.line_ids:
                lines_to_create = []
                contract = record.contract_id
                
                # Ensure adjusted_price is computed before using it
                record._compute_price_adjustment()
                record._compute_adjusted_price()
                
                # Use adjusted_price instead of base_price to account for slide adjustments
                if contract.shrink_percentage:
                    shrink = contract.shrink_percentage
                else:
                    shrink = 0.0
                
                # Create line for Head 1 if head1 > 0
                if contract.head1 and contract.head1 > 0:
                    # Estimate gross weight based on weight1 and head1
                    gross_weight_1 = contract.weight1 * contract.head1
                    
                    # Create a command to add a line for Head 1
                    lines_to_create.append((0, 0, {
                        'head_group': '1',  # Mark as Head 1
                        'head_count': 0,
                        'description': contract.kind1.name if contract.kind1 else '',
                        'gross_weight': 0,
                        'shrink_percentage': shrink,
                        'is_price_back': False,
                        'price': contract.sold_price,
                        'sequence': 10,  # Explicit sequence for Head 1
                    }))
                
                # Create line for Head 2 if head2 > 0
                if contract.head2 and contract.head2 > 0:
                    # Create a command to add a line for Head 2
                    lines_to_create.append((0, 0, {
                        'head_group': '2',  # Mark as Head 2
                        'head_count': 0,
                        'description': contract.kind2.name if contract.kind2 else '',
                        'gross_weight': 0,
                        'shrink_percentage': shrink,
                        'is_price_back': True,
                        'price': contract.sold_price,
                        'sequence': 20,  # Explicit sequence for Head 2
                    }))
                
                # Apply the created lines
                if lines_to_create:
                    record.line_ids = lines_to_create
                    
    def get_default_slide_type(self):
        """Set slide_type and weight_stop_id based on contract"""
        for record in self:
            if record.contract_id:
                # Set slide type
                if record.contract_id.slide_type:
                    record.slide_type = record.contract_id.slide_type.id
                # Set weight stop
                if record.contract_id.weight_stop:
                    record.weight_stop_id = record.contract_id.weight_stop.id
                else:
                    # Find and set the "None" weight stop
                    none_weight_stop = self.env['weight.stop'].search([('name', '=', 'None')], limit=1)
                    if none_weight_stop:
                        record.weight_stop_id = none_weight_stop.id
                    else:
                        record.weight_stop_id = None
                # Set contract weight
                if record.contract_id.weight1:
                    record.contract_weight = record.contract_id.weight1
                if record.contract_id.weight2:
                    record.contract_weight2 = record.contract_id.weight2
                # Set base price
                if record.contract_id.sold_price:
                    record.base_price = record.contract_id.sold_price
                # Set slide values
                if record.contract_id.slide_over:
                    record.slide_over = record.contract_id.slide_over
                if record.contract_id.slide_under:
                    record.slide_under = record.contract_id.slide_under
                if record.contract_id.slide_both:
                    record.slide_both = record.contract_id.slide_both
                # Set price back
                if record.contract_id.price_back:
                    record.price_back = record.contract_id.price_back
                # Set beef checkoff state
                if record.contract_id.state_of_nearest_town:
                    record.beef_check_off_state_id = record.contract_id.state_of_nearest_town.id
                    # Trigger the financial mixin's onchange to load the rates
                    record._onchange_beef_check_off_state()
    
    def get_default_check_entry(self):
        """Create default check entries from contract addendums if none exist"""
        for record in self:
            if not record.contract_id:
                continue
            if not record.check_ids:
                check_lines = []
                for addendum in record.contract_id.addendum_ids:
                    payable = f"{addendum.seller_id.name}{f' & {addendum.lien_holder_id.name}' if addendum.lien_holder_id else ''}"
                    check_lines.append((0, 0, {
                        'payable_to': payable,
                        'check_amount': 0,
                        'is_primary': bool(addendum.id == record.contract_id.addendum_ids[0].id)
                    }))
                if check_lines:
                    record.check_ids = check_lines
                    
    def get_default_freight_adjustment(self):
        """Auto-fill freight adjustment from contract"""
        for record in self:
            if record.contract_id and record.contract_id.freight_adjustment_amount and record.contract_id.freight_adjustment_amount > 0:
                record.freight_adjustment = record.contract_id.freight_adjustment_amount
                
    def get_default_sell_by_head(self):
        """Auto-fill sell_by_head from contract"""
        for record in self:
            if record.contract_id and record.contract_id.sell_by_head:
                record.sell_by_head = record.contract_id.sell_by_head
    
    def get_default_rep_ids(self):
        """Auto-fill rep_ids from contract's reps - works via contract.delivery_id relationship"""
        for record in self:
            if record.contract_id and record.contract_id.rep_ids:
                rep_commands = [(4, rep.id) for rep in record.contract_id.rep_ids]
                record.rep_ids = rep_commands

    def get_default_values(self):
        for record in self:
            if not record.contract_id:
                continue
            
            record.seller_id = record.contract_id.seller_id.id
            record.buyer_id = record.contract_id.buyer_id.id
            record.lot_number = record.contract_id.lot_number
            record.contract_weight = record.contract_id.weight1
            record.contract_weight2 = record.contract_id.weight2
            record.base_price = record.contract_id.sold_price
            # record.shrink_percentage = record.contract_id.shrink_percentage or 0.0
            record.sell_by_head = record.contract_id.sell_by_head
            record.slide_type = record.contract_id.slide_type.id if record.contract_id.slide_type else None
            record.slide_over = record.contract_id.slide_over
            record.slide_under = record.contract_id.slide_under
            record.slide_both = record.contract_id.slide_both
            record.price_back = record.contract_id.price_back
            record.contract_head1 = record.contract_id.head1
            record.contract_head2 = record.contract_id.head2
            record.seller_discount = record.contract_id.seller_id.discount
            record.buyer_number = record.contract_id.buyer_id.name if record.contract_id.buyer_id else ''
            record.rep_id = record.contract_id.primary_rep.id if record.contract_id.primary_rep else None
            record.rep_ids = [(4, rep.id) for rep in record.contract_id.rep_ids]

    def get_default_flow(self):
        """Auto-fill all default values from contract"""
        for record in self:
            try:
                # When contract_id is set or changed, sync contract_ids to only that contract (replace any others)
                if record.contract_id:
                    record.contract_ids = [(6, 0, [record.contract_id.id])]
                record.get_default_values()
                record.get_default_shrink()
                record.get_default_head_count()
                record.get_default_part_payment()
                record.get_default_lines()
                record.get_default_slide_type()
                record.get_default_check_entry()
                record.get_default_freight_adjustment()
                record.get_default_sell_by_head()
                record.get_default_rep_ids()
            except Exception as e:
                _logger.error(f"Error getting default values: {e}")

    @api.onchange('contract_id')
    def _onchange_contract_id_flow(self):
        """Onchange flow to auto-fill default values when contract is selected"""
        # Clear existing check entries so defaults are regenerated for the new contract
        if self.check_ids:
            self.check_ids = [(5, 0, 0)]
        self.get_default_flow()