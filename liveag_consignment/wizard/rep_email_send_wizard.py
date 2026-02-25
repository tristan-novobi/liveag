from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class RepEmailSendWizard(models.TransientModel):
    _name = 'rep.email.send.wizard'
    _description = 'Send Rep Recap via Email'

    auction_id = fields.Many2one('sale.auction', string='Auction', required=True)
    date_from = fields.Date(string='Select Sale Date From')
    date_to = fields.Date(string='Select Sale Date To')
    print_with_contracts = fields.Boolean(default=False)
    show_date_filter = fields.Boolean(compute='_compute_show_date_filter', store=True)
    available_rep_ids = fields.Many2many('res.partner', compute='_compute_available_rep_ids', store=True)

    @api.depends('auction_id.sale_type')
    def _compute_show_date_filter(self):
        for wizard in self:
            sale_type = wizard.auction_id.sale_type.name if wizard.auction_id.sale_type else False
            wizard.show_date_filter = sale_type in ['Private Treaty', 'LiveAgXchange']

    @api.depends('auction_id', 'date_from', 'date_to')
    def _compute_available_rep_ids(self):
        for wizard in self:
            try:
                contracts = wizard.auction_id.sudo().sold_contracts_ids
                if wizard.date_from:
                    contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= wizard.date_from)
                if wizard.date_to:
                    contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= wizard.date_to)
                rep_partners = contracts.mapped('rep_ids').filtered(lambda r: r.active).mapped('rep_id')
                valid_reps = rep_partners.filtered(lambda r: r.exists() and r.with_user(self.env.user.id).check_access_rights('read', raise_exception=False))
                wizard.available_rep_ids = [(6, 0, valid_reps.ids)]
            except Exception:
                wizard.available_rep_ids = [(6, 0, [])]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            res['auction_id'] = self.env.context.get('active_id')
        return res

    def action_send_emails(self):
        self.ensure_one()
        Email = self.env['auction.report.email'].with_context(
            date_from=self.date_from,
            date_to=self.date_to,
            print_with_contracts=self.print_with_contracts,
        )
        email_ids_to_send = []
        for partner in self.available_rep_ids:
            email = Email.search([
                ('auction_id', '=', self.auction_id.id),
                ('partner_id', '=', partner.id),
                ('report_type', '=', 'rep_recap'),
            ], limit=1)
            if not email:
                email = Email.create({
                    'auction_id': self.auction_id.id,
                    'partner_id': partner.id,
                    'report_type': 'rep_recap',
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

        # Ensure queue records are committed before background start
        self.env.cr.commit()
        if email_ids_to_send:
            self.env['auction.report.email'].send_in_background(email_ids_to_send)

        action = self.env.ref('liveag_consignment.action_auction_report_email').read()[0]
        action['domain'] = [('auction_id', '=', self.auction_id.id)]
        return action
