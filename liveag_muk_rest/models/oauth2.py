from odoo import _, models, api, fields
from odoo.exceptions import ValidationError

from odoo.addons.liveag_muk_rest.tools import common


class OAuth2(models.Model):
    
    _name = 'muk_rest.oauth2'
    _description = "OAuth2 Configuration"

    # ----------------------------------------------------------
    # Fields
    # ----------------------------------------------------------
    name = fields.Char(
        string="Name",
        related='oauth_id.name',
        readonly=False,
        store=True,
        required=True
    )
    
    oauth_id = fields.Many2one(
        comodel_name="muk_rest.oauth",
        string="OAuth",
        required=True,
        ondelete="cascade",
        help="Parent OAuth configuration record linked to this OAuth2 setup.",
    )
    
    active = fields.Boolean(
        related='oauth_id.active',
        readonly=False,
        store=True,
        default=True,
    )
    
    state = fields.Selection(
        selection=[
            ('authorization_code', 'Authorization Code'),
            ('implicit', 'Implicit'),
            ('password', 'Password Credentials'),
            ('client_credentials', 'Client Credentials')
        ],
        string="OAuth Type",
        required=True,
        default='authorization_code'
    )
    
    client_id = fields.Char(
        string="Client Key",
        required=True,
        copy=False,
        default=lambda x: common.generate_token()
    )
    
    client_secret = fields.Char(
        string="Client Secret",
        copy=False,
        default=lambda x: common.generate_token()
    )
    
    default_callback_id = fields.Many2one(
        compute='_compute_default_callback_id',
        comodel_name='muk_rest.callback',
        string="Default Callback",
        readonly=True,
        store=True,
    )
    
    user_id = fields.Many2one(
        comodel_name='res.users',
        ondelete='cascade',
        string="User",
    )

    company = fields.Char(
        string="Company",
        related='oauth_id.company',
        readonly=False,
        store=True,
    )

    homepage = fields.Char(
        string="Homepage URL",
        related='oauth_id.homepage',
        readonly=False,
        store=True,
    )

    security = fields.Selection(
        selection=[
            ('basic', "Basic Access Control"),
            ('advanced', "Advanced Access Control")
        ],
        string="Security",
        required=True,
        default='basic',
    )

    description = fields.Text(
        string="Description",
        related='oauth_id.description',
        readonly=False,
        store=True,
    )

    logo_url = fields.Char(
        string="Product logo URL",
        related='oauth_id.logo_url',
        readonly=False,
        store=True,
    )

    privacy_policy = fields.Char(
        string="Privacy policy URL",
        related='oauth_id.privacy_policy',
        readonly=False,
        store=True,
    )

    service_terms = fields.Char(
        string="Terms of service URL",
        related='oauth_id.service_terms',
        readonly=False,
        store=True,
    )

    callback_ids = fields.One2many(
        comodel_name='muk_rest.callback',
        # inverse_name='oauth_id', 
        related='oauth_id.callback_ids',
        string="Callback URLs",
    )

    rule_ids = fields.One2many(
        comodel_name='muk_rest.access_rules',
        # inverse_name='oauth_id', 
        related='oauth_id.rule_ids',
        string="Access Rules",
    )
    # ----------------------------------------------------------
    # Constraints
    # ----------------------------------------------------------
    
    _sql_constraints = [
        ('client_id_unique', 'UNIQUE (client_id)', 'Client ID must be unique.'),
        ('client_secret_unique', 'UNIQUE (client_secret)', 'Client Secret must be unique.'),
    ]
    
    @api.constrains('state', 'default_callback_id')
    def _check_default_callback_id(self):
        for record in self.filtered(lambda rec: rec.state == 'authorization_code'):
            if not record.default_callback_id:
                raise ValidationError(_("Authorization Code needs a default callback."))

    # ----------------------------------------------------------
    # Compute
    # ----------------------------------------------------------
    
    @api.depends('oauth_id', 'oauth_id.callback_ids', 'oauth_id.callback_ids.sequence')
    def _compute_default_callback_id(self):
        for record in self:
            callbacks = record.oauth_id.callback_ids if record.oauth_id else self.env['muk_rest.callback']
            if len(callbacks) >= 1:
                record.default_callback_id = callbacks[0]
            else:
                record.default_callback_id = False

    # ----------------------------------------------------------
    # ORM
    # ----------------------------------------------------------

    def unlink(self):
        self.mapped('oauth_id').unlink()
        return super(OAuth2, self).unlink()
        