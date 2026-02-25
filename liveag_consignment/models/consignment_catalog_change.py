
from odoo import fields, models
from odoo.exceptions import ValidationError

class CatalogChange(models.Model):
    _name = 'catalog.change'
    _description = 'Catalog Change'
    _order = 'create_date desc'

    contract_id = fields.Many2one('consignment.contract', string='Contract', required=True, ondelete='cascade')
    field_name = fields.Char(string='Field Name', required=True)
    old_value = fields.Char(string='Old Value')
    new_value = fields.Char(string='New Value')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='State', default='draft')
    approved_by = fields.Many2one('res.users', string='Approved By')
    approved_date = fields.Datetime(string='Approved Date')
    notes = fields.Text(string='Notes')
    catalog_change = fields.Boolean(string='Catalog Change', default=True)

    def action_approve(self):
        user_partner = self.env.user.partner_id
        is_admin = 'Admin' in user_partner.contact_type_ids.mapped('name')
        if is_admin:
            self.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now()
            })
            if self.contract_id and self.field_name:
                self.contract_id.with_context(from_catalog_change=True).write({self.field_name: self.new_value}) 
        else:
            raise ValidationError("Only Admin users can approve changes.")

    def action_reject(self):
        self.write({'state': 'rejected'})

    def create(self, data_list):
        if data_list['state'] in ['draft', 'pending']:
            self.env['consignment.contract'].browse(data_list['contract_id']).write({'state': 'changed'})
        return super().create(data_list)