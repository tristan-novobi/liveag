# Copyright © 2026 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo import sql_db
import base64
import logging
import threading
import time

_logger = logging.getLogger(__name__)

REPORT_TYPE_SELECTION = [
    ('buyer_report', 'Buyer Report'),
    ('seller_report', 'Seller Report'),
    ('rep_recap', 'Rep Recap'),
]

STATE_SELECTION = [
    ('draft', 'Draft'),
    ('sent', 'Sent'),
    ('failed', 'Failed'),
    ('no_email', 'No Email'),
]


class AuctionReportEmail(models.Model):
    _name = 'auction.report.email'
    _description = 'Auction Report Email'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ============================== FIELDS ==================================
    auction_id = fields.Many2one(
        comodel_name='sale.auction',
        string='Auction',
        required=True,
        index=True,
        tracking=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        required=True,
        index=True,
        help='Recipient partner (Seller/Buyer/Rep).',
        tracking=True,
        ondelete='restrict',
    )
    email_to = fields.Char(
        string='Email To',
        index=True,
    )
    report_type = fields.Selection(
        selection=REPORT_TYPE_SELECTION,
        string='Report Type',
        required=True,
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=STATE_SELECTION,
        string='State',
        required=True,
        default='draft',
        index=True,
        tracking=True,
        copy=False,
    )
    mail_id = fields.Many2one(
        comodel_name='mail.mail',
        string='Mail',
        readonly=True,
        ondelete='set null',
    )
    error_message = fields.Text(
        string='Error Message',
        readonly=True,
    )
    sent_at = fields.Datetime(
        string='Sent At',
        readonly=True,
        copy=False,
    )
    # Optional filters copied from wizard for reproducibility
    date_from = fields.Date(string='Sale Date From', help='Optional start date to filter contracts.')
    date_to = fields.Date(string='Sale Date To', help='Optional end date to filter contracts.')
    print_with_contracts = fields.Boolean(string='Print With Contracts', help='If True, include contracts detail pages in the report.')

    _auction_partner_report_unique = models.Constraint(
        'unique(auction_id, partner_id, report_type)',
        "Only one email per auction/partner/report type is allowed.",
    )

    # ============================== HELPERS =================================
    def get_report_type_label(self):
        self.ensure_one()
        return dict(REPORT_TYPE_SELECTION).get(self.report_type, self.report_type)

    def _compute_filtered_contract_ids(self, report_type):
        self.ensure_one()
        auction = self.auction_id
        # Prefer stored values; fallback to context
        date_from = self.date_from or self.env.context.get('date_from')
        date_to = self.date_to or self.env.context.get('date_to')
        contracts = auction.sold_contracts_ids
        if date_from:
            if isinstance(date_from, str):
                date_from = fields.Date.from_string(date_from)
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= date_from)
        if date_to:
            if isinstance(date_to, str):
                date_to = fields.Date.from_string(date_to)
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= date_to)
        if report_type == 'buyer_report':
            contracts = contracts.filtered(lambda c: c.buyer_id.id == self.partner_id.id)
            contracts = contracts.sorted(key=lambda c: c.lot_number or '')
        elif report_type in ('seller_report', 'rep_recap'):
            contracts = contracts.sorted(lambda c: c.lot_number or 0)
        return contracts.ids

    def _get_report_action_xmlid_and_context(self):
        self.ensure_one()
        if not self.auction_id:
            raise UserError(_('Auction is required on the email.'))
        if not self.partner_id:
            raise UserError(_('Partner is required on the email.'))

        if self.report_type == 'buyer_report':
            return ('liveag_consignment.action_report_buyer', {
                'active_model': 'sale.auction',
                'active_id': self.auction_id.id,
                'buyer_id': self.partner_id.id,
                'filtered_contract_ids': self._compute_filtered_contract_ids('buyer_report'),
                'print_with_contracts': self.print_with_contracts if self.print_with_contracts else self.env.context.get('print_with_contracts'),
            })
        if self.report_type == 'seller_report':
            return ('liveag_consignment.action_report_seller', {
                'active_model': 'sale.auction',
                'active_id': self.auction_id.id,
                'seller_id': self.partner_id.id,
                'filtered_contract_ids': self._compute_filtered_contract_ids('seller_report'),
                'print_with_contracts': self.print_with_contracts if self.print_with_contracts else self.env.context.get('print_with_contracts'),
            })
        if self.report_type == 'rep_recap':
            return ('liveag_consignment.action_report_rep', {
                'active_model': 'sale.auction',
                'active_id': self.auction_id.id,
                'rep_id': self.partner_id.id,
                'filtered_contract_ids': self._compute_filtered_contract_ids('rep_recap'),
                'print_with_contracts': self.print_with_contracts if self.print_with_contracts else self.env.context.get('print_with_contracts'),
            })
        raise UserError(_('Unsupported report type: %s') % (self.report_type,))

    def _render_report_pdf(self):
        self.ensure_one()
        xmlid, extra_ctx = self._get_report_action_xmlid_and_context()
        report_action = self.env.ref(xmlid)
        if not report_action or report_action._name != 'ir.actions.report':
            raise UserError(_('Report action not found: %s') % (xmlid,))
        safe_auction = (self.auction_id.name or 'Auction').replace('/', '-')
        safe_partner = (self.partner_id.name or 'Partner').replace('/', '-')
        filename = f"{self.get_report_type_label().replace(' ', '_')}_{safe_auction}_{safe_partner}.pdf"
        ctx = dict(self.env.context or {})
        ctx.update(extra_ctx or {})
        pdf_content, _format = report_action.with_context(extra_ctx)._render_qweb_pdf(xmlid, [self.auction_id.id])
        if not pdf_content:
            raise UserError(_('Failed to render PDF for %s') % (self.display_name,))
        return pdf_content, filename

    # ============================== ACTIONS =================================
    def action_send_single(self):
        for email in self:
            if not email.exists():
                continue
            if email.state == 'sent':
                continue
            # Retry loop to handle concurrent updates (serialization failures)
            max_attempts = 3
            attempt = 0
            while attempt < max_attempts:
                try:
                    email_to_addr = (email.email_to or '').strip() or (email.partner_id.email or '').strip()
                    if not email_to_addr:
                        email.write({'state': 'no_email', 'error_message': _('Missing partner email')})
                        email.env.cr.commit()
                        break
                    pdf_bytes, filename = email._render_report_pdf()
                    attachment = email.env['ir.attachment'].create({
                        'name': filename,
                        'res_model': email._name,
                        'res_id': email.id,
                        'type': 'binary',
                        'datas': base64.b64encode(pdf_bytes),
                        'mimetype': 'application/pdf',
                    })
                    template = email.env.ref('liveag_consignment.mail_template_auction_report', raise_if_not_found=False)
                    if not template:
                        raise UserError(_('Email template not found: liveag_consignment.mail_template_auction_report'))
                    template_ctx = {
                        'report_type_label': email.get_report_type_label(),
                        'partner_name': email.partner_id.name or '',
                    }
                    email_values = {
                        'email_to': email_to_addr,
                        'attachment_ids': [(4, attachment.id)],
                    }
                    # Send with queue record as the object (template model: auction.report.email)
                    mail_id = template.with_context(template_ctx).send_mail(email.id, force_send=True, email_values=email_values)
                    mail = email.env['mail.mail'].browse(mail_id) if mail_id else email.mail_id
                    email.write({
                        'state': 'sent',
                        'sent_at': fields.Datetime.now(),
                        'mail_id': mail.id if mail else False,
                        'error_message': False,
                        'email_to': email_to_addr,
                    })
                    email.env.cr.commit()
                    break
                except Exception as e:
                    # Detect serialization failure and retry
                    if 'could not serialize access due to concurrent update' in str(e):
                        email.env.cr.rollback()
                        attempt += 1
                        # short backoff
                        time.sleep(0.1 * attempt)
                        continue
                    _logger.exception('Failed sending auction report email (email %s): %s', email.id, e)
                    email.write({
                        'state': 'failed',
                        'error_message': str(e)[:2000],
                    })
                    email.env.cr.commit()
                    break
        return True

    @api.model
    def send_in_background(self, email_ids):
        if not email_ids:
            return True
        db_name = self.env.cr.dbname
        uid = self.env.uid
        context = dict(self.env.context or {})

        def _runner(db, user_id, ids, ctx):
            with sql_db.db_connect(db).cursor() as cr:
                env = api.Environment(cr, user_id, ctx)
                env['auction.report.email'].browse(ids).action_send_single()

        thread = threading.Thread(target=_runner, args=(db_name, uid, email_ids, context), daemon=True)
        thread.start()
        return True
