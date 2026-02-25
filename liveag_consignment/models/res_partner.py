# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from collections import defaultdict
_logger = logging.getLogger(__name__)

SOLD_STATES = ['sold', 'delivery_ready','delivered']
class ResPartner(models.Model):
    _inherit = 'res.partner'

    buyer_name = fields.Char('Buyer Name', compute='_compute_buyer_name', store=False)
    buyer_name_display_preference = fields.Selection(
        selection=[
            ('use_name', 'Use Name'),
            ('use_company', 'Use Company'),
            ('use_both', 'Use Both')
        ],
        string='Buyer Name',
        default='use_name'
    )

    ytd_head_sold = fields.Float(string='YTD Head Sold', 
                                 compute = 'get_ytd_head_sold',
                                 help="Year to date head sold for this rep/seller")
    
    ytd_head_delivered = fields.Float(string='YTD Head Delivered', 
                                 compute = 'get_ytd_head_delivered',
                                 help='''Year-to-date heads delivered for this Rep/Seller. 
                                 The calculation includes only contracts in "Delivered" status 
                                 and counts the number of heads from delivery records linked to those contracts.''')
    
    ltd_head_delivered = fields.Float(string='LTD Head Delivered',
                                      compute = 'get_ltd_head_delivered',
                                      help='''Lifetime-to-date heads delivered for this Rep/Seller.
                                        The calculation includes only contracts in "Delivered" status and is cumulative.''')
    ltd_head_sold = fields.Float(string="LTD Head Sold",
                                 compute = 'get_ltd_head_sold',
                                 help='''Lifetime-to-date heads sold for this Rep/Seller.
                                        The calculation includes only contracts in "Delivered" status and is cumulative.''')

    sale_type_stats_html = fields.Html(
        string="Sales by Type",
        compute="_compute_sale_type_stats_html",
        sanitize=False
    )

    sale_type_stats = fields.Json(
        string='Sale by Type Stats',
        compute="_compute_sale_type_stats",
        copy=False
    )

    rep_name = fields.Char('Rep Name', compute='_compute_rep_name', store=False)
    rep_name_display_preference = fields.Selection(
        selection=[
            ('use_name', 'Use Name'),
            ('use_company', 'Use Company'),
            ('use_both', 'Use Both')
        ],
        string='Rep Name',
        default='use_name'
    )

    seller_name = fields.Char('Seller Name', compute='_compute_seller_name', store=False)
    seller_name_display_preference = fields.Selection(
        selection=[
            ('use_name', 'Use Name'),
            ('use_company', 'Use Company'),
            ('use_both', 'Use Both')
        ],
        string='Seller Name',
        default='use_name'
    )

    has_master_agreement = fields.Boolean(string="Has Master Agreement")
     
    contact_type_ids = fields.Many2many(
        comodel_name='res.contact.type',
        relation='partner_contact_type_rel',
        column1='partner_id',
        column2=('contact_type_id'),
        string='Type(s)'
    )

    lien_holder_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='seller_lien_holder_rel',
        column1='seller_id',
        column2='lien_holder_id',
        string="Lien Holders",
        )

    default_lien_holder_id = fields.Many2one('res.partner', 
                                             string="Default Lien Holder"
                                             )
    default_payment_info_id = fields.Many2one('res.partner', 
                                             string="Default Payment info"
                                             )

    contact_name = fields.Char('Contact Name')

    contact_address_inline_clean = fields.Char(
        string='Address',
        compute='_compute_contact_address_inline_clean',
        store=False,
        )

    clerk_user_id = fields.Char(compute="_compute_clerk_user_id", store=False)
    
    def _compute_clerk_user_id(self):
        for p in self:
            user = self.env["res.users"].sudo().search([("partner_id", "=", p.id)], limit=1)
            p.clerk_user_id = user.clerk_user_id if user else False

    master_agreement_file = fields.Binary('Buyer Agreement')
    seller_master_agreement_file = fields.Binary('Seller Agreement')

    rep_ids = fields.One2many('res.rep',
                              'seller_id',
                              string="Reps",
                              domain=[('contract_id','=',False)],
                              help="From sellers, the list of reps is displayed")

    seller_ids = fields.One2many('res.rep',
                              'rep_id',
                              string="Sellers", 
                              help="From Reps, the list of sellers is displayed")
    
    type = fields.Selection(
        selection_add=[('payment', 'Payment Address'),('bank','Bank'), ('other',)],
        help="- Contact: Use this to organize the contact details of employees of a given company (e.g. CEO, CFO, ...).\n"
             "- Invoice Address: Preferred address for all invoices. Selected by default when you invoice an order that belongs to this company.\n"
             "- Delivery Address: Preferred address for all deliveries. Selected by default when you deliver an order that belongs to this company.\n"
             "- Private: Private addresses are only visible by authorized users and contain sensitive data (employee home addresses, ...).\n"
             "- Follow-up Address: Preferred address for follow-up reports. Selected by default when you send reminders about overdue invoices.\n"
             "- Payment Address: Preferred address for follow-up reports. Selected by default when you send reminders about overdue invoices.\n"
             "- Other: Other address for the company (e.g. subsidiary, ...)")
    
    # Related contracts 
    contracts_as_seller = fields.One2many('consignment.contract',
                                          'seller_id',
                                          help='Contract where this contact is the Seller')

    contracts_as_lien_holder = fields.One2many('consignment.contract',
                                          compute='_compute_contracts_as_lien_holder',
                                          help='Contract where this contact is the Lien Holder')
    contracts_as_buyer = fields.One2many('consignment.contract',
                                          compute='_compute_contracts_as_buyer',
                                          help='Contract where this contact is the seller')

    contracts_as_rep = fields.One2many('consignment.contract',
                                          compute='_compute_contracts_as_rep',
                                          help='Contract where this contact is one of the Reps')

    deliveries_as_rep = fields.One2many('consignment.delivery',
                                          compute='_compute_deliveries_as_rep',
                                          help='Delivery where this contact is one of the Reps')

    affidavit_verified = fields.Boolean('Affidavit Verified')

    verified_date = fields.Date('Verified date')

    verified_buyer = fields.Boolean('Authorized')

    buyer_number_ids = fields.One2many('buyer.number',
                               'partner_id',
                               string="Buyer numbers",
                               help="")
                               
    discount = fields.Float(string='Discount (%)', default=2.0,
                           help="Default discount percentage for this contact")

    hide_seller_fields = fields.Boolean(compute='_compute_hide_seller_fields')
    hide_buyer_fields = fields.Boolean(compute='_compute_hide_buyer_fields')
    hide_lien_holder_fields = fields.Boolean(compute='_compute_hide_lien_holder_fields')
    hide_rep_fields = fields.Boolean(compute='_compute_hide_rep_fields')
    hide_company_employee_fields = fields.Boolean(compute='_compute_hide_company_employee_fields')
    hide_company_fields = fields.Boolean(compute='_compute_hide_company_fields')

    additional_emails = fields.One2many(
        'res.partner.email',
        'partner_id',
        string='Additional Emails',
    )

    def _compute_hide_company_employee_fields(self):
        for partner in self:
            if partner.parent_id:
                partner.hide_company_employee_fields = False
            else:
                partner.hide_company_employee_fields = True

    def _compute_hide_seller_fields(self):
        for partner in self:
            if 'Seller' in partner.contact_type_ids.mapped('name'): 
                partner.hide_seller_fields = False
            else:
                partner.hide_seller_fields = True

    def _compute_hide_buyer_fields(self):
        for partner in self:
            if 'Buyer' in partner.contact_type_ids.mapped('name'):
                partner.hide_buyer_fields = False
            else:
                partner.hide_buyer_fields = True

    def _compute_hide_lien_holder_fields(self):
        for partner in self:
            if 'Lien Holder' in partner.contact_type_ids.mapped('name'):
                partner.hide_lien_holder_fields = False
            else:
                partner.hide_lien_holder_fields = True

    def _compute_contracts_as_lien_holder(self):
        for partner in self:
            if not isinstance(partner.id, int):
                partner.contracts_as_lien_holder = False
                continue
            contracts = self.env['consignment.contract'].search(['|',('lien_holder_id','=',partner.id),('lien_holder_id','child_of',partner.id)])
            if contracts:
                partner.contracts_as_lien_holder = contracts
            else:
                partner.contracts_as_lien_holder = False

    def _compute_contracts_as_buyer(self):
        for partner in self:
            if not isinstance(partner.id, int):
                partner.contracts_as_buyer = False
                continue
            contracts = self.env['consignment.contract'].search(['|',('buyer_id','=',partner.id),('buyer_id','child_of',partner.id)])
            if contracts:
                partner.contracts_as_buyer = contracts
            else:
                partner.contracts_as_buyer = False

    def _compute_contracts_as_rep(self):
        for partner in self:
            if not isinstance(partner.id, int):
                partner.contracts_as_rep = False
                continue
            contracts = self.env['res.rep'].search([('contract_id','!=',False),'|',('rep_id','=',partner.id),('rep_id','child_of',partner.id)]).mapped('contract_id')
            if contracts:
                partner.contracts_as_rep = contracts
            else:
                partner.contracts_as_rep = False

    def _compute_deliveries_as_rep(self):
        for partner in self:
            if not isinstance(partner.id, int):
                partner.deliveries_as_rep = self.env['consignment.delivery']
                continue
            deliveries = self.env['res.rep'].search([('delivery_id','!=',False),'|',('rep_id','=',partner.id),('rep_id','child_of',partner.id)]).mapped('delivery_id')
            partner.deliveries_as_rep = deliveries or self.env['consignment.delivery']

    def _compute_hide_rep_fields(self):
        for partner in self:
            if 'Rep' in partner.contact_type_ids.mapped('name'):
                partner.hide_rep_fields = False
            else:
                partner.hide_rep_fields = True

    def _compute_hide_company_fields(self):
        for partner in self:
            if partner.company_type == 'company':
                partner.hide_company_fields = False
            else:
                partner.hide_company_fields = True

    @api.onchange('verified_buyer')
    def _onchange_verified_buyer(self):
        if self.verified_buyer:
            self.verified_date = fields.Date.today()
        else:
            self.verified_date = False

    @api.onchange('master_agreement_file', 'seller_master_agreement_file')
    def _onchange_master_agreement_files(self):
        if self.master_agreement_file or self.seller_master_agreement_file:
            self.has_master_agreement = True
        else:
            self.has_master_agreement = False

    # --- Computes ------------------------------------------------------------

    def _get_sale_type_ytd_groups(self, partner):
        first_day_of_year = fields.Date.today().replace(month=1, day=1)
        groups = defaultdict(lambda: {'sold': 0.0, 'delivered': 0.0})
        # Skip when partner is new (NewId); search('child_of', id) requires a stored int
        if not partner or not isinstance(partner.id, int):
            return groups

        partner_ids = self.env['res.partner'].search([('id', 'child_of', partner.id)]).ids

        ytd_contracts = self._contracts_for_totals(partner, date_from=first_day_of_year)
        for contract in ytd_contracts:
            sale_type_name = contract.sale_type.display_name if getattr(contract, 'sale_type', False) else 'No Type'
            reps = contract.rep_ids.filtered(lambda r: r.active and r.rep_id.id in partner_ids)
            if not reps:
                continue
            groups[sale_type_name]['sold'] += sum(reps.mapped('rep_sold_head_count'))

        delivered_reps = self.env['res.rep'].search([
            ('active', '=', True),
            '|', ('rep_id', '=', partner.id), ('rep_id', 'child_of', partner.id),
            ('delivery_id', '!=', False),
            ('delivery_id.state', '=', 'delivered'),
            ('delivery_id.delivery_date', '>=', first_day_of_year),
        ])
        for rep in delivered_reps:
            sale_type_name = rep.contract_id.sale_type.display_name if getattr(rep.contract_id, 'sale_type', False) else 'No Type'
            groups[sale_type_name]['delivered'] += rep.rep_delivered_head_count

        return groups

    @api.depends('child_ids', 'company_id')
    def _compute_sale_type_stats_html(self):
        for partner in self:
            groups = self._get_sale_type_ytd_groups(partner)

            rows = [(name, data['sold'], data['delivered']) for name, data in groups.items()]
            rows.sort(key=lambda r: r[0].lower())
            html = [
                '<table class="o_list_view table table-sm table-striped"><thead><tr>',
                '<th>Type</th><th class="text-right">Head Sold</th><th class="text-right">Head Delivered</th>',
                '</tr></thead><tbody>'
            ]
            total_sold = 0.0
            total_delivered = 0.0
            for name, sold_count, delivered_count in rows:
                total_sold += sold_count
                total_delivered += delivered_count
                html += [f'<tr><td>{name}</td><td class="text-right">{sold_count}</td><td class="text-right">{delivered_count}</td></tr>']
            html += [f'<tr><td><b>Total</b></td><td class="text-right"><b>{total_sold}</b></td><td class="text-right"><b>{total_delivered}</b></td></tr>']
            html += ['</tbody></table>']
            partner.sale_type_stats_html = ''.join(html)

    def _compute_sale_type_stats(self):
        for partner in self:
            json_data = {
                'ytd_head_sold': {
                    'value': partner.ytd_head_sold,
                    'label': 'YTD Head Sold',
                    'percentage_change': None,
                    'is_increase': None,
                },
                'ytd_head_delivered': {
                    'value': partner.ytd_head_delivered,
                    'label': 'YTD Head Delivered',
                    'percentage_change': None,
                    'is_increase': None,
                },
            }

            groups = self._get_sale_type_ytd_groups(partner)

            for name in sorted(groups.keys(), key=lambda n: n.lower()):
                data = groups[name]
                name_key = name.lower().replace(' ', '_')
                json_data[name_key] = {
                    'value': data['delivered'],
                    'sold_value': data['sold'],
                    'label': name,
                    'percentage_change': None,
                    'is_increase': None,
                }

            partner.sale_type_stats = json_data

    def _contracts_for_totals(self, partner, date_from=None, date_to=None):
        """Return consignment.contract records linked to the given partner via res.rep.

        - Includes partner and its children (rep hierarchy) using child_of domain
        - Filters to states relevant to sales totals
        - Optionally filters by sold_date >= date_from and <= date_to
        """
        self.ensure_one()
        if not partner or not isinstance(partner.id, int):
            return self.env['consignment.contract']
        rep_records = self.env['res.rep'].search([
            '|', ('rep_id', '=', partner.id), ('rep_id', 'child_of', partner.id),
            ('contract_id', '!=', False),
            ('active', '=', True),
        ])
        contracts = rep_records.mapped('contract_id')
        if not contracts:
            return self.env['consignment.contract']

        contracts = contracts.filtered(lambda c: (c.state or '') in ['sold', 'delivery_ready', 'delivered'])

        if date_from:
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date >= date_from)
        if date_to:
            contracts = contracts.filtered(lambda c: c.sold_date and c.sold_date <= date_to)

        return contracts

    def get_upcoming_deliveries_json(self):
        """Return upcoming deliveries for this partner as JSON data."""
        self.ensure_one()
        if not isinstance(self.id, int):
            return []
        today = fields.Date.today()
        deliveries = self.env['consignment.delivery'].search([
            ('rep_id', '=', self.id),
            ('state', '=', ['draft','confirmed']),
            ('delivery_date', '>=', today)
        ], order='delivery_date asc', limit=10)

        upcoming_deliveries = []
        for delivery in deliveries:
            upcoming_deliveries.append({
                'id': delivery.id,
                'lot_number': delivery.lot_number,
                'delivery_date': delivery.delivery_date.isoformat(),
                'total_head_count': sum(delivery.line_ids.mapped('head_count')),
                'state': delivery.state,
            })
        return upcoming_deliveries
    
    @api.depends('contracts_as_rep')  
    def get_ytd_head_sold(self):
        first_day_of_year = fields.Date.today().replace(month=1, day=1)
        for partner in self:
            if not isinstance(partner.id, int):
                partner.ytd_head_sold = 0.0
                continue
            rep_records = self.env['res.rep'].search([
                '|', ('rep_id', '=', partner.id), ('rep_id', 'child_of', partner.id),
                ('contract_id', '!=', False),
                ('contract_id.state', 'in', ['sold', 'delivery_ready', 'delivered']),
            ])
            if first_day_of_year:
                rep_records = rep_records.filtered(
                    lambda r: r.contract_id.sold_date 
                    and r.contract_id.sold_date >= first_day_of_year
                )
            partner.ytd_head_sold = sum(rep_records.mapped('rep_sold_head_count'))

    @api.depends('deliveries_as_rep')
    def get_ytd_head_delivered(self):
        first_day_of_year = fields.Date.today().replace(month=1, day=1)
        for partner in self:
            if not isinstance(partner.id, int):
                partner.ytd_head_delivered = 0.0
                continue
            rep_records = self.env['res.rep'].search([
                '|', ('rep_id', '=', partner.id), ('rep_id', 'child_of', partner.id),
                ('delivery_id', '!=', False),
                ('delivery_id.state', '=', 'delivered'),
            ])
            if first_day_of_year:
                rep_records = rep_records.filtered(
                    lambda r: r.delivery_id.delivery_date 
                    and r.delivery_id.delivery_date >= first_day_of_year
                )
            partner.ytd_head_delivered = sum(rep_records.mapped('rep_delivered_head_count'))

    @api.depends('contracts_as_rep')  
    def get_ltd_head_sold(self):
        for partner in self:
            if not isinstance(partner.id, int):
                partner.ltd_head_sold = 0.0
                continue
            rep_records = self.env['res.rep'].search([
                '|', ('rep_id', '=', partner.id), ('rep_id', 'child_of', partner.id),
                ('contract_id', '!=', False),
                ('contract_id.state', 'in', ['sold', 'delivery_ready', 'delivered']),
            ])
            
            partner.ltd_head_sold = sum(rep_records.mapped('rep_sold_head_count'))

    @api.depends('deliveries_as_rep')
    def get_ltd_head_delivered(self):
        for partner in self:
            rep_records = self.env['res.rep'].search([
                '|', ('rep_id', '=', partner.id), ('rep_id', 'child_of', partner.id),
                ('delivery_id', '!=', False),
                ('delivery_id.state', '=', 'delivered'),
            ])
            partner.ltd_head_delivered = sum(rep_records.mapped('rep_delivered_head_count'))


    @api.depends('name', 'parent_name', 'buyer_name_display_preference')
    def _compute_buyer_name(self):
        for partner in self:
            if partner.buyer_name_display_preference == 'use_name':
                partner.buyer_name = partner.name
            elif partner.buyer_name_display_preference == 'use_company':
                partner.buyer_name = partner.parent_name
            elif partner.buyer_name_display_preference == 'use_both':
                partner.buyer_name = f"{partner.parent_name}, {partner.name}"
            else:
                partner.buyer_name = ''

    @api.depends('name', 'parent_name', 'rep_name_display_preference')
    def _compute_rep_name(self):
        for partner in self:
            if partner.rep_name_display_preference == 'use_name':
                partner.rep_name = partner.name
            elif partner.rep_name_display_preference == 'use_company':
                partner.rep_name = partner.parent_name
            elif partner.rep_name_display_preference == 'use_both':
                partner.rep_name = f"{partner.parent_name}, {partner.name}"
            else:
                partner.rep_name = ''

    @api.depends('name', 'parent_name', 'seller_name_display_preference')
    def _compute_seller_name(self):
        for partner in self:
            if partner.seller_name_display_preference == 'use_name':
                partner.seller_name = partner.name
            elif partner.seller_name_display_preference == 'use_company':
                partner.seller_name = partner.parent_name
            elif partner.seller_name_display_preference == 'use_both':
                partner.seller_name = f"{partner.parent_name}, {partner.name}"
            else:
                partner.seller_name = ''

    @api.model
    def _search_display_name(self, operator, value):
        """Extend display name search with buyer number and buyer context filtering."""
        from odoo.osv.expression import OR, AND
        domain = super()._search_display_name(operator, value)
        # Add buyer number search when a value is provided
        if value and operator.endswith('like'):
            domain = OR([domain, [('buyer_number_ids.name', operator, value)]])
        # Filter by buyer contact type when buyer_search context is set
        if self.env.context.get('buyer_search'):
            domain = AND([domain, [('contact_type_ids.name', '=', 'Buyer')]])
        return domain

    @api.depends('street', 'street2', 'city', 'state_id', 'zip', 'country_id')
    def _compute_contact_address_inline_clean(self):
        for partner in self:
            address_parts = []
            if partner.street:
                address_parts.append(partner.street)
            if partner.street2:
                address_parts.append(partner.street2)
            city_state_zip = ", ".join(filter(None, [partner.city, partner.state_id.code, partner.zip]))
            if city_state_zip:
                address_parts.append(city_state_zip)
            
            # Join parts with commas to match the inline style
            partner.contact_address_inline_clean = ", ".join(address_parts)

    def ensure_payment_address(self):
        """
        For each partner that has no child contact with type='payment', create one
        from the partner's address/contact info and set it as default_payment_info_id.
        Idempotent: skips partners that already have a payment address.
        """
        for partner in self:
            if not partner.exists():
                continue
            payment_children = partner.child_ids.filtered(lambda p: p.type == 'payment')
            if payment_children:
                if not partner.default_payment_info_id:
                    partner.default_payment_info_id = payment_children[0].id
                continue
            vals = {
                'parent_id': partner.id,
                'type': 'payment',
                'company_id': partner.company_id.id,
                'name': partner.name or _('Payment Address'),
                'street': partner.street,
                'street2': partner.street2,
                'city': partner.city,
                'state_id': partner.state_id.id if partner.state_id else False,
                'zip': partner.zip,
                'country_id': partner.country_id.id if partner.country_id else False,
                'phone': partner.phone,
                'email': partner.email,
            }
            payment = self.env['res.partner'].create(vals)
            partner.default_payment_info_id = payment.id

    @api.depends('name', 'buyer_number_ids.name')
    def _compute_display_name(self):
        if self.env.context.get('buyer_search'):
            for partner in self:
                buyer_numbers = partner.buyer_number_ids.mapped('name')
                buyer_number_str = ', '.join(buyer_numbers) if buyer_numbers else ''
                partner.display_name = f"{buyer_number_str} - {partner.name}" if buyer_number_str else partner.name
        else:
            super()._compute_display_name()

    # Contact type name -> user group xmlid (Commercial Cattle roles)
    CONTACT_TYPE_TO_GROUP = {
        'Buyer': 'liveag_consignment.group_consignment_buyer',
        'Seller': 'liveag_consignment.group_consignment_seller',
        'Rep': 'liveag_consignment.group_consignment_rep',
        'Administrator': 'liveag_consignment.group_consignment_manager',
        'Admin': 'liveag_consignment.group_consignment_manager',
    }

    def _sync_partner_contact_types_to_user_groups(self, partner):
        """Assign / unassign Commercial Cattle groups on the partner's user(s)
        so they match partner.contact_type_ids (Buyer, Seller, Rep, Admin/Administrator)."""
        if not partner.user_ids:
            return
        contact_types = set(partner.contact_type_ids.mapped('name'))
        for user in partner.user_ids:
            for type_name, group_xml_id in self.CONTACT_TYPE_TO_GROUP.items():
                group = self.env.ref(group_xml_id).sudo()
                if type_name in contact_types:
                    user.sudo().write({'group_ids': [(4, group.id)]})
                else:
                    user.sudo().write({'group_ids': [(3, group.id)]})

    def write(self, vals):
        result = super().write(vals)
        if 'contact_type_ids' in vals:
            for partner in self:
                partner._sync_partner_contact_types_to_user_groups(partner)
        return result
