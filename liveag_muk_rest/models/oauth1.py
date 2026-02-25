from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

from odoo.addons.liveag_muk_rest.tools import common


class OAuth1(models.Model):
    
    _name = 'muk_rest.oauth1'
    _description = "OAuth1 Configuration"

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
        help="Parent OAuth configuration record linked to this OAuth1 setup.",
    )

    active = fields.Boolean(
        related='oauth_id.active',
        readonly=False,
        store=True,
        default=True,
    )
    
    consumer_key = fields.Char(
        string="Consumer Key",
        required=True,
        copy=False,
        default=lambda x: common.generate_token()
    )
    
    consumer_secret = fields.Char(
        string="Consumer Secret",
        required=True,
        copy=False,
        default=lambda x: common.generate_token()
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
        ('consumer_key_unique', 'UNIQUE (consumer_key)', 'Consumer Key must be unique.'),
        ('consumer_secret_unique', 'UNIQUE (consumer_secret)', 'Consumer Secret must be unique.'),
    ]
    
    @api.constrains('consumer_key')
    def check_consumer_key(self):
        for record in self:
            if not (20 < len(record.consumer_key) < 50):
                raise ValidationError(_("The consumer key must be between 20 and 50 characters long."))
            
    @api.constrains('consumer_secret')
    def check_consumer_secret(self):
        for record in self:
            if not (20 < len(record.consumer_secret) < 50):
                raise ValidationError(_("The consumer secret must be between 20 and 50 characters long."))

    # ----------------------------------------------------------
    # ORM
    # ----------------------------------------------------------

    def unlink(self):
        self.mapped('oauth_id').unlink()
        return super(OAuth1, self).unlink()
