from odoo import api, fields, models, _

class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    region_id = fields.Many2one(
        'res.region',
        string="Region",
        help="Region associated with the state."
    )
    beef_checkoff = fields.Float(string='Beef Checkoff $/Head')
    
    # Beef checkoff related fields
    national_beef_checkoff = fields.Float(string='National Beef Checkoff $/Head', default=0.0)
    state_beef_checkoff = fields.Float(string='State Beef Checkoff $/Head', default=0.0)
    other_state_fees = fields.Float(string='Other State Fees $/Head', default=0.0)
    fee_description = fields.Text(string='Fee Description')
    brand_inspector_national = fields.Float(string='Brand Inspector National $/Head', default=0.0)
    brand_inspector_state = fields.Float(string='Brand Inspector State $/Head', default=0.0)
    
    @api.model
    def _update_from_beef_checkoff(self):
        """Update state records with beef checkoff information"""
        BeefCheckoff = self.env['beef.checkoff']
        
        for state in self.search([]):
            checkoff = BeefCheckoff._get_by_state_code(state.code)
            if checkoff:
                state.write({
                    'national_beef_checkoff': checkoff.national_beef_checkoff,
                    'state_beef_checkoff': checkoff.state_beef_checkoff,
                    'other_state_fees': checkoff.other_state_fees,
                    'fee_description': checkoff.description,
                    'brand_inspector_national': checkoff.brand_inspector_national,
                    'brand_inspector_state': checkoff.brand_inspector_state,
                })