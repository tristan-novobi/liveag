from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class RepReportWizard(models.TransientModel):
    _name = 'rep.report.wizard'
    _description = 'Rep Report Wizard'

    auction_id = fields.Many2one('sale.auction', string='Auction', required=True)
    rep_id = fields.Many2one('res.partner', string='Rep')
    date_from = fields.Date(string='Select Sale Date')
    date_to = fields.Date(string='Select Sale Date To')
    print_with_contracts = fields.Boolean(default=False)
    show_date_filter = fields.Boolean(compute='_compute_show_date_filter', store=True)
    available_rep_ids = fields.Many2many('res.partner', compute='_compute_available_rep_ids', store=True)

    @api.depends('auction_id.sale_type')
    def _compute_show_date_filter(self):
        for wizard in self:
            sale_type = wizard.auction_id.sale_type.name if wizard.auction_id.sale_type else False
            wizard.show_date_filter = sale_type in ['Private Treaty', 'LiveAgXchange']

    @api.depends('auction_id', 'date_from')
    def _compute_available_rep_ids(self):
        for wizard in self:
            try:
                contracts = wizard.auction_id.sudo().sold_contracts_ids
                _logger.info(f"Initial contracts count: {len(contracts)}")

                if wizard.date_from:
                    contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= wizard.date_from)
                    _logger.info(f"Contracts after date filter ({wizard.date_from}): {len(contracts)}")

                if wizard.date_to:
                    contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= wizard.date_to)
                    _logger.info(f"Contracts after date filter ({wizard.date_to}): {len(contracts)}")

                rep_partners = contracts.mapped('rep_ids').filtered(lambda r: r.active).mapped('rep_id')

                valid_reps = rep_partners.filtered(lambda r: r.exists() and r.with_user(self.env.user.id).check_access_rights('read', raise_exception=False))

                _logger.info(f"Final valid rep partner ids: {valid_reps.ids}")
                wizard.available_rep_ids = [(6, 0, valid_reps.ids)]
            except Exception as e:
                _logger.error(f"Error computing available reps: {str(e)}")
                wizard.available_rep_ids = [(6, 0, [])]

    @api.onchange('date_from', 'date_to')
    def _onchange_date_from(self):
        self._compute_available_rep_ids()
        # Clear the selected rep_id if it's not in the available reps
        if self.rep_id and self.rep_id not in self.available_rep_ids:
            self.rep_id = False
        return {'domain': {'rep_id': [('id', 'in', self.available_rep_ids.ids)]}}

    def print_report(self):
        self.ensure_one()
        contracts = self.auction_id.sudo().sold_contracts_ids
        if self.date_from:
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= self.date_from)
        if self.date_to:
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= self.date_to)

        return self.env.ref('liveag_consignment.action_report_rep').with_context(
            rep_id=self.rep_id.id,
            date_from=self.date_from,
            date_to=self.date_to,
            filtered_contract_ids=contracts.ids,
            print_with_contracts=self.print_with_contracts
        ).report_action(self.auction_id)
