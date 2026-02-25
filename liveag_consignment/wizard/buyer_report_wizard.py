from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

class BuyerReportWizard(models.TransientModel):
    _name = 'buyer.report.wizard'
    _description = 'Buyer Report Wizard'

    auction_id = fields.Many2one('sale.auction', string='Auction', required=True)
    buyer_id = fields.Many2one('res.partner', string='Buyer', required=True)
    date_from = fields.Date(string='Select Sale Date From')
    date_to = fields.Date(string='Select Sale Date To')
    print_with_contracts = fields.Boolean(default=False)
    show_date_filter = fields.Boolean(compute='_compute_show_date_filter', store=True)
    available_buyer_ids = fields.Many2many('res.partner', compute='_compute_available_buyers', store=True)

    @api.depends('auction_id.sale_type')
    def _compute_show_date_filter(self):
        for wizard in self:
            sale_type = wizard.auction_id.sale_type.name if wizard.auction_id.sale_type else False
            wizard.show_date_filter = sale_type in ['Private Treaty', 'LiveAgXchange']

    @api.depends('auction_id', 'date_from')
    def _compute_available_buyers(self):
        for wizard in self:
            # Start with all sold contracts
            contracts = wizard.auction_id.sold_contracts_ids
            _logger.info(f"Initial contracts count: {len(contracts)}")

            # Filter contracts by date if date_from is set
            if wizard.date_from:
                contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= wizard.date_from)
                
            # Filter by date_to if it's set
            if wizard.date_to:
                contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= wizard.date_to)

            # Get unique buyer IDs from filtered contracts
            buyer_ids = contracts.mapped('buyer_id').ids
            wizard.available_buyer_ids = [(6, 0, buyer_ids)]

    @api.onchange('date_from', 'date_to')
    def _onchange_date_from(self):
        # Recompute available buyers
        self._compute_available_buyers()
        # Clear the current buyer selection when date changes if that buyer is no longer an option in available buyers
        if self.buyer_id and self.buyer_id.id not in self.available_buyer_ids.ids:
            self.buyer_id = False
            
        return {'domain': {'buyer_id': [('id', 'in', self.available_buyer_ids.ids)]}}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            auction = self.env['sale.auction'].browse(self.env.context.get('active_id'))
            res['auction_id'] = auction.id
            buyers = auction.sold_contracts_ids.mapped('buyer_id')
            if len(buyers) == 1:
                res['buyer_id'] = buyers.id
        return res

    def action_print_report(self):
        self.ensure_one()
        
        # Start with all sold contracts from the auction
        contracts = self.auction_id.sold_contracts_ids
        _logger.info(f"Total auction contracts: {len(contracts)}")
        
        # Filter by the selected buyer
        contracts = contracts.filtered(lambda c: c.buyer_id == self.buyer_id)
        _logger.info(f"Contracts for buyer {self.buyer_id.name}: {len(contracts)}")
        
        # Debug: Show some sample dates and our filter dates
        if contracts:
            sample_contracts = contracts[:3]
            for c in sample_contracts:
                _logger.info(f"Contract {c.id}: sold_date={c.sold_date} (type: {type(c.sold_date).__name__})")
        
        _logger.info(f"Filter date_from: {self.date_from} (type: {type(self.date_from).__name__})")
        _logger.info(f"Filter date_to: {self.date_to} (type: {type(self.date_to).__name__})")
        
        # Filter contracts by date if date_from is set
        if self.date_from:
            before_count = len(contracts)
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= self.date_from)
            _logger.info(f"After date_from filter: {len(contracts)} (was {before_count})")
            
        # Filter by date_to if it's set
        if self.date_to:
            before_count = len(contracts)
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= self.date_to)
            _logger.info(f"After date_to filter: {len(contracts)} (was {before_count})")
        
        # Sort contracts by lot number, lowest to highest
        contracts = contracts.sorted(key=lambda c: c.lot_number or '')
        _logger.info(f"Final contracts count: {len(contracts)}")

        return self.env.ref('liveag_consignment.action_report_buyer').with_context(
            active_model='sale.auction',
            active_id=self.auction_id.id,
            buyer_id=self.buyer_id.id,
            date_from=self.date_from,
            date_to=self.date_to,
            filtered_contract_ids=contracts.ids,
            print_with_contracts=self.print_with_contracts
        ).report_action(self.auction_id)
