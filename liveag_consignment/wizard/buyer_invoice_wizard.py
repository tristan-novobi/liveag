# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class BuyerInvoiceWizardContractLine(models.TransientModel):
    _name = 'buyer.invoice.wizard.contract.line'
    _description = 'Contract Line for Buyer Invoice Wizard'
    
    wizard_id = fields.Many2one('buyer.invoice.wizard', string='Wizard')
    head_group = fields.Char(string='Group')
    head_count = fields.Integer(string='Head')
    kind = fields.Char(string='Kind')
    gross_weight = fields.Float(string='Gross Weight')
    shrink = fields.Integer(string='Shrink %')
    net_weight = fields.Float(string='Net Weight')
    avg_weight = fields.Float(string='Avg Weight')
    price = fields.Monetary(string='Price', currency_field='currency_id')
    gross_amount = fields.Monetary(string='Gross Amount', currency_field='currency_id')
    currency_id = fields.Many2one(related='wizard_id.currency_id', store=True)


class BuyerInvoiceWizard(models.TransientModel):
    _name = 'buyer.invoice.wizard'
    _description = 'Buyer Invoice PDF Generator'

    delivery_id = fields.Many2one(
        comodel_name='consignment.delivery',
        string='Delivery',
        required=True,
        readonly=True,
        help='Delivery record to generate buyer invoice for')

    # Company Information (Static)
    company_name = fields.Char(string='Company Name', default='LiveAg, LLC')
    company_address_line1 = fields.Char(string='Address Line 1', default='108 W Angeline St')
    company_address_line2 = fields.Char(string='Address Line 2', default='Groesbeck, TX 76642')
    company_phone = fields.Char(string='Phone', default='817-533-6699')

    # Header Information
    buyer_id = fields.Many2one(
        related='delivery_id.buyer_id',
        string='Buyer',
        store=True,
        readonly=True)
    buyer_number = fields.Char(string='Buyer #', compute='_compute_header_info', store=True)
    lot_number = fields.Char(string='Lot #', compute='_compute_header_info', store=True)
    seller_name = fields.Char(string='Seller', compute='_compute_header_info', store=True)
    seller_location = fields.Char(string='Location', compute='_compute_header_info', store=True)
    rep_ids = fields.One2many(
        comodel_name='res.rep',
        related='delivery_id.rep_ids',
        string='Reps',
        readonly=True,
        help='Representatives associated with this delivery through the contract')
    rep_names_list = fields.Many2many(
        comodel_name='res.partner',
        compute='_compute_rep_names_list',
        store=True,
        string='Rep(s)',
        help='Representative names for display')
    rep_name = fields.Char(string='Rep(s)', compute='_compute_header_info', store=True)
    seller_phone = fields.Char(string='Cell', compute='_compute_header_info', store=True)
    seller_email = fields.Char(string='Email', compute='_compute_header_info', store=True)
    buyer_phone = fields.Char(string='Buyer Phone', compute='_compute_header_info', store=True)
    buyer_email = fields.Char(string='Buyer Email', compute='_compute_header_info', store=True)
    delivery_date = fields.Date(string='Delivery Date', compute='_compute_header_info', store=True)
    auction_date = fields.Date(string='Auction Date', compute='_compute_header_info', store=True)

    # Contract Section
    contract_head1 = fields.Integer(string='Contract Head 1', compute='_compute_contract_info', store=True)
    contract_head2 = fields.Integer(string='Contract Head 2', compute='_compute_contract_info', store=True)
    contract_head_count = fields.Integer(string='Contract Head', compute='_compute_contract_info', store=True)
    contract_kind1 = fields.Char(string='Contract Kind 1', compute='_compute_contract_info', store=True)
    contract_kind2 = fields.Char(string='Contract Kind 2', compute='_compute_contract_info', store=True)
    contract_weight1 = fields.Float(string='Contract Weight 1', compute='_compute_contract_info', store=True)
    contract_weight2 = fields.Float(string='Contract Weight 2', compute='_compute_contract_info', store=True)
    contract_gross_weight = fields.Float(string='Contract Gross Weight', compute='_compute_contract_info', store=True)
    contract_shrink = fields.Float(string='Contract Shrink %', compute='_compute_contract_info', store=True)
    contract_slide_description = fields.Char(string='Contract Slide Type', compute='_compute_contract_info', store=True)
    contract_slide = fields.Float(string='Contract Slide', compute='_compute_contract_info', store=True)
    contract_net_weight = fields.Float(string='Contract Net Weight', compute='_compute_contract_info', store=True)
    contract_avg_weight_stop = fields.Char(string='Contract Weight Stop', compute='_compute_contract_info', store=True)
    contract_price = fields.Monetary(string='Contract Price', currency_field='currency_id', compute='_compute_contract_info', store=True)
    contract_price2 = fields.Monetary(string='Contract Price 2', currency_field='currency_id', compute='_compute_contract_info', store=True)
    contract_gross_amount = fields.Monetary(string='Contract Gross Amount', currency_field='currency_id', compute='_compute_contract_info', store=True)

    # Delivery Section
    delivery_lines = fields.One2many(
        comodel_name='consignment.delivery.line',
        related='delivery_id.line_ids',
        string='Delivery Lines',
        readonly=True)
    
    contract_lines = fields.One2many(
        comodel_name='buyer.invoice.wizard.contract.line',
        inverse_name='wizard_id',
        string='Contract Lines',
        compute='_compute_contract_lines',
        store=True)
    delivery_head_count = fields.Integer(string='Delivery Head', compute='_compute_delivery_info', store=True)
    delivery_kind = fields.Char(string='Delivery Kind', compute='_compute_delivery_info', store=True)
    delivery_gross_weight = fields.Float(string='Delivery Gross Weight', compute='_compute_delivery_info', store=True)
    delivery_shrink = fields.Float(string='Delivery Shrink %', compute='_compute_delivery_info', store=True)
    delivery_net_weight = fields.Float(string='Delivery Net Weight', compute='_compute_delivery_info', store=True)
    delivery_capped_net_weight = fields.Float(string='Delivery Capped Net Weight', compute='_compute_delivery_info', store=True)
    delivery_avg_weight = fields.Float(string='Delivery Avg Weight', compute='_compute_delivery_info', store=True)
    delivery_capped_avg_weight = fields.Float(string='Delivery Capped Avg Weight', compute='_compute_delivery_info', store=True)
    delivery_price = fields.Monetary(string='Delivery Price', currency_field='currency_id', compute='_compute_delivery_info', store=True)
    delivery_gross_amount = fields.Monetary(string='Delivery Gross Amount', currency_field='currency_id', compute='_compute_delivery_info', store=True)

    # Financial Information
    buyer_comments = fields.Text(string='Buyer Comments', related='delivery_id.buyer_comments', store=True) 
    total_gross_amount = fields.Monetary(string='Total Gross Amount', currency_field='currency_id', compute='_compute_financial_info', store=True)
    buyer_part_payment = fields.Monetary(string='Buyer Part Payment', currency_field='currency_id', compute='_compute_financial_info', store=True)
    freight_adjustment = fields.Monetary(string='Freight Adjustment', currency_field='currency_id', compute='_compute_financial_info', store=True)
    buyer_adjustment = fields.Monetary(string='Adjustment', currency_field='currency_id', compute='_compute_financial_info', store=True)
    buyer_adjustment_description = fields.Char(string='Adjustment Description', compute='_compute_financial_info', store=True)
    net_due = fields.Monetary(string='Net Due', currency_field='currency_id', compute='_compute_financial_info', store=True)

    # Display fields for weight capping notation
    delivery_net_weight_display = fields.Char(string='Net Weight Display', compute='_compute_weight_displays', store=True)
    delivery_avg_weight_display = fields.Char(string='Avg Weight Display', compute='_compute_weight_displays', store=True)

    currency_id = fields.Many2one(
        related='delivery_id.currency_id',
        store=True)

    @api.model
    def default_get(self, fields_list):
        """Set default delivery_id from context"""
        res = super().default_get(fields_list)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'consignment.delivery':
            res['delivery_id'] = self.env.context.get('active_id')
        return res

    @api.depends('delivery_id')
    def _compute_header_info(self):
        """Compute header information from delivery and related records"""
        for wizard in self:
            if not wizard.delivery_id:
                continue

            delivery = wizard.delivery_id
            contract = delivery.contract_id
            buyer = delivery.buyer_id
            seller = delivery.seller_id
            rep = delivery.rep_id

            # Buyer information
            wizard.buyer_number = (buyer.ref or buyer.name) if buyer else ''
            wizard.lot_number = getattr(delivery, 'lot_number', '') or ''
            wizard.buyer_phone = buyer.phone if buyer else ''
            wizard.buyer_email = buyer.email if buyer else ''

            # Seller information
            wizard.seller_name = seller.name if seller else ''
            
            # Seller location (city, state)
            location_parts = []
            if seller:
                if getattr(seller, 'city', None):
                    location_parts.append(seller.city)
                if getattr(seller, 'state_id', None):
                    state_code = getattr(seller.state_id, 'code', None)
                    if state_code:
                        location_parts.append(state_code)
            wizard.seller_location = ', '.join(location_parts)

            # Rep information
            wizard.rep_name = rep.name if rep else ''

            # Contact information
            seller_phone = ''
            if seller:
                seller_phone = getattr(seller, 'phone', '') or getattr(seller, 'mobile', '') or ''
            wizard.seller_phone = seller_phone
            
            wizard.seller_email = getattr(seller, 'email', '') if seller else ''

            # Dates
            wizard.delivery_date = delivery.delivery_date
            
            # Auction date from contract's auction
            if contract and contract.auction_id:
                # Convert datetime to date if needed
                if contract.auction_id.sale_date_begin:
                    wizard.auction_date = contract.auction_id.sale_date_begin.date()
                else:
                    wizard.auction_date = False
            else:
                wizard.auction_date = False

    @api.depends('delivery_id')
    def _compute_contract_info(self):
        """Compute contract section information"""
        for wizard in self:
            if not wizard.delivery_id or not wizard.delivery_id.contract_id:
                continue

            delivery = wizard.delivery_id
            contract = delivery.contract_id

            # Contract head count (combine head1 and head2)
            head1 = getattr(contract, 'head1', 0) or 0
            head2 = getattr(contract, 'head2', 0) or 0
            wizard.contract_head_count = head1 + head2
            wizard.contract_head1 = head1
            wizard.contract_head2 = head2

            # Contract kind (combine kind1 and kind2)
            kind1 = getattr(contract.kind1, 'name', '') or ''
            kind2 = getattr(contract.kind2, 'name', '') or ''
            wizard.contract_kind1 = kind1
            wizard.contract_kind2 = kind2

            # Contract weights and calculations
            contract_weight1 = getattr(contract, 'weight1', 0) or 0
            contract_weight2 = getattr(contract, 'weight2', 0) or 0
            wizard.contract_weight1 = contract_weight1
            wizard.contract_weight2 = contract_weight2
            wizard.contract_shrink = getattr(contract, 'shrink_percentage', 0) or 0
            
            # Calculate contract net weight with shrink
            wizard.contract_net_weight = wizard.contract_gross_weight * (1 - wizard.contract_shrink / 100)

            # Slide information
            slide_description = getattr(contract, 'short_slide_description', '') or ''
            slide_over = getattr(contract, 'slide_over', 0) or 0
            slide_under = getattr(contract, 'slide_under', 0) or 0
            slide_both = getattr(contract, 'slide_both', 0) or 0
            wizard.contract_slide = slide_over or slide_under or slide_both
            wizard.contract_slide_description = slide_description

            # Weight stop
            if hasattr(contract, 'weight_stop') and contract.weight_stop:
                wizard.contract_avg_weight_stop = getattr(contract.weight_stop, 'name', '') or ''
            else:
                wizard.contract_avg_weight_stop = 'None'

            # Price and gross amount
            wizard.contract_price = getattr(contract, 'sold_price', 0) or 0
            price_back = getattr(contract, 'price_back', 0) or 0
            wizard.contract_price2 = wizard.contract_price - price_back
            wizard.contract_gross_amount = wizard.contract_net_weight * wizard.contract_price / 100

    @api.depends('delivery_id')
    def _compute_delivery_info(self):
        """Compute delivery section information"""
        for wizard in self:
            if not wizard.delivery_id:
                continue

            delivery = wizard.delivery_id

            # Delivery totals from line items
            wizard.delivery_head_count = delivery.head_count
            wizard.delivery_gross_weight = delivery.gross_weight
            wizard.delivery_shrink = delivery.shrink_percentage or 0
            wizard.delivery_net_weight = delivery.net_weight

            # Get capped weights from line items
            capped_net_total = 0
            capped_avg_total = 0
            line_count = 0

            for line in delivery.line_ids.filtered(lambda l: not l.is_gain_line):
                if line.capped_net_weight > 0:
                    capped_net_total += line.capped_net_weight
                else:
                    capped_net_total += line.net_weight
                    
                if line.capped_average_weight > 0:
                    capped_avg_total += line.capped_average_weight * line.head_count
                    line_count += line.head_count

            wizard.delivery_capped_net_weight = capped_net_total
            
            # Calculate capped average weight
            if line_count > 0:
                wizard.delivery_capped_avg_weight = capped_avg_total / line_count
            else:
                wizard.delivery_capped_avg_weight = 0

            # Regular average weight
            if wizard.delivery_head_count > 0:
                wizard.delivery_avg_weight = wizard.delivery_net_weight / wizard.delivery_head_count
            else:
                wizard.delivery_avg_weight = 0

            # Kind information from line items
            kinds = delivery.line_ids.filtered(lambda l: not l.is_gain_line).mapped('description')
            wizard.delivery_kind = ', '.join(set(kinds)) if kinds else ''

            # Price and gross amount
            wizard.delivery_price = delivery.base_price or 0
            wizard.delivery_gross_amount = delivery.gross_amount

    @api.depends('delivery_id')
    def _compute_financial_info(self):
        """Compute financial information"""
        for wizard in self:
            if not wizard.delivery_id:
                continue

            delivery = wizard.delivery_id

            wizard.total_gross_amount = delivery.gross_amount
            wizard.buyer_part_payment = delivery.buyer_part_payment or 0
            wizard.freight_adjustment = delivery.freight_adjustment or 0
            wizard.buyer_adjustment = delivery.buyer_adjustment or 0
            wizard.buyer_adjustment_description = delivery.buyer_adjustments_description or ''
            wizard.net_due = delivery.total_due

    @api.depends('delivery_net_weight', 'delivery_capped_net_weight', 'delivery_avg_weight', 'delivery_capped_avg_weight')
    def _compute_weight_displays(self):
        """Compute display strings for weights with capped notation"""
        for wizard in self:
            # Net weight display
            if wizard.delivery_capped_net_weight > 0 and wizard.delivery_net_weight > wizard.delivery_capped_net_weight:
                wizard.delivery_net_weight_display = f"{wizard.delivery_net_weight:,.0f} ({wizard.delivery_capped_net_weight:,.0f}*)"
            else:
                wizard.delivery_net_weight_display = f"{wizard.delivery_net_weight:,.0f}"

            # Average weight display
            if wizard.delivery_capped_avg_weight > 0 and wizard.delivery_avg_weight > wizard.delivery_capped_avg_weight:
                wizard.delivery_avg_weight_display = f"{wizard.delivery_avg_weight:,.0f} ({wizard.delivery_capped_avg_weight:,.0f}*)"
            else:
                wizard.delivery_avg_weight_display = f"{wizard.delivery_avg_weight:,.0f}"

    @api.depends('delivery_id')
    def _compute_contract_lines(self):
        """Compute contract lines for tree view display"""
        for wizard in self:
            if not wizard.delivery_id or not wizard.delivery_id.contract_id:
                wizard.contract_lines = [(5, 0, 0)]
                continue
            
            contract = wizard.delivery_id.contract_id
            lines = []
            
            # Head 1 line
            if wizard.contract_head1 and wizard.contract_head1 > 0:
                lines.append((0, 0, {
                    'head_group': 'Head 1',
                    'head_count': wizard.contract_head1,
                    'kind': wizard.contract_kind1 or '',
                    'gross_weight': wizard.contract_head1 * (wizard.contract_weight1 or 0),
                    'shrink': wizard.contract_shrink or 0,
                    'net_weight': wizard.contract_head1 * (wizard.contract_weight1 or 0) * (1 - (wizard.contract_shrink or 0) / 100),
                    'avg_weight': wizard.contract_weight1 or 0,
                    'price': wizard.contract_price or 0,
                    'gross_amount': wizard.contract_head1 * (wizard.contract_weight1 or 0) * (wizard.contract_price or 0) / 100,
                }))
            
            # Head 2 line
            if wizard.contract_head2 and wizard.contract_head2 > 0:
                lines.append((0, 0, {
                    'head_group': 'Head 2',
                    'head_count': wizard.contract_head2,
                    'kind': wizard.contract_kind2 or '',
                    'gross_weight': wizard.contract_head2 * (wizard.contract_weight2 or 0),
                    'shrink': wizard.contract_shrink or 0,
                    'net_weight': wizard.contract_head2 * (wizard.contract_weight2 or 0) * (1 - (wizard.contract_shrink or 0) / 100),
                    'avg_weight': wizard.contract_weight2 or 0,
                    'price': wizard.contract_price2 or 0,
                    'gross_amount': wizard.contract_head2 * (wizard.contract_weight2 or 0) * (wizard.contract_price2 or 0) / 100,
                }))
            
            wizard.contract_lines = lines

    @api.depends('rep_ids', 'rep_ids.rep_id')
    def _compute_rep_names_list(self):
        """Compute the actual rep partner records for display"""
        for record in self:
            if record.rep_ids:
                rep_partners = record.rep_ids.mapped('rep_id').filtered(lambda p: p)
                record.rep_names_list = rep_partners
            else:
                record.rep_names_list = [(5, 0, 0)]

    def action_generate_pdf(self):
        """Generate the buyer invoice PDF with dynamic filename"""
        self.ensure_one()
        # Pass the delivery record instead of the wizard
        return self.env.ref('liveag_consignment.action_report_buyer_invoice').report_action(self.delivery_id)

    def action_generate_and_email_pdf(self):
        """Generate PDF and email it to the buyer using email template"""
        self.ensure_one()
        
        attachment = None
        try:
            # Generate the PDF
            report_action = self.env.ref('liveag_consignment.action_report_buyer_invoice')
            pdf_content, dummy = report_action._render_qweb_pdf('liveag_consignment.action_report_buyer_invoice', [self.delivery_id.id])
            
            # Get buyer email
            buyer_email = self.buyer_email
            if not buyer_email:
                buyer_identifier = getattr(self, 'buyer_id', None)
                buyer_name = buyer_identifier.name if buyer_identifier and hasattr(buyer_identifier, 'name') else str(buyer_identifier) if buyer_identifier else 'Unknown'
                raise UserError(_("No email address found for the buyer: %s.") % buyer_name)
            
            # Create PDF attachment
            attachment_vals = {
                'name': f'Buyer_Invoice_Lot_{self.delivery_id.lot_number}.pdf',
                'type': 'binary',
                'raw': pdf_content,
                'res_model': 'consignment.delivery',
                'res_id': self.delivery_id.id,
            }
            attachment = self.env['ir.attachment'].create(attachment_vals)
            
            # Get the email template
            template = self.env.ref('liveag_consignment.email_template_buyer_invoice')
            
            # Send email using template - pass the delivery record instead of the wizard
            template.with_context(
                attachment_ids=[attachment.id]
            ).send_mail(self.delivery_id.id, force_send=True)

            # Post to delivery chatter so the sent invoice is visible in the thread
            # (send_mail's chatter entry is destroyed by auto_delete on the template)
            try:
                self.delivery_id.message_post(
                    body=_('Buyer invoice emailed to %s') % buyer_email,
                    subject=_('Buyer Invoice - Lot #%s') % self.delivery_id.lot_number,
                    attachment_ids=[attachment.id],
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
            except Exception as post_error:
                _logger.warning("Failed to post buyer invoice to delivery chatter: %s", post_error)

            # Show success message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Buyer invoice has been sent to %s') % buyer_email,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            # Clean up attachment if it was created but email failed
            if attachment:
                try:
                    attachment.unlink()
                except Exception as cleanup_error:
                    _logger.error("Failed to cleanup attachment %s: %s", attachment.id, cleanup_error)
            
            # Re-raise the original exception
            raise UserError(_("Failed to send buyer invoice email: %s") % str(e))
