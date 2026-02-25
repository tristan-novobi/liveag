from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BeefCheckoff(models.Model):
    _name = 'beef.checkoff'
    _description = 'Beef Checkoff State Information'
    _order = "state_code"
    
    state_code = fields.Char(string='State Code', required=True)
    national_beef_checkoff = fields.Float(string='National Beef Checkoff')
    state_beef_checkoff = fields.Float(string='State Beef Checkoff')
    other_state_fees = fields.Float(string='Other State Fees')
    description = fields.Text(string='Description')
    brand_inspector_national = fields.Float(string='Brand Inspector National')
    brand_inspector_state = fields.Float(string='Brand Inspector State')
    
    active = fields.Boolean(string='Active', default=True)
    
    # Used for data import from CSV
    def _get_by_state_code(self, state_code):
        return self.search([('state_code', '=', state_code)], limit=1)
    
    @api.constrains('state_code')
    def _check_duplicated_state_code(self):
        for record in self:
            if not record.state_code:
                continue
                
            value_esc = record.state_code.replace('_', '\\_').replace('%', '\\%')
            if self.with_context(active_test=False).search([('id', '!=', record.id), ('state_code', '=ilike', value_esc)]):
                raise ValidationError(_(f'State code {record.state_code} already exists.'))