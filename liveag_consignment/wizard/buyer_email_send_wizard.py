from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class BuyerEmailSendWizard(models.TransientModel):
    _name = 'buyer.email.send.wizard'
    _description = 'Send Buyer Reports via Email'

    # ============================== FIELDS ==================================
    auction_id = fields.Many2one('sale.auction', string='Auction', required=True)
    date_from = fields.Date(string='Select Sale Date From')
    date_to = fields.Date(string='Select Sale Date To')
    print_with_contracts = fields.Boolean(default=False)
    show_date_filter = fields.Boolean(compute='_compute_show_date_filter', store=True)
    available_buyer_ids = fields.Many2many('res.partner', compute='_compute_available_buyers', store=True)

    # ============================== COMPUTES ================================
    @api.depends('auction_id.sale_type')
    def _compute_show_date_filter(self):
        for wizard in self:
            sale_type = wizard.auction_id.sale_type.name if wizard.auction_id.sale_type else False
            wizard.show_date_filter = sale_type in ['Private Treaty', 'LiveAgXchange']

    @api.depends('auction_id', 'date_from', 'date_to')
    def _compute_available_buyers(self):
        for wizard in self:
            contracts = wizard.auction_id.sold_contracts_ids
            if wizard.date_from:
                contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= wizard.date_from)
            if wizard.date_to:
                contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= wizard.date_to)
            buyer_ids = contracts.mapped('buyer_id').ids
            wizard.available_buyer_ids = [(6, 0, buyer_ids)]

    # ============================== DEFAULTS ===============================
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            res['auction_id'] = self.env.context.get('active_id')
        return res

    # ============================== ACTIONS =================================
    def action_send_emails(self):
        self.ensure_one()
        Email = self.env['auction.report.email'].with_context(
            date_from=self.date_from,
            date_to=self.date_to,
            print_with_contracts=self.print_with_contracts,
        )
        email_ids_to_send = []
        for partner in self.available_buyer_ids:
            email = Email.search([
                ('auction_id', '=', self.auction_id.id),
                ('partner_id', '=', partner.id),
                ('report_type', '=', 'buyer_report'),
            ], limit=1)
            if not email:
                email = Email.create({
                    'auction_id': self.auction_id.id,
                    'partner_id': partner.id,
                    'report_type': 'buyer_report',
                    'state': 'draft',
                    'email_to': (partner.email or '').strip() or False,
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'print_with_contracts': self.print_with_contracts,
                })
            else:
                email.write({
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'print_with_contracts': self.print_with_contracts,
                })
            email_ids_to_send.append(email.id)

        # Ensure queue records are visible to the background thread
        self.env.cr.commit()
        # Run sending in background
        if email_ids_to_send:
            self.env['auction.report.email'].send_in_background(email_ids_to_send)

        action = self.env.ref('liveag_consignment.action_auction_report_email').read()[0]
        action['domain'] = [('auction_id', '=', self.auction_id.id)]
        return action
