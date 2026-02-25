import json
import datetime
import logging
from typing import Dict, Any, List, Optional

from odoo import http
from odoo.http import request

from odoo.addons.liveag_muk_rest.tools.http import build_route
from odoo.addons.liveag_muk_rest import core
from odoo.addons.liveag_api.controllers.liveag import LiveAgController

_logger = logging.getLogger(__name__)


class LiveAgAnalysisItemController(LiveAgController):

    def _bool_from_param(self, value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None
        v = str(value).strip().lower()
        if v in ("true", "1", "t", "yes", "y"):
            return True
        if v in ("false", "0", "f", "no", "n"):
            return False
        return None

    # -------------------------------
    # Select Values / Lookups
    # -------------------------------
    @core.http.rest_route(
        routes=build_route(['/select-values/states', '/custom/select-values/states']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Lookups'],
            summary='List states for a country',
            description='Return states for the given country_id (default US = 233).',
        ),
    )
    def get_states(self, **kw):
        try:
            country_id = int(request.params.get('country_id', 233))
            country = request.env['res.country'].browse(country_id)
            if not country.exists():
                return request.make_json_response({'error': 'Invalid country ID'}, status=400)
            states = request.env['res.country.state'].search([('country_id', '=', country.id)])
            result = [{
                'id': st.id,
                'name': st.name,
                'abv': st.code,
                'region': getattr(st, 'region', None),
                'country_id': st.country_id.id
            } for st in states]
            return request.make_json_response(result)
        except Exception as e:
            _logger.exception("Error getting states")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/select-values/countries', '/custom/select-values/countries']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Lookups'],
            summary='List supported countries',
            description='Return US, CA, MX with US sorted first.',
        ),
    )
    def get_countries(self, **kw):
        try:
            countries = request.env['res.country'].search([('code', 'in', ['US', 'CA', 'MX'])])
            sorted_countries = sorted(countries, key=lambda c: (c.code != 'US', c.name))
            result = [{'id': c.id, 'name': c.name, 'abv': c.code} for c in sorted_countries]
            return request.make_json_response(result)
        except Exception as e:
            _logger.exception("Error getting countries")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/slide_types', '/custom/slide_types']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Lookups'],
            summary='List slide types',
            description='Return slide types filtered by sell_by_head (true/false).',
        ),
    )
    def get_slide_types(self, **kw):
        try:
            sell_by_head_raw = request.params.get('sell_by_head')
            sell_by_head = self._bool_from_param(sell_by_head_raw)
            if sell_by_head is None:
                return request.make_json_response({'error': 'Invalid sell_by_head'}, status=400)

            slide_types = request.env['slide.type'].search([('sell_by_head', '=', sell_by_head)])
            result = [{
                'id': st.id,
                'name': st.name,
                'sell_by_head': st.sell_by_head,
                'above': st.above,
                'under': st.under
            } for st in slide_types]
            return request.make_json_response(result)
        except Exception as e:
            _logger.exception("Error getting slide types")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/consignment/select-values', '/custom/consignment/select-values']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Lookups'],
            summary='List static select values',
            description='Return static select values per category or all when not specified.',
        ),
    )
    def get_static_values(self, **kw):
        try:
            category_param = request.params.get('category')
            available = {
                'saleType': 'sale.type',
                'contractType': 'contract.type',
                'kind': 'kind.list',
                'slideType': 'slide.type',
                'frameSize': 'frame.size',
                'flesh': 'flesh.type',
                'weightVariance': 'weight.variance',
                'horns': 'horns.list',
                'implant': 'implanted.list',
                'castration': 'castration.list',
                'bangVacc': 'bangs.vaccinated',
                'origin': 'origin.list',
                'states': 'res.country.state',
                'countries': 'res.country',
                'vaccPrograms': 'vac.program',
                'specialSections': 'special.section',
                'geneticMerit': 'genetic.merit',
                'valueNutrition': 'van.program',
                'premiumGenetics': 'premium.genetics.program',
                'sourceAgeVerification': 'third.party.age',
                'gap': 'gap.program',
                'locationType': 'location.type',
                'whosOption': 'whose.option',
                'weightStop': 'weight.stop',
            }
            categories: List[str] = list(available.keys()) if not category_param else [
                c for c in category_param.split(',') if c in available
            ]
            static_fields: Dict[str, Any] = {}

            def simple(model_name: str):
                return [{'id': rec.id, 'name': rec.name} for rec in request.env[model_name].search([])]

            for cat in categories:
                if cat == 'states':
                    us = request.env['res.country'].search([('code', '=', 'US')], limit=1)
                    states = request.env['res.country.state'].search([('country_id', '=', us.id)])
                    static_fields['states'] = [{
                        'id': st.id,
                        'name': st.name,
                        'abv': st.code,
                        'region': getattr(st, 'region', None)
                    } for st in states]
                elif cat == 'countries':
                    countries = request.env['res.country'].search([('code', 'in', ['US', 'CA', 'MX'])])
                    sorted_countries = sorted(countries, key=lambda c: c.code != 'US')
                    static_fields['countries'] = [{'id': c.id, 'name': c.name, 'abv': c.code} for c in sorted_countries]
                else:
                    static_fields[cat] = simple(available[cat])

            return request.make_json_response(static_fields)
        except Exception as e:
            _logger.exception("Error getting static values")
            return request.make_json_response({'error': str(e)}, status=500)

    # -------------------------------
    # Contacts
    # -------------------------------
    @core.http.rest_route(
        routes=build_route(['/contacts/sellers', '/custom/contacts/sellers']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='List Sellers',
            description='Return partners with contact type Seller.',
        ),
    )
    def list_sellers(self, **kw):
        sellers = []
        try:
            seller_ct = request.env['res.contact.type'].search([('name', '=', 'Seller')])
            if seller_ct:
                contacts = request.env['res.partner'].search([('contact_type_ids', 'in', seller_ct.ids)])
                for c in contacts:
                    sellers.append({
                        'id': c.id,
                        'name': c.name,
                        'email': c.email,
                        'phone': c.phone,
                        'street': c.street,
                        'street2': c.street2,
                        'city': c.city,
                        'state': c.state_id.code if c.state_id else None,
                        'zip': c.zip,
                        'country': c.country_id.code if c.country_id else None,
                    })
            return request.make_json_response(sellers)
        except Exception as e:
            _logger.exception("Error listing sellers")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/contacts/reps', '/custom/contacts/reps']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='List Reps',
            description='Return partners with contact type Rep.',
        ),
    )
    def list_reps(self, **kw):
        reps = []
        try:
            rep_ct = request.env['res.contact.type'].search([('name', '=', 'Rep')])
            if rep_ct:
                contacts = request.env['res.partner'].search([('contact_type_ids', 'in', rep_ct.ids)])
                for c in contacts:
                    reps.append({
                        'id': c.id,
                        'name': c.name,
                        'email': c.email,
                        'phone': c.phone,
                        'street': c.street,
                        'street2': c.street2,
                        'city': c.city,
                        'state': c.state_id.code if c.state_id else None,
                        'zip': c.zip,
                        'country': c.country_id.code if c.country_id else None,
                    })
            return request.make_json_response(reps)
        except Exception as e:
            _logger.exception("Error listing reps")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/contacts/lienholders', '/custom/contacts/lienholders']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='List Lien Holders',
            description='Return partners with contact type Lien Holder.',
        ),
    )
    def list_lienholders(self, **kw):
        data = []
        try:
            ct = request.env['res.contact.type'].search([('name', '=', 'Lien Holder')])
            if ct:
                contacts = request.env['res.partner'].search([('contact_type_ids', 'in', ct.ids)])
                for c in contacts:
                    data.append({
                        'id': c.id,
                        'name': c.name,
                        'city': c.city,
                        'state': c.state_id.code if c.state_id else None,
                        'zip': c.zip,
                        'country': c.country_id.code if c.country_id else None,
                    })
            return request.make_json_response(data)
        except Exception as e:
            _logger.exception("Error listing lien holders")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/contacts/sellers/lienholders', '/custom/contacts/sellers/lienholders']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Seller Lien Holders',
            description='Return lien holders linked to a seller (seller_id).',
        ),
    )
    def seller_lienholders(self, **kw):
        try:
            seller_id = request.params.get('seller_id')
            seller = request.env['res.partner'].browse(int(seller_id)) if seller_id else None
            if not seller or not seller.exists():
                return request.make_json_response({'error': 'Seller not found'}, status=404)
            out = []
            for lh in seller.lien_holder_ids:
                out.append({
                    'id': lh.id,
                    'name': lh.name,
                    'city': lh.city,
                    'state': lh.state_id.code if lh.state_id else None,
                    'zip': lh.zip,
                    'country': lh.country_id.code if lh.country_id else None,
                    'default': lh.id == seller.default_lien_holder_id.id,
                })
            return request.make_json_response(out)
        except Exception as e:
            _logger.exception("Error getting seller lien holders")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/contacts/sellers/payment_info', '/custom/contacts/sellers/payment_info']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Seller Payment Info',
            description='Return payment info child contacts for a seller (seller_id).',
        ),
    )
    def seller_payment_info(self, **kw):
        try:
            seller_id = request.params.get('seller_id')
            seller = request.env['res.partner'].browse(int(seller_id)) if seller_id else None
            if not seller or not seller.exists():
                return request.make_json_response({'error': 'Seller not found'}, status=404)
            out = []
            for pi in seller.child_ids.filtered(lambda p: p.type == 'payment'):
                out.append({
                    'id': pi.id,
                    'name': pi.name,
                    'street': pi.street,
                    'street2': pi.street2,
                    'city': pi.city,
                    'state': pi.state_id.code if pi.state_id else None,
                    'zip': pi.zip,
                    'country': pi.country_id.code if pi.country_id else None,
                    'default': pi.id == seller.default_payment_info_id.id,
                })
            return request.make_json_response(out)
        except Exception as e:
            _logger.exception("Error getting seller payment info")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/contacts/sellers/seller', '/custom/contacts/sellers/seller']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Seller Details',
            description='Return seller details including default lien holder and payment info.',
        ),
    )
    def seller_info(self, **kw):
        try:
            seller_id = request.params.get('seller_id')
            seller_ct = request.env['res.contact.type'].search([('name', '=', 'Seller')])
            contact = request.env['res.partner'].search([
                ('contact_type_ids', 'in', seller_ct.ids),
                ('id', '=', int(seller_id or 0))
            ], limit=1)
            if not contact:
                return request.make_json_response({'error': 'Seller not found'}, status=404)
            default_lh = None
            if contact.default_lien_holder_id:
                lh = contact.default_lien_holder_id
                default_lh = {
                    'id': lh.id,
                    'name': lh.name,
                    'city': lh.city,
                    'state': lh.state_id.code if lh.state_id else None,
                    'zip': lh.zip,
                    'country': lh.country_id.code if lh.country_id else None,
                }
            default_pi = None
            if contact.default_payment_info_id:
                pi = contact.default_payment_info_id
                default_pi = {
                    'id': pi.id,
                    'name': pi.name,
                    'street': pi.street,
                    'street2': pi.street2,
                    'city': pi.city,
                    'state': pi.state_id.code if pi.state_id else None,
                    'zip': pi.zip,
                    'country': pi.country_id.code if pi.country_id else None,
                }
            result = {
                'id': contact.id,
                'name': contact.name,
                'email': contact.email,
                'phone': contact.phone,
                'city': contact.city,
                'state': contact.state_id.code if contact.state_id else None,
                'country': contact.country_id.code if contact.country_id else None,
                'default_lien_holder': default_lh,
                'default_payment_info': default_pi,
            }
            return request.make_json_response(result)
        except Exception as e:
            _logger.exception("Error getting seller info")
            return request.make_json_response({'error': str(e)}, status=500)

    # -------------------------------
    # Auctions
    # -------------------------------
    @core.http.rest_route(
        routes=build_route(['/auctions/upcoming', '/custom/auctions/upcoming']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Auctions'],
            summary='Upcoming Auctions',
            description='Return upcoming auctions; filter by type (sale.type id).',
        ),
    )
    def get_upcoming_auctions(self, **kw):
        try:
            type_param = request.params.get('type')
            lax = request.env['sale.type'].search([('name', '=', 'LiveAg Xchange')], limit=1)
            pt = request.env['sale.type'].search([('name', '=', 'Private Treaty')], limit=1)
            current = datetime.date.today()
            domain = []
            if type_param:
                type_id = int(type_param)
                if type_id in [pt.id, lax.id]:
                    domain = [('sale_type', '=', type_id)]
                else:
                    domain = [('sale_date_begin', '>=', current), ('sale_type', '=', type_id)]
            else:
                domain = ['|', ('sale_type', '=', lax.id), '|', ('sale_type', '=', pt.id), ('sale_date_begin', '>=', current)]
            records = request.env['sale.auction'].search(domain)
            out = [{
                'id': rec.id,
                'name': rec.name,
                'auction_date': rec.sale_date_begin,
                'location': rec.location,
                'sale_type': rec.sale_type.name if rec.sale_type else None,
            } for rec in records]
            return request.make_json_response(out)
        except Exception as e:
            _logger.exception("Error getting upcoming auctions")
            return request.make_json_response({'error': str(e)}, status=500)

    # -------------------------------
    # Rep / Contacts stats
    # -------------------------------
    @core.http.rest_route(
        routes=build_route(['/contacts/stats', '/custom/contacts/stats']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Rep stats',
            description='Return sale_type_stats for a rep. Accepts rep-id or rep_id.',
        ),
    )
    def rep_stats(self, **kw):
        try:
            rep_id_param = request.params.get('rep-id') or request.params.get('rep_id')
            if not rep_id_param:
                return request.make_json_response({'error': 'Missing rep-id'}, status=400)
            rep = request.env['res.partner'].browse(int(rep_id_param))
            if not rep.exists():
                return request.make_json_response({'error': 'Rep not found'}, status=404)
            return request.make_json_response(rep.sale_type_stats or {})
        except Exception as e:
            _logger.exception("Error getting rep stats")
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route(['/contacts/upcoming_deliveries', '/custom/contacts/upcoming_deliveries']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Rep upcoming deliveries',
            description='Return upcoming deliveries for a rep. Accepts rep-id or rep_id.',
        ),
    )
    def rep_upcoming_deliveries(self, **kw):
        try:
            rep_id_param = request.params.get('rep-id') or request.params.get('rep_id')
            if not rep_id_param:
                return request.make_json_response({'error': 'Missing rep-id'}, status=400)
            rep = request.env['res.partner'].browse(int(rep_id_param))
            if not rep.exists():
                return request.make_json_response({'error': 'Rep not found'}, status=404)
            data = rep.get_upcoming_deliveries_json()
            return request.make_json_response(data if data is not None else [])
        except Exception as e:
            _logger.exception("Error getting rep upcoming deliveries")
            return request.make_json_response({'error': str(e)}, status=500)

    # -------------------------------
    # Contracts
    # -------------------------------
    @core.http.rest_route(
        routes=build_route(['/contracts/messages', '/custom/contracts/messages']),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contracts'],
            summary='Contract Messages',
            description='Return messages and tracking values for a given contract_id.',
        ),
    )
    def get_contract_messages(self, **kw):
        try:
            contract_id = int(request.params.get('contract_id', 0))
            contract = request.env['consignment.contract'].browse(contract_id)
            if not contract.exists():
                return request.make_json_response({'error': 'Contract not found'}, status=404)
            messages: List[Dict[str, Any]] = []
            for msg in contract.message_ids:
                data = msg.read()[0]
                tracking_ids = data.get('tracking_value_ids', [])
                if tracking_ids:
                    tracking_values = request.env['mail.tracking.value'].browse(tracking_ids).read()
                    data['tracking_values'] = tracking_values
                messages.append(data)
            return request.make_json_response(messages)
        except Exception as e:
            _logger.exception("Error getting contract messages")
            return request.make_json_response({'error': str(e)}, status=500)

