from odoo import api, fields, models
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class SellerReportWizard(models.TransientModel):
    _name = 'seller.report.wizard'
    _description = 'Seller Report Wizard'

    auction_id = fields.Many2one('sale.auction', string='Auction', required=True)
    seller_id = fields.Many2one('res.partner', string='Seller')
    date_from = fields.Date(string='Select Sale Date')
    date_to = fields.Date(string='Select Sale Date To')
    print_with_contracts = fields.Boolean(default=False)
    show_date_filter = fields.Boolean(compute='_compute_show_date_filter', store=True)
    available_seller_ids = fields.Many2many('res.partner', compute='_compute_available_sellers', store=True)

    @api.depends('auction_id.sale_type')
    def _compute_show_date_filter(self):
        for wizard in self:
            sale_type = wizard.auction_id.sale_type.name if wizard.auction_id.sale_type else False
            wizard.show_date_filter = sale_type in ['Private Treaty', 'LiveAgXchange']

    @api.depends('auction_id', 'date_from')
    def _compute_available_sellers(self):
        for wizard in self:
            contracts = wizard.auction_id.sold_contracts_ids
            _logger.info(f"Initial contracts count: {len(contracts)}")

            if wizard.date_from:
                contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= wizard.date_from)
                _logger.info(f"Contracts after date filter ({wizard.date_from}): {len(contracts)}")

            if wizard.date_to:
                contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= wizard.date_to)
                _logger.info(f"Contracts after date filter ({wizard.date_to}): {len(contracts)}")

            seller_ids = set()
            for contract in contracts:
                if contract.seller_id:
                    seller_ids.add(contract.seller_id.id)
                for addendum in contract.addendum_ids:
                    if addendum.seller_id:
                        seller_ids.add(addendum.seller_id.id)
            _logger.info(f"Final unique seller count: {len(seller_ids)}")
            wizard.available_seller_ids = [(6, 0, list(seller_ids))]

    @api.onchange('date_from', 'date_to')
    def _onchange_date_from(self):
        self._compute_available_sellers()
        if self.seller_id and self.seller_id.id not in self.available_seller_ids.ids:
            self.seller_id = False
        return {'domain': {'seller_id': [('id', 'in', self.available_seller_ids.ids)]}}

    def action_print_report(self):
        self.ensure_one()
        contracts = self.auction_id.sold_contracts_ids
        if self.date_from:
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= self.date_from)

        if self.date_to:
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= self.date_to)

        contracts = contracts.sorted(lambda c: c.lot_number or 0)

        return self.env.ref('liveag_consignment.action_report_seller').with_context(
            active_model='sale.auction',
            active_id=self.auction_id.id,
            seller_id=self.seller_id.id,
            date_from=self.date_from,
            date_to=self.date_to,
            filtered_contract_ids=contracts.ids,
            print_with_contracts=self.print_with_contracts
        ).report_action(self.auction_id) 