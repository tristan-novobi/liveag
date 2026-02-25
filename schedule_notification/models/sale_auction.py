from odoo import models, fields 
from odoo.exceptions import UserError

class SaleAuction(models.Model):
    _inherit = 'sale.auction'

    schedule_notifications = fields.Boolean(string='Schedule Notifications', 
                                            default=False)
    
    date_for_next_notification = fields.Date(string='Date for Next Notification')



    def _send_scheduled_notifications(self):
        for auction in self.search([('schedule_notifications', '=', True), 
                                    ('date_for_next_notification', '=', fields.Date.today())]):
            contracts = auction.contracts_ids
            # raise UserError(contracts)
            if not contracts:
                continue
            reps = contracts.mapped('primary_rep')
            if not reps:
                continue

            for rep in reps:
                if not rep.email:
                    continue
                # Send email notification
                sellers_to_reach_out = contracts.filtered(lambda c: c.primary_rep == rep).mapped('seller_id')
                sellers_list = ''.join([f'<li>{seller.name}</li>' for seller in sellers_to_reach_out])
                self.env['mail.mail'].create({
                    'subject': f'Auction Reminder: {auction.name}',
                    'email_to': rep.email,
                    'body_html': f'''
                    <p>Dear {rep.name},</p>
                    <p>This is a reminder for the auction {auction.name}.</p>
                    <p>Please reach out to the following sellers:</p>
                    <ul>
                        {sellers_list}
                    </ul>
                    ''',
                })