import base64
import logging

from odoo import http, exceptions
from odoo.http import request
from odoo.tools import misc, replace_exceptions

from odoo.addons.web.controllers import main
from odoo.addons.liveag_muk_rest.tools.http import build_route
from odoo.addons.liveag_muk_rest import core

from odoo.addons.liveag_api.tools.liveag import (
    serialize_contract_preview,
    serialize_contract_detailed,
    serialize_contract_editable,
    serialize_reps_for_contract,
    serialize_contact_basic_info,
    serialize_contact_buyer,
    serialize_contact_seller,
    serialize_contact_rep,
)

import json
import datetime

_logger = logging.getLogger(__name__)

DIRECTION_LIST = [
    ('N', "N"),
    ('W', "W"),
    ('E', "E"),
    ('S', "S"),
    ('NE', "NE"),
    ('NW', "NW"),
    ('SE', "SE"),
    ('SW', "SW"),
]

def get_user(user_id):
    if not user_id:
        return {'error': 'Missing Clerk user ID', 'isAuthorized': False, 'X-User-Id': user_id}

    user = request.env['res.partner'].search([('clerk_user_id', '=', user_id)], limit=1)

    if not user:
        return {'isAuthorized': False, 'error': 'User not found', 'X-User-Id': user_id}

    user_roles = [role.name.lower() for role in user.contact_type_ids]

    response = {**user.read()[0], 'isAuthorized': True, 'roles': user_roles, 'X-User-Id': user_id}
    
    return response

class LiveAgController(http.Controller):
    
    def _get_filter_from_params(self):
        """Extract filter parameters from request.
        
        Returns:
            Dictionary of filter parameters
        """
        filters = {}
        
        # 1. kind_type (array of strings)
        kind_type = request.params.get('kind_type')
        if kind_type:
            try:
                filters['kind_type'] = json.loads(kind_type)
            except (json.JSONDecodeError, TypeError):
                _logger.warning("Invalid kind_type parameter: %s", kind_type)
        
        # 2. seller_id (number)
        seller_id = request.params.get('seller_id')
        if seller_id:
            try:
                filters['seller_id'] = int(seller_id)
            except (ValueError, TypeError):
                _logger.warning("Invalid seller_id parameter: %s", seller_id)
        
        # 3. representative_id (number)
        representative_id = request.params.get('representative_id')
        if representative_id:
            try:
                filters['representative_id'] = int(representative_id)
            except (ValueError, TypeError):
                _logger.warning("Invalid representative_id parameter: %s", representative_id)
        
        # 4. state (array of strings)
        state = request.params.get('state')
        if state:
            try:
                filters['state'] = json.loads(state)
            except (json.JSONDecodeError, TypeError):
                _logger.warning("Invalid state parameter: %s", state)
        
        # 5. delivery_date_start (ISO date)
        delivery_date_start = request.params.get('delivery_date_start')
        if delivery_date_start:
            filters['delivery_date_start'] = delivery_date_start
        
        # 6. delivery_date_end (ISO date)
        delivery_date_end = request.params.get('delivery_date_end')
        if delivery_date_end:
            filters['delivery_date_end'] = delivery_date_end
        
        # 7. weight_min (number)
        weight_min = request.params.get('weight_min')
        if weight_min:
            try:
                filters['weight_min'] = int(weight_min)
            except (ValueError, TypeError):
                _logger.warning("Invalid weight_min parameter: %s", weight_min)
        
        # 8. weight_max (number)
        weight_max = request.params.get('weight_max')
        if weight_max:
            try:
                filters['weight_max'] = int(weight_max)
            except (ValueError, TypeError):
                _logger.warning("Invalid weight_max parameter: %s", weight_max)
        
        # 9. auction_id (number)
        auction_id = request.params.get('auction_id')
        if auction_id:
            try:
                filters['auction_id'] = int(auction_id)
            except (ValueError, TypeError):
                _logger.warning("Invalid auction_id parameter: %s", auction_id)
        
        # 10. search (string)
        search = request.params.get('search')
        if search:
            filters['search'] = search

        # 11. sale_type (array of strings)
        sale_type = request.params.get('sale_type')
        if sale_type:
            try:
                filters['sale_type'] = json.loads(sale_type)
            except (json.JSONDecodeError, TypeError):
                _logger.warning("Invalid sale_type parameter: %s", sale_type)

        return filters
    
    def _apply_filters_to_domain(self, domain, filters):
        """Apply filters to domain.
        
        Args:
            domain: Base domain list
            filters: Dictionary of filter parameters
            
        Returns:
            Updated domain list with filters applied
        """
        
        # 1. kind_type filter
        if filters.get('kind_type') and isinstance(filters['kind_type'], list):
            kind_domain = ['|']
            kind_domain.append(('kind1.name', 'in', filters['kind_type']))
            kind_domain.append(('kind2.name', 'in', filters['kind_type']))
            domain.extend(kind_domain)
        
        # 2. seller_id filter
        if filters.get('seller_id'):
            domain.append(('seller_id', '=', filters['seller_id']))
        
        # 3. representative_id filter
        if filters.get('representative_id'):
            domain.append(('rep_ids.rep_id', '=', filters['representative_id']))
        
        # 4. state filter
        if filters.get('state') and isinstance(filters['state'], list):
            domain.append(('state', 'in', filters['state']))
        
        # 5. delivery_date_start filter
        if filters.get('delivery_date_start'):
            domain.append(('delivery_date_end', '>=', filters['delivery_date_start']))
        
        # 6. delivery_date_end filter
        if filters.get('delivery_date_end'):
            domain.append(('delivery_date_start', '<=', filters['delivery_date_end']))
        
        # 7. weight_min filter
        if filters.get('weight_min'):
            weight_min_domain = ['|']
            weight_min_domain.append(('weight1', '>=', filters['weight_min']))
            weight_min_domain.append(('weight2', '>=', filters['weight_min']))
            domain.extend(weight_min_domain)
        
        # 8. weight_max filter
        if filters.get('weight_max'):
            weight_max_domain = ['|']
            weight_max_domain.append(('weight1', '<=', filters['weight_max']))
            weight_max_domain.append(('weight2', '<=', filters['weight_max']))
            domain.extend(weight_max_domain)
        
        # 9. auction_id filter
        if filters.get('auction_id'):
            domain.append(('auction_id', '=', filters['auction_id']))
        
        # 10. search filter
        if filters.get('search'):
            search_domain = ['|', '|', '|']
            search_domain.append(('seller_id.name', 'ilike', filters['search']))
            search_domain.append(('contract_id', 'ilike', filters['search']))
            search_domain.append(('lot_number', 'ilike', filters['search']))
            search_domain.append(('consignment_id', 'ilike', filters['search']))
            domain.extend(search_domain)

        # 11. sale_type filter
        if filters.get('sale_type') and isinstance(filters['sale_type'], list):
            domain.append(('sale_type.name', 'in', filters['sale_type']))

        return domain

  # ---------------------------------------------------------- #
  # ------------------------------------------------------ #
  # Authorization Endpoints
  # ------------------------------------------------------ #
  # ---------------------------------------------------------- #

    @core.http.rest_route(
      routes=build_route('/authorize'),
      methods=['POST'],
      protected=True,
      docs=dict(
          tags=['Auth'],
          summary='Authorize User',
          description='Authorizes a user based on the Clerk user ID.',
      ),
    )
    def authorize_user(self, **kw):
        request_body = request.httprequest.get_data(as_text=True)
        json_data = json.loads(request_body)
        clerk_user_id = json_data['clerkUserId']

        user = get_user(clerk_user_id)
        return request.make_json_response({'user': user})

  # ---------------------------------------------------------- #
  # ------------------------------------------------------ #
  # Contacts Endpoints
  # ------------------------------------------------------ #
  # ---------------------------------------------------------- #

    # ----------------------------------------------------------
    # Clients Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
        routes=build_route('/me'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Get All Clients / Create Client',
            description='Fetches all clients or creates a new client.',
        ),
    )
    def handle_clients(self, **kw):
        """Fetch all clients or create a new client"""

        user_id = request.httprequest.headers.get('X-User-Id')
        return request.make_json_response({'user_id': user_id})
        # if not user_id:
        #     return request.make_json_response({'error': 'Missing X-User-ID header'}, status=400)

        # try:
        #     partner = request.env['res.partner'].sudo().search([
        #         ('clerk_user_id', '=', user_id)
        #     ], limit=1)
        #     if not partner:
        #         return request.make_json_response({'error': 'User not found'}, status=404)

        #     me = (serialize_contact_basic_info(contact))
            
        #     return request.make_json_response(me)
        
        # except Exception as e:
        #     return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route('/clients'),
        methods=['GET', 'POST'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Get All Clients / Create Client',
            description='Fetches all clients or creates a new client.',
        ),
    )
    def handle_clients(self, **kw):
        """Fetch all clients or create a new client"""

        if request.httprequest.method == 'GET':
            clients = []
            contact_types = request.env['res.contact.type'].search([
                '|', '|',
                ('name', 'ilike', 'Seller'),
                ('name', 'ilike', 'Rep'),
                ('name', 'ilike', 'Buyer')
            ])
            
            if contact_types:
                contacts = request.env['res.partner'].search([
                    ('contact_type_ids', 'in', contact_types.ids)
                ])
                
                for contact in contacts:
                    client = serialize_contact_basic_info(contact)
                    
                    # Check contact types properly by iterating through them
                    contact_type_names = [ct.name for ct in contact.contact_type_ids]
                    
                    if 'Buyer' in contact_type_names:
                        client.update(serialize_contact_buyer(contact))
                    if 'Seller' in contact_type_names:
                        client.update(serialize_contact_seller(contact))
                    if 'Rep' in contact_type_names:
                        client.update(serialize_contact_rep(contact))
                        
                    clients.append(client)
            
            return request.make_json_response(clients)
            
        elif request.httprequest.method == 'POST':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                json_data = json.loads(request_body)
                
                contactInfo = json_data.get('contactInfo')
                paymentInfo = json_data.get('paymentInfo', {})  # Optional
                lienHolderInfo = json_data.get('lienHolderInfo', {})  # Optional
                bankInfo = json_data.get('bankInfo', {})  # Optional

                if not contactInfo:
                    return request.make_json_response({'error': 'Missing contactInfo in request body'}, 400)
                
                contact_type_names = []
                for type_id in contactInfo.get('contact_type_ids', []):
                    contact_type = request.env['res.contact.type'].browse(type_id)
                    if contact_type.exists():
                        contact_type_names.append(contact_type.name.lower())
                
                primary_contact = request.env['res.partner'].create(contactInfo)

                new_payment_info = None
                if paymentInfo:
                    paymentInfo['type'] = 'payment'
                    new_payment_info = request.env['res.partner'].create(paymentInfo)
                    primary_contact.write({
                        'child_ids': [(4, new_payment_info.id)],
                        'default_payment_info_id': new_payment_info.id
                    })

                new_bank_info = None
                if bankInfo:
                    bankInfo['type'] = 'bank'
                    new_bank_info = request.env['res.partner'].create(bankInfo)
                    primary_contact.write({
                        'child_ids': [(4, new_bank_info.id)]
                    })

                default_lien_holder_id = None
                if lienHolderInfo:
                    lien_holder_contact_type = request.env['res.contact.type'].search([('name', '=', 'Lien Holder')], limit=1)
                    lienHolderInfo['contact_type_ids'] = [lien_holder_contact_type.id]  # Ensure correct contact type for lien holders
                    new_lien_holder = request.env['res.partner'].create(lienHolderInfo)
                    default_lien_holder_id = new_lien_holder.id
                    primary_contact.write({
                        'default_lien_holder_id': default_lien_holder_id
                    })

                lien_holder_ids = contactInfo.get('lien_holder_ids', [])
                if lien_holder_ids:
                    primary_contact.write({
                        'default_lien_holder_id': lien_holder_ids[0],
                        'child_ids': [(4, lien_id) for lien_id in lien_holder_ids]  # Associate existing lien holders
                    })

                result = primary_contact.read()[0]

            except Exception as e:
                result = {'error': f"Error when creating or updating: {str(e)}"}

            return request.make_json_response(result)

        return request.make_json_response({'error': 'Method not allowed'}, status=405)

    @core.http.rest_route(
        routes=build_route('/clients/<int:client_id>'),
        methods=['GET', 'PUT'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Get or Update client by ID',
            description='Fetch a client by their ID or update their information.',
        ),
    )
    def get_or_update_client_by_id(self, client_id, **kw):
        if request.httprequest.method == 'GET':
            try:
                client = request.env['res.partner'].search([('id', '=', client_id)], limit=1)
                if client:
                    # default_reps = None
                    # if client.rep_ids:
                    #     default_reps = []
                    #     for rep in client.rep_ids:
                    #         default_reps.append({
                    #             'percentage_commission': rep.percentage_commission,
                    #             'id': rep.rep_id.id,
                    #         })

                    # default_lien_holder = None
                    # if client.default_lien_holder_id:
                    #     lien_holder = client.default_lien_holder_id
                    #     default_lien_holder = {
                    #         'id': lien_holder.id,
                    #         'name': lien_holder.name,
                    #         'city': lien_holder.city,
                    #         'state': lien_holder.state_id.code if lien_holder.state_id else None,
                    #         'zip': lien_holder.zip,
                    #         'country': lien_holder.country_id.code if lien_holder.country_id else None,
                    #     }

                    # default_payment_info = None
                    # if client.default_payment_info_id:
                    #     payment_info = client.default_payment_info_id
                    #     default_payment_info = {
                    #         'id': payment_info.id,
                    #         'name': payment_info.name,
                    #         'street': payment_info.street,
                    #         'street2': payment_info.street2 if payment_info.street2 else None,
                    #         'city': payment_info.city,
                    #         'state': payment_info.state_id.code if payment_info.state_id else None,
                    #         'zip': payment_info.zip,
                    #         'country': payment_info.country_id.code if payment_info.country_id else None,
                    #     }

                    # result = {
                    #     'id': client.id,
                    #     'company_type': client.company_type,
                    #     'company': client.commercial_company_name or None,
                    #     'contact_name': client.contact_name or None,
                    #     'roles': [role.name.lower() for role in client.contact_type_ids],
                    #     'buyer_numbers': [buyer_number.name for buyer_number in client.buyer_number_ids] or None,
                    #     'name': client.name or None,
                    #     'email': client.email or None,
                    #     'phone': client.phone or None,
                    #     'mobile': client.mobile or None,
                    #     'street': client.street or None,
                    #     'city': client.city or None,
                    #     'state': client.state_id.code if client.state_id else None,
                    #     'country': client.country_id.name if client.country_id else None,
                    #     'zip': client.zip or None,
                    #     'default_lien_holder': default_lien_holder or None,
                    #     'affidavit_verified': client.affidavit_verified or None,
                    #     'has_master_agreement': client.has_master_agreement or None,
                    #     'default_payment_info': default_payment_info or None,
                    #     'reps': default_reps
                    # }
                    client_result = serialize_contact_basic_info(client)
                    
                    # Check contact types properly by iterating through them
                    contact_type_names = [ct.name.lower() for ct in client.contact_type_ids]
                    
                    if 'buyer' in contact_type_names:
                        client_result.update(serialize_contact_buyer(client))
                    if 'seller' in contact_type_names:
                        client_result.update(serialize_contact_seller(client))
                    if 'rep' in contact_type_names:
                        client_result.update(serialize_contact_rep(client))
                    return request.make_json_response(client_result)
                    # return request.make_json_response(client.read()[0])
                return request.make_json_response({'error': 'Client not found'}, status=404)
            except Exception as e:
                return request.make_json_response({'error': f"Unexpected error: {str(e)}"}, status=500)

        elif request.httprequest.method == 'PUT':
            try:
                data = json.loads(request.httprequest.get_data(as_text=True))
                client = request.env['res.partner'].search([
                    ('id', '=', client_id),
                ], limit=1)

                if not client:
                    return request.make_json_response({'error': 'Client not found'}, status=404)

                allowed_fields = ['name', 'email', 'phone', 'street', 'city', 'state_id', 'country_id', 'zip', 'default_lien_holder_id', 'default_payment_info_id']
                update_vals = {key: data[key] for key in allowed_fields if key in data}
                client.write(update_vals)

                return request.make_json_response({'message': 'Client updated successfully', 'client': client.read()[0]})

            except Exception as e:
                return request.make_json_response({'error': f'Error updating seller: {str(e)}'}, status=500)


    # ----------------------------------------------------------
    # Sellers Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
      routes=build_route('/sellers'),
      methods=['GET', 'POST'],
      protected=True,
      docs=dict(
          tags=['Contacts'],
          summary='Get All Sellers / Create Seller',
          description='Fetches all sellers or creates a new seller.',
      ),
    )
    def handle_sellers(self, **kw):
        """Fetch all sellers or create a new seller"""
        
        if request.httprequest.method == 'GET':
            sellers = []
            seller_contact_type = request.env['res.contact.type'].search([('name', '=', 'Seller')])
            
            if seller_contact_type:
                contacts = request.env['res.partner'].search([('contact_type_ids', 'in', seller_contact_type.ids)])
                
                for contact in contacts:
                    sellers.append({
                        'id': contact.id,
                        'name': contact.name,
                        'email': contact.email,
                        'phone': contact.phone,
                        'address': {
                            'street': contact.street,
                            'street2': contact.street2 if contact.street2 else None,
                            'city': contact.city,
                            'state': contact.state_id.code if contact.state_id else None,
                            'country': contact.country_id.name if contact.country_id else None,
                            'zip': contact.zip,
                        }
                    })
            return request.make_json_response(sellers)

        elif request.httprequest.method == 'POST':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                json_data = json.loads(request_body)

                sellerInfo = json_data.get('sellerInfo')
                paymentInfo = json_data.get('paymentInfo')
                lienHolderInfo = json_data.get('lienHolderInfo')

                if not sellerInfo or not paymentInfo:
                    return request.make_json_response({'error': 'Missing sellerInfo or paymentInfo in request body'}, 400)

                seller_contact_type = request.env['res.contact.type'].search([('name', '=', 'Seller')], limit=1)
                if not seller_contact_type:
                    return request.make_json_response({'error': 'Seller contact type not found'}, 400)
                sellerInfo['contact_type_ids'] = [seller_contact_type.id]

                newSeller = request.env['res.partner'].create(sellerInfo)
                if not newSeller:
                    return request.make_json_response({'error': 'Failed to create seller record'}, 500)

                paymentInfo['type'] = 'payment'
                newPaymentInfo = request.env['res.partner'].create(paymentInfo)
                if not newPaymentInfo:
                    return request.make_json_response({'error': 'Failed to create payment info'}, 500)

                default_lien_holder_id = None
                if lienHolderInfo:
                    lien_holder_contact_type = request.env['res.contact.type'].search([('name', '=', 'Lien Holder')], limit=1)
                    if not lien_holder_contact_type:
                        return request.make_json_response({'error': 'Lien Holder contact type not found'}, 400)

                    lienHolderInfo['contact_type_ids'] = [lien_holder_contact_type.id]
                    newLienHolder = request.env['res.partner'].create(lienHolderInfo)
                    if not newLienHolder:
                        return request.make_json_response({'error': 'Failed to create lien holder info'}, 500)

                    default_lien_holder_id = newLienHolder.id

                newSeller.write({
                    'child_ids': [(4, newPaymentInfo.id)],
                    'default_payment_info_id': newPaymentInfo.id,
                    'default_lien_holder_id': default_lien_holder_id
                })

                seller_data = newSeller.read()[0]
                new_seller_formatted = {
                    'id': seller_data['id'],
                }
                return request.make_json_response(new_seller_formatted)

            except Exception as e:
                _logger.error(f"Error creating seller: {str(e)}")
                return request.make_json_response({'error': f"Error when creating or updating: {str(e)}"}, 500)

    @core.http.rest_route(
      routes=build_route('/sellers/<int:seller_id>'),
      methods=['GET', 'PUT'],
      protected=True,
      docs=dict(
          tags=['Contacts'],
          summary='Get or Update Seller by ID',
          description='Fetch a seller by their ID or update their information.',
      ),
    )
    def get_or_update_seller_by_id(self, seller_id, **kw):
      """Fetch or update seller details by ID"""
    
      seller_contact_type = request.env['res.contact.type'].search([('name', '=', 'Seller')])
    
      if request.httprequest.method == 'GET':
        # Handle GET request: Fetch seller details
        if seller_contact_type:
            seller = request.env['res.partner'].search([
                ('id', '=', seller_id),
                ('contact_type_ids', 'in', seller_contact_type.ids)
            ], limit=1)
            
            if seller:
                # Retrieve default reps from seller
                default_reps = None
                if seller.rep_ids:
                  default_reps = []
                  for rep in seller.rep_ids:
                    default_reps.append({
                        'percentage_commission': rep.percentage_commission,
                        'id': rep.rep_id.id,
                    })

                # Retrieve default lien holder
                default_lien_holder = None
                if seller.default_lien_holder_id:
                    lien_holder = seller.default_lien_holder_id
                    default_lien_holder = {
                        'id': lien_holder.id,
                        'name': lien_holder.name,
                        'city': lien_holder.city,
                        'state': lien_holder.state_id.code if lien_holder.state_id else None,
                        'zip': lien_holder.zip,
                        'country': lien_holder.country_id.code if lien_holder.country_id else None,
                    }

                # Retrieve default payment information
                default_payment_info = None
                if seller.default_payment_info_id:
                    payment_info = seller.default_payment_info_id
                    default_payment_info = {
                        'id': payment_info.id,
                        'name': payment_info.name,
                        'street': payment_info.street,
                        'street2': payment_info.street2 if payment_info.street2 else None,
                        'city': payment_info.city,
                        'state': payment_info.state_id.code if payment_info.state_id else None,
                        'zip': payment_info.zip,
                        'country': payment_info.country_id.code if payment_info.country_id else None,
                    }

                # Prepare and return the response
                result = {
                    'id': seller.id,
                    'name': seller.name,
                    'contact_name': seller.contact_name,
                    'email': seller.email,
                    'phone': seller.phone,
                    'address': {
                        'street': seller.street,
                        'city': seller.city,
                        'state': seller.state_id.code if seller.state_id else None,
                        'country': seller.country_id.name if seller.country_id else None,
                        'zip': seller.zip,
                    },
                    'default_lien_holder': default_lien_holder,
                    'affidavit_verified': seller.affidavit_verified,
                    'has_master_agreement': seller.has_master_agreement,
                    'default_payment_info': default_payment_info,
                    'reps': default_reps
                }
                return request.make_json_response(result)
        return request.make_json_response({'error': 'Seller not found'}, status=404)
    
      elif request.httprequest.method == 'PUT':
        try:
            data = json.loads(request.httprequest.get_data(as_text=True))
            seller = request.env['res.partner'].search([
                ('id', '=', seller_id),
            ], limit=1)

            if not seller:
                return request.make_json_response({'error': 'Seller not found'}, status=404)

            allowed_fields = ['name', 'email', 'phone', 'street', 'city', 'state_id', 'country_id', 'zip', 'default_lien_holder_id', 'default_payment_info_id']
            update_vals = {key: data[key] for key in allowed_fields if key in data}
            seller.write(update_vals)

            return request.make_json_response({'message': 'Seller updated successfully', 'seller': seller.read()[0]})

        except Exception as e:
            return request.make_json_response({'error': f'Error updating seller: {str(e)}'}, status=500)

    @core.http.rest_route(
        routes=build_route('/sellers/<int:seller_id>/lienholders'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Get Lien Holders for a Seller',
            description='Fetches lien holders associated with a seller.',
        ),
    )
    def get_lienholders_for_seller(self, seller_id, **kw):
        """Fetch lien holders for a specific seller"""
        lien_holders = []
        seller = request.env['res.partner'].search([('id', '=', seller_id)], limit=1)

        if seller:
            for lien_holder in seller.lien_holder_ids:
                lien_holders.append({
                    'id': lien_holder.id,
                    'name': lien_holder.name,
                    'street': lien_holder.street if lien_holder.street else None,
                    'street2': lien_holder.street2 if lien_holder.street2 else None,
                    'city': lien_holder.city,
                    'state': lien_holder.state_id.code if lien_holder.state_id else None,
                    'zip': lien_holder.zip,
                    'country': lien_holder.country_id.name if lien_holder.country_id else None,
                    'default': lien_holder.id == seller.default_lien_holder_id.id,
                })
            return request.make_json_response(lien_holders)
        return request.make_json_response({'error': 'Seller not found'}, status=404)

    @core.http.rest_route(
        routes=build_route('/sellers/<int:seller_id>/paymentinfo'),
        methods=['GET', 'POST'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Get or Create Payment Info options for a Seller',
            description='Fetches or creates payment info associated with a seller.',
        ),
    )
    def handle_payment_info_for_seller(self, seller_id, **kw):
        """Fetch or create payment info options for a specific seller"""

        if request.httprequest.method == 'GET':
            payment_info_options = []
            seller = request.env['res.partner'].search([('id', '=', seller_id)], limit=1)

            if not seller:
                return request.make_json_response({'error': 'Seller not found'}, status=404)

            for payment_info in seller.child_ids:
                if payment_info.type == 'payment':
                    payment_info_options.append({
                        'id': payment_info.id,
                        'street': payment_info.street,
                        'street2': payment_info.street2 if payment_info.street2 else None,
                        'name': payment_info.name,
                        'city': payment_info.city,
                        'state': payment_info.state_id.code if payment_info.state_id else None,
                        'zip': payment_info.zip,
                        'country': payment_info.country_id.name if payment_info.country_id else None,
                        'default': payment_info.id == seller.default_payment_info_id.id,
                    })

            return request.make_json_response(payment_info_options)

        elif request.httprequest.method == 'POST':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                payment_info_data = json.loads(request_body)

                if not payment_info_data:
                    return request.make_json_response({'error': 'Missing payment info data in request body'}, 400)

                make_default = payment_info_data.pop('make_default', False)

                seller = request.env['res.partner'].search([('id', '=', seller_id)], limit=1)
                if not seller:
                    return request.make_json_response({'error': 'Seller not found'}, 404)

                payment_info_data['parent_id'] = seller.id
                payment_info_data['type'] = 'payment'

                new_payment_info = request.env['res.partner'].create(payment_info_data)

                if make_default:
                    seller.default_payment_info_id = new_payment_info.id

                result = new_payment_info.read(fields=None)[0]
                return request.make_json_response(result)

            except Exception as e:
                return request.make_json_response({'error': f"Error when creating payment info: {str(e)}"}, 500)


    # ----------------------------------------------------------
    # Lien Holders Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
      routes=build_route('/lienholders'),
      methods=['GET', 'POST'],
      protected=True,
      docs=dict(
          tags=['Contacts'],
          summary='Get All Lien Holders / Create Lien Holders',
          description='Fetches all lien holders or creates a new lien holder.',
      ),
    )
    def handle_lien_holders(self, **kw):
        """Fetch all lien holders or create a new lien holder"""

        
        if request.httprequest.method == 'GET':
            lien_holders = []
            lien_holder_contact_type = request.env['res.contact.type'].search([('name', '=', 'Lien Holder')])
            
            if lien_holder_contact_type:
                contacts = request.env['res.partner'].search([('contact_type_ids', 'in', lien_holder_contact_type.ids)], limit=1)
                
                for contact in contacts:
                    lien_holders.append({
                        'id': contact.id,
                        'name': contact.name,
                        'address': {
                            'street': contact.street,
                            'street2': contact.street2 if contact.street2 else None,
                            'city': contact.city,
                            'state': contact.state_id.code if contact.state_id else None,
                            'country': contact.country_id.name if contact.country_id else None,
                            'zip': contact.zip,
                        }
                    })
            return request.make_json_response(lien_holders)
        
        elif request.httprequest.method == 'POST':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                lien_holder_info = json.loads(request_body)

                if not lien_holder_info:
                    return request.make_json_response({'error': 'Missing lien holder information in request body'}, 400)


                # Extract and remove seller_id from the data
                seller_id = lien_holder_info.pop('seller_id', None)
                make_default = lien_holder_info.pop('make_default', False)

                lien_holder_contact_type = request.env['res.contact.type'].search([('name', '=', 'Lien Holder')], limit=1)
                if not lien_holder_contact_type:
                    return request.make_json_response({'error': 'Lien Holder contact type not found'}, 400)
                    
                lien_holder_info['contact_type_ids'] = [lien_holder_contact_type.id]
                new_lien_holder = request.env['res.partner'].create(lien_holder_info)

                if seller_id:
                    seller = request.env['res.partner'].search([('id', '=', seller_id)], limit=1)
                    if seller.exists():
                        seller.write({'lien_holder_ids': [(4, new_lien_holder.id)]})
                    else:
                        return request.make_json_response({'error': 'Seller not found'}, 404)

                if make_default:
                    seller.default_lien_holder_id = new_lien_holder.id 

                result = new_lien_holder.read(fields=None)[0]
                return request.make_json_response(result)

            except Exception as e:
                return request.make_json_response({'error': f"Error when creating or updating: {str(e)}"}, 500)
      
    @core.http.rest_route(
      routes=build_route('/lienholders/<int:lien_holder_id>'),
      methods=['GET', 'PUT'],
      protected=True,
      docs=dict(
          tags=['Contacts'],
          summary='Get or Update Lien Holder by ID',
          description='Fetch a lien holder by their ID or update their information.',
      ),
    )
    def get_or_update_lien_holder_by_id(self, lien_holder_id, **kw):
      """Fetch or update lien holder details by ID"""
    
      lien_holder_contact_type = request.env['res.contact.type'].search([('name', '=', 'Lien Holder')])
    
      if request.httprequest.method == 'GET':
        if lien_holder_contact_type:
            lien_holder = request.env['res.partner'].search([
                ('id', '=', lien_holder_id),
                ('contact_type_ids', 'in', lien_holder_contact_type.ids)
            ], limit=1)
            
            if lien_holder:
              result = {
                  'id': lien_holder.id,
                  'name': lien_holder.name,
                  'email': lien_holder.email,
                  'phone': lien_holder.phone,
                  'address': {
                      'street': lien_holder.street,
                      'city': lien_holder.city,
                      'state': lien_holder.state_id.code if lien_holder.state_id else None,
                      'country': lien_holder.country_id.name if lien_holder.country_id else None,
                      'zip': lien_holder.zip,
                  },
              }
              return request.make_json_response(result)
        return request.make_json_response({'error': 'Lien holder not found'}, status=404)
    
      elif request.httprequest.method == 'PUT':
        try:
            data = json.loads(request.httprequest.get_data(as_text=True))
            lien_holder = request.env['res.partner'].search([
                ('id', '=', lien_holder_id),
                ('contact_type_ids', 'in', lien_holder_contact_type.ids)
            ], limit=1)

            if not lien_holder:
                return request.make_json_response({'error': 'Lien holder not found'}, status=404)

            allowed_fields = ['name', 'email', 'phone', 'street', 'city', 'state_id', 'country_id', 'zip']
            update_vals = {key: data[key] for key in allowed_fields if key in data}
            lien_holder.write(update_vals)

            return request.make_json_response({'message': 'Lien holder updated successfully', 'Lien holder': lien_holder.read()[0]})

        except Exception as e:
            return request.make_json_response({'error': f'Error updating lien holder: {str(e)}'}, status=500)

    # ----------------------------------------------------------
    # Rep Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
      routes=build_route('/reps'),
      methods=['GET', 'POST'],
      protected=True,
      docs=dict(
          tags=['Contacts'],
          summary='List of Reps / Create Rep',
          description='Fetches a list of reps or creates a new rep.',
      ),
    )
    def handle_reps(self, **kw):
        """Fetch all reps or create a new rep"""
        
        if request.httprequest.method == 'GET':
            try:
                reps = []
                
                rep_contact_type = request.env['res.contact.type'].search([('name', '=', 'Rep')])
                
                if rep_contact_type:
                    contacts = request.env['res.partner'].search([('contact_type_ids', 'in', rep_contact_type.ids)])
                    
                    for contact in contacts:
                        state_abbreviation = contact.state_id.code if contact.state_id else None
                        
                        reps.append({
                            'id': contact.id,
                            'name': contact.name,
                            'email': contact.email,
                            'phone': contact.phone,
                            'address': {
                                'street': contact.street,
                                'street2': contact.street2 if contact.street2 else None,
                                'city': contact.city,
                                'state': state_abbreviation,
                                'country': contact.country_id.code if contact.country_id else None,
                                'zip': contact.zip,
                            }
                        })
                else:
                    reps = {'error': "No 'Rep' contact type found."}

                return request.make_json_response(reps)

            except Exception as e:
                return request.make_json_response({'error': str(e)}, status=500)

        elif request.httprequest.method == 'POST':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                rep_info = json.loads(request_body)
                
                if not rep_info:
                    return request.make_json_response({'error': 'Missing repInfo in request body'}, 400)

                rep_contact_type = request.env['res.contact.type'].search([('name', '=', 'Rep')], limit=1)
                if not rep_contact_type:
                    return request.make_json_response({'error': "Rep contact type not found"}, 400)
                
                rep_info['contact_type_ids'] = [(4, rep_contact_type.id)]

                new_rep = request.env['res.partner'].create(rep_info)

                result = {
                    'id': new_rep.id,
                    'name': new_rep.name,
                    'email': new_rep.email,
                    'phone': new_rep.phone,
                    'address': {
                        'street': new_rep.street,
                        'street2': new_rep.street2 if new_rep.street2 else None,
                        'city': new_rep.city,
                        'state': new_rep.state_id.code if new_rep.state_id else None,
                        'country': new_rep.country_id.code if new_rep.country_id else None,
                        'zip': new_rep.zip,
                    }
                }
                return request.make_json_response(result, status=201)

            except Exception as e:
                return request.make_json_response({'error': f"Error when creating a new rep: {str(e)}"}, 500)

    @core.http.rest_route(
        routes=build_route('/reps/<int:rep_id>'),
        methods=['GET', 'PUT'],
        protected=True,
        docs=dict(
            tags=['Contacts'],
            summary='Get or Update Rep by ID',
            description='Fetch a rep by their ID or update their information.',
        ),
    )
    def handle_rep_by_id(self, rep_id, **kw):
        """Fetch or update a rep by ID"""

        if request.httprequest.method == 'GET':
            try:
                rep_contact_type = request.env['res.contact.type'].search([('name', '=', 'Rep')], limit=1)
                if not rep_contact_type:
                    return request.make_json_response({'error': "Rep contact type not found"}, 404)

                rep = request.env['res.partner'].search([('id', '=', rep_id), ('contact_type_ids', 'in', rep_contact_type.ids)], limit=1)
                if not rep:
                    return request.make_json_response({'error': 'Rep not found'}, 404)

                result = {
                    'id': rep.id,
                    'name': rep.name,
                    'email': rep.email,
                    'phone': rep.phone,
                    'address': {
                        'street': rep.street,
                        'street2': rep.street2 if rep.street2 else None,
                        'city': rep.city,
                        'state': rep.state_id.code if rep.state_id else None,
                        'country': rep.country_id.code if rep.country_id else None,
                        'zip': rep.zip,
                    }
                }
                return request.make_json_response(result)

            except Exception as e:
                return request.make_json_response({'error': str(e)}, 500)

        elif request.httprequest.method == 'PUT':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                rep_info = json.loads(request_body)

                if not rep_info:
                    return request.make_json_response({'error': 'Missing repInfo in request body'}, 400)

                rep = request.env['res.partner'].search([('id', '=', rep_id)], limit=1)
                if not rep:
                    return request.make_json_response({'error': 'Rep not found'}, 404)

                rep.write(rep_info)

                result = {
                    'id': rep.id,
                    'name': rep.name,
                    'email': rep.email,
                    'phone': rep.phone,
                    'address': {
                        'street': rep.street,
                        'street2': rep.street2 if rep.street2 else None,
                        'city': rep.city,
                        'state': rep.state_id.code if rep.state_id else None,
                        'country': rep.country_id.code if rep.country_id else None,
                        'zip': rep.zip,
                    }
                }
                return request.make_json_response(result)

            except Exception as e:
                return request.make_json_response({'error': f"Error when updating rep: {str(e)}"}, 500)

    # ----------------------------------------------------------
    # Buyer Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
        routes=build_route('/buyers'),
        methods=['GET', 'POST'],
        protected=True,
        docs=dict(
            tags=['Buyers'],
            summary='Get All Buyers / Create Buyer',
            description='Fetches all buyers or creates a new buyer.',
        ),
    )
    def handle_buyers(self, **kw):
        """Fetch all buyers or create a new buyer"""
        
        if request.httprequest.method == 'GET':
            buyers = []
            buyer_contact_type = request.env['res.contact.type'].search([('name', '=', 'Buyer')])

            if buyer_contact_type:
                contacts = request.env['res.partner'].search([('contact_type_ids', 'in', buyer_contact_type.ids)])

                for contact in contacts:
                    buyers.append(serialize_contact_buyer(contact))
                return request.make_json_response(buyers)

        elif request.httprequest.method == 'POST':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                buyerInfo = json.loads(request_body)

                if not buyerInfo:
                    return request.make_json_response({'error': 'Missing buyerInfo in request body'}, 400)

                buyer_contact_type = request.env['res.contact.type'].search([('name', '=', 'Buyer')], limit=1)
                buyerInfo['contact_type_ids'] = [buyer_contact_type.id]

                newBuyer = request.env['res.partner'].create(buyerInfo)

                result = newBuyer.read()[0]
            except Exception as e:
                result = {'error': f"Error when creating or updating: {str(e)}"}

            return request.make_json_response(result)

    @core.http.rest_route(
        routes=build_route('/buyers/<int:buyer_id>'),
        methods=['GET', 'PUT'],
        protected=True,
        docs=dict(
            tags=['Buyers'],
            summary='Get or Update Buyer by ID',
            description='Fetch a buyer by their ID or update their information.',
        ),
    )
    def handle_buyer_by_id(self, buyer_id, **kw):
        """Fetch or update a buyer by ID"""
        
        if request.httprequest.method == 'GET':
            try:
                buyer_contact_type = request.env['res.contact.type'].search([('name', '=', 'Buyer')], limit=1)
                if not buyer_contact_type:
                    return request.make_json_response({'error': "Buyer contact type not found"}, 404)

                buyer = request.env['res.partner'].search([('id', '=', buyer_id), ('contact_type_ids', 'in', buyer_contact_type.ids)], limit=1)
                if not buyer:
                    return request.make_json_response({'error': 'Buyer not found'}, 404)

                result = {
                    'id': buyer.id,
                    'name': buyer.name,
                    'email': buyer.email,
                    'phone': buyer.phone,
                    'address': {
                        'street': buyer.street,
                        'street2': buyer.street2 if buyer.street2 else None,
                        'city': buyer.city,
                        'state': buyer.state_id.code if buyer.state_id else None,
                        'country': buyer.country_id.name if buyer.country_id else None,
                        'zip': buyer.zip,
                    }
                }
                return request.make_json_response(result)

            except Exception as e:
                return request.make_json_response({'error': str(e)}, 500)

        elif request.httprequest.method == 'PUT':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                buyerInfo = json.loads(request_body)

                if not buyerInfo:
                    return request.make_json_response({'error': 'Missing buyerInfo in request body'}, 400)

                buyer = request.env['res.partner'].search([('id', '=', buyer_id)], limit=1)
                if not buyer:
                    return request.make_json_response({'error': 'Buyer not found'}, 404)

                buyer.write(buyerInfo)

                result = {
                    'id': buyer.id,
                    'name': buyer.name,
                    'email': buyer.email,
                    'phone': buyer.phone,
                    'address': {
                        'street': buyer.street,
                        'street2': buyer.street2 if buyer.street2 else None,
                        'city': buyer.city,
                        'state': buyer.state_id.code if buyer.state_id else None,
                        'country': buyer.country_id.name if buyer.country_id else None,
                        'zip': buyer.zip,
                    }
                }
                return request.make_json_response(result)

            except Exception as e:
                return request.make_json_response({'error': f"Error when updating buyer: {str(e)}"}, 500)

  # ---------------------------------------------------------- #
  # ------------------------------------------------------ #
  # Select Options Endpoints
  # ------------------------------------------------------ #
  # ---------------------------------------------------------- #

    # ----------------------------------------------------------
    # Cattle Select Options Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
      routes=build_route('/select-options/states'),
      methods=['GET'],
      protected=True,
      docs=dict(
          tags=['Select Options'],
          summary='Select Options for States',
          description='Fetches states based on the selected country.',
      ),
    )
    def get_states(self, **kw):
      """Fetch states by country"""
    
      try:
          country_id = request.params.get('country_id', 233)
          country = request.env['res.country'].browse(int(country_id))
          
          if not country.exists():
              return request.make_json_response({'error': 'Invalid country ID'})
          
          state_records = request.env['res.country.state'].search([('country_id', '=', country.id)])
          states = [{'id': state.id, 'name': state.name, 'abv': state.code, 'region': state.region_id.id, 'country_id': state.country_id.id} for state in state_records]

          return request.make_json_response(states)
      
      except Exception as e:
          return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route('/select-options/regions'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Select Options'],
            summary='Select Options for Regions',
            description='Fetches regions.',
        ),
    )
    def get_regions(self, **kw):
        """Fetch regions with associated states"""
        try:
            regions = []
            for region in request.env['res.region'].search([]):
                # Fetch states for the current region
                states = request.env['res.country.state'].search([('region_id', '=', region.id)])
                regions.append({
                    'id': region.id,
                    'name': region.name,
                    'states': [{'id': state.id, 'name': state.name, 'abv': state.code} for state in states],
                })

            return request.make_json_response(regions)

        except Exception as e:
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
      routes=build_route('/select-options/contract/statuses'),
      methods=['GET'],
      protected=True,
      docs=dict(
          tags=['Select Options'],
          summary='Select Options for States',
          description='Fetches states based on the selected country.',
      ),
    )
    def get_statuses(self, **kw):
        """Fetch contract status types"""
        try:
            # Access the model and its fields
            Contract = request.env['consignment.contract']
            status_options = dict(Contract._fields['state'].selection)

            # Return the selection values as JSON
            return request.make_json_response({'statuses': status_options})
        
        except Exception as e:
            return request.make_json_response({'error': str(e)}, status=500)

    @core.http.rest_route(
        routes=build_route('/select-options/countries'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Select Options'],
            summary='Select Options for Countries',
            description='Fetches a list of specific countries (US, CA, MX).',
        ),
    )
    def get_countries(self, **kw):
        """Fetch countries (US, CA, MX)"""

        try:
            countries = request.env['res.country'].search([('code', 'in', ['US', 'CA', 'MX'])])
            sorted_countries = sorted(countries, key=lambda country: (country.code != 'US', country.name))
            result = [{'id': country.id, 'name': country.name, 'abv': country.code} for country in sorted_countries]

            return request.make_json_response(result)

        except Exception as e:
            return request.make_json_response({'error': str(e)}, status=500)
    
    @core.http.rest_route(
        routes=build_route('/select-options/contacts/types'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Select Options'],
            summary='Select Options for Contact Types',
            description='Fetches a list of contact types.',
        ),
    )
    def get_contact_types(self, **kw):
        """Fetch contact types"""

        try:
            contact_types = request.env['res.contact.type'].search([])
            result = [{'id': type.id, 'name': type.name} for type in contact_types]

            return request.make_json_response(result)

        except Exception as e:
            return request.make_json_response({'error': str(e)}, status=500)
    
    @core.http.rest_route(
        routes=build_route('/select-options/cattle/static'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Select Options'],
            summary='Static Select Options for Cattle Contracts',
            description='Fetches static select values for cattle contracts based on the categories provided.',
        ),
    )
    def get_static_cattle_values(self, **kw):
      """Fetch static select values for cattle contracts"""
      
      category_model_mapping = {
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
          'regions': 'res.region',
          'countries': 'res.country',
          'directions': '',
          'vaccPrograms': 'vac.program',
          'specialSections': 'special.section',
          'geneticMerit': 'genetic.merit',
          'valueNutrition': 'van.program',
          'premiumGenetics': 'premium.genetics.program',
          'sourceAgeVerification': 'third.party.age',
          'locationType': 'location.type',
          'gap': 'gap.program',
          'current_fob': 'location.type',
          'whoseOption': 'whose.option',
          'weightStop': 'weight.stop'
      }

      category_param = request.params.get('category')
      if category_param:
          category_list = category_param.split(',')
      else:
          category_list = category_model_mapping.keys()

      staticFields = {}

      def fetch_and_format_records(model_name, name_field='name'):
          records = request.env[model_name].search([])
          return [{'id': record.id, 'name': getattr(record, name_field)} for record in records]

      for category in category_list:
          if category in category_model_mapping:
              model_name = category_model_mapping[category]
              if category == 'states':
                  us_country = request.env['res.country'].search([('code', '=', 'US')])
                  state_records = request.env['res.country.state'].search([('country_id', '=', us_country.id)])
                  staticFields['states'] = [{'id': record.id, 'name': record.name, 'abv': record.code, 'region': record.region_id.id} for record in state_records]
              elif category == 'countries':
                  countries = request.env['res.country'].search([('code', 'in', ['US', 'CA', 'MX'])])
                  sorted_countries = sorted(countries, key=lambda c: c.code != 'US')
                  staticFields['countries'] = [{'id': country.id, 'name': country.name, 'abv': country.code} for country in sorted_countries]
              elif category == 'directions':
                staticFields['directions'] = [{'id': key, 'name': label} for key, label in DIRECTION_LIST]
              elif category == 'regions':
                regions = request.env['res.region'].search([])
                staticFields['regions'] = []
                for region in regions:
                    states = request.env['res.country.state'].search([('region_id', '=', region.id)])
                    region_data = {
                        'id': region.id,
                        'name': region.name,
                        'states': [{'id': state.id, 'name': state.name, 'abv': state.code} for state in states],
                    }
                    staticFields['regions'].append(region_data)
              else:
                  staticFields[category] = fetch_and_format_records(model_name)
      
      return request.make_json_response(staticFields)

    @core.http.rest_route(
        routes=build_route('/select-options/cattle/slides'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Select Options'],
            summary='Select Options for Slide Type in Cattle Contracts',
            description='Fetches slide type select values for cattle contracts.',
        ),
    )
    def get_slide_type_values(self, **kw):
        """Fetch select options for slide types in cattle contracts"""
        
        try:
            slide_type_records = request.env['slide.type'].search([])
            slide_types = [{'id': record.id, 'name': record.label, 'sell_by_head': record.sell_by_head, 'above': record.above, 'under': record.under, 'both': record.both} for record in slide_type_records]

            return request.make_json_response(slide_types)

        except Exception as e:
            return request.make_json_response({'error': str(e)}, status=500)

  # ---------------------------------------------------------- #
  # ------------------------------------------------------ #
  # Auction Endpoints
  # ------------------------------------------------------ #
  # ---------------------------------------------------------- #

    # ----------------------------------------------------------
    # Cattle Auction Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
        routes=build_route('/auctions'),
        methods=['GET', 'POST'],
        protected=True,
        docs=dict(
            tags=['Auctions'],
            summary='Get All Auctions / Create Auction',
            description='Fetches all auctions or creates a new auction, with optional filtering by sale type and category.',
        ),
    )
    def handle_auctions(self, **kw):
        """Handle auctions (GET all with optional filters, POST create)"""

        if request.httprequest.method == 'GET':
            auction_list = []
            try:
                type_param = request.params.get('type')

                domain = []

                if type_param:
                    domain.append(('sale_type', '=', int(type_param)))

                auctions = request.env['sale.auction'].search(domain)

                for auction in auctions:
                    auction_list.append({
                        'id': auction.id,
                        'name': auction.name,
                        'auction_date': auction.sale_date_begin,
                        'location': auction.location,
                        'sale_type': auction.sale_type.name if auction.sale_type else None,
                    })
                return request.make_json_response(auction_list)
            except Exception as e:
                return request.make_json_response({'error': str(e)})

        elif request.httprequest.method == 'POST':
          try:
              request_body = request.httprequest.get_data(as_text=True)
              auction_data = json.loads(request_body)

              if not auction_data:
                  return request.make_json_response({'error': 'Auction data missing from request body'})

              new_auction = request.env['sale.auction'].create(auction_data)
              
              created_auction = new_auction.read(['id', 'name', 'sale_date_begin', 'location', 'sale_type'])[0]

              return request.make_json_response(created_auction)

          except Exception as e:
              return request.make_json_response({'error': str(e)})

        return request.make_json_response({'error': 'Method not allowed'})

    @core.http.rest_route(
        routes=build_route('/auctions/upcoming'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Auctions'],
            summary='Get Upcoming Auctions',
            description='Fetches upcoming auctions with optional filtering by sale type and category.',
        ),
    )
    def get_upcoming_auctions(self, **kw):
        """Fetch upcoming auctions with optional filters by type and category"""
        sale_list = []
        try:
            type_param = request.params.get('type')
            lax_sale_type = request.env['sale.type'].search([('name', '=', 'LiveAg Xchange')], limit=1)
            pt_sale_type = request.env['sale.type'].search([('name', '=', 'Private Treaty')], limit=1)
            current_date = datetime.date.today()

            domain = []

            if type_param:
                type_id = int(type_param)
                if type_id in [pt_sale_type.id, lax_sale_type.id]:
                    domain.append(('sale_type', '=', type_id))
                else:
                    domain = [
                        ('sale_date_begin', '>=', current_date),
                        ('sale_type', '=', type_id),
                    ]
            else:
                domain = [
                    '|',
                    ('sale_type', '=', lax_sale_type.id),
                    '|',
                    ('sale_type', '=', pt_sale_type.id),
                    ('sale_date_begin', '>=', current_date),
                ]

            sale_type_records = request.env['sale.auction'].search(domain)

            for record in sale_type_records:
                sale_list.append({
                    'id': record.id,
                    'name': record.name,
                    'auction_date': record.sale_date_begin,
                    'location': record.location,
                    'sale_type': record.sale_type.name if record.sale_type else None,
                })

            if not sale_list:
                _logger.info("No records found for the given search parameters.")

            return request.make_json_response(sale_list)
        except Exception as e:
            _logger.error("Error occurred: %s", str(e))
            return request.make_json_response({'error': str(e)})

    @core.http.rest_route(
        routes=build_route('/auctions/<int:auction_id>'),
        methods=['GET', 'PUT'],
        protected=True,
        docs=dict(
            tags=['Auctions'],
            summary='Get Auction by ID / Update Auction',
            description='Fetches or updates a specific auction by ID.',
        ),
    )
    def handle_auction_by_id(self, auction_id, **kw):
        """Handle auctions by ID (GET fetch, PUT update)"""

        if request.httprequest.method == 'GET':
            try:
                auction = request.env['sale.auction'].search([('id', '=', auction_id)], limit=1)
                if not auction:
                    return request.make_json_response({'error': 'Auction not found'})
                
                lot_list = []
                lots = request.env['consignment.contract'].search([('auction_id', '=', auction_id)])
                sale_order_list = []
                for lot in lots:
                    sale_order = lot.sale_order
                    if sale_order:
                        sale_order_list.append(lot.lot_number)

                for lot in lots:
                    lot_data = serialize_contract_preview(lot)
                    lot_list.append(lot_data)

                auction_data = {
                    'id': auction.id,
                    'name': auction.name,
                    'auction_date': auction.sale_date_begin,
                    'location': auction.location,
                    'sale_type': auction.sale_type.name if auction.sale_type else None,
                    'lots': lot_list,
                    'sale_order': sale_order_list,
                }
                return request.make_json_response(auction_data)
            except Exception as e:
                return request.make_json_response({'error': str(e)})

        elif request.httprequest.method == 'PUT':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                auction_data = json.loads(request_body)

                if not auction_data:
                    return request.make_json_response({'error': 'Auction data missing from request body'})

                auction = request.env['sale.auction'].browse(auction_id)
                if not auction:
                    return request.make_json_response({'error': 'Auction not found'})

                auction.write(auction_data)

                updated_auction = auction.read(['id', 'name', 'sale_date_begin', 'location', 'sale_type'])[0]

                return request.make_json_response({'message': 'Auction updated successfully', 'auction': updated_auction})
            except Exception as e:
                return request.make_json_response({'error': str(e)})

        return request.make_json_response({'error': 'Method not allowed'})
    
    @core.http.rest_route(
        routes=build_route('/auctions/<int:auction_id>/lots'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Auctions'],
            summary='Get Lots for Auction by ID',
            description='Fetches lots for a specific auction by ID.',
        ),
    )
    def get_lots_for_auction(self, auction_id, **kw):
        """Handle auctions by ID (GET fetch, PUT update)"""
        try:
            limit_param = request.params.get('limit')

            domain = []

            if limit_param:
                domain.append(('limit', '=', int(limit_param)))
                
            lot_list = []
            lots = request.env['consignment.contract'].search([('auction_id', '=', auction_id)], limit=limit_param)

            for lot in lots:
                lot_data = serialize_contract_preview(lot)
                lot_list.append(lot_data)
                
            return request.make_json_response(lot_list)
        except Exception as e:
            return request.make_json_response({'error': str(e)})
        
    @core.http.rest_route(
        routes=build_route('/auctions/<int:auction_id>/lots/<string:contract_id>'),
        methods=['GET', 'PUT'],
        protected=True,
        docs=dict(
            tags=['Auctions'],
            summary='Get Lot by ID / Update Lot by ID',
            description='Fetches or updates a lot by its ID.',
        ),
    )
    def handle_lot_by_id(self, auction_id, contract_id, **kw):
        """Handle lot by ID (GET fetch, PUT update)"""

        if request.httprequest.method == 'GET':
          try:
              lot = request.env['consignment.contract'].search([
                  '&',
                  ('auction_id', '=', auction_id),
                  '|',
                  ('contract_id', '=', contract_id),
                  ('lot_number', '=', contract_id)
              ], limit=1)
              if lot:
                view = kw.get('view', 'preview')
                if view == 'detailed':
                    lot_data = serialize_contract_detailed(lot)
                elif view == 'editable':
                    lot_data = serialize_contract_editable(lot)
                else:
                    lot_data = serialize_contract_preview(lot)

                return request.make_json_response(lot_data)
              else:
                  return request.make_json_response({'error': 'Lot not found'})
          except Exception as e:
              return request.make_json_response({'error': str(e)})

        elif request.httprequest.method == 'PUT':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                lot_data = json.loads(request_body)

                if not lot_data:
                    return request.make_json_response({'error': 'Contract data missing from request body'})

                lot = request.env['consignment.contract'].search([
                    '&',
                    ('auction_id', '=', auction_id),
                    '|',
                    ('contract_id', '=', contract_id),
                    ('lot_number', '=', contract_id)
                ], limit=1)
                
                if not lot:
                    return request.make_json_response({'error': 'Lot not found'})

                # Extract rep and addendum data before writing to contract
                incoming_rep_data = lot_data.pop('rep_ids', None)
                incoming_addendum_data = lot_data.pop('addendum_ids', None)

                # Write basic contract data first
                lot.write(lot_data)

                # Handle reps
                if incoming_rep_data is not None:
                    incoming_rep_ids = {rep_data['rep_id'] for rep_data in incoming_rep_data}
                    existing_rep_entries = lot.rep_ids
                    existing_rep_ids = {entry.rep_id.id: entry for entry in existing_rep_entries}

                    reps_to_delete = [
                        (2, existing_rep_ids[rep_id].id, False)
                        for rep_id in existing_rep_ids
                        if rep_id not in incoming_rep_ids
                    ]
                    reps_to_update = [
                        (1, existing_rep_ids[rep_data['rep_id']].id, {
                            'percentage_commission': rep_data['percentage_commission'],
                            'seller_id': lot.seller_id.id
                        })
                        for rep_data in incoming_rep_data if rep_data['rep_id'] in existing_rep_ids
                    ]
                    reps_to_add = [
                        (0, 0, {
                            'rep_id': rep_data['rep_id'], 
                            'percentage_commission': rep_data['percentage_commission'],
                            'seller_id': lot.seller_id.id
                        })
                        for rep_data in incoming_rep_data if rep_data['rep_id'] not in existing_rep_ids
                    ]

                    lot.write({'rep_ids': reps_to_delete + reps_to_update + reps_to_add})

                # Handle addendums
                if incoming_addendum_data is not None:
                    # Get existing addendums and their IDs
                    existing_addendums = lot.addendum_ids
                    existing_addendum_ids = {addendum.id for addendum in existing_addendums}
                    
                    # Prepare commands for addendums
                    addendums_to_delete = [
                        (2, addendum.id, False)
                        for addendum in existing_addendums
                        if addendum.id not in {addendum_data.get('id') for addendum_data in incoming_addendum_data if addendum_data.get('id')}
                    ]
                    
                    addendums_to_update = [
                        (1, addendum_data['id'], {
                            'seller_id': addendum_data['seller_id'],
                            'head_count': addendum_data['head_count'],
                            'lien_holder_id': addendum_data.get('lien_holder_id'),
                            'part_payment': addendum_data.get('part_payment', 0),
                            'active': addendum_data.get('active', True),
                        })
                        for addendum_data in incoming_addendum_data
                        if addendum_data.get('id') in existing_addendum_ids
                    ]
                    
                    addendums_to_add = [
                        (0, 0, {
                            'seller_id': addendum_data['seller_id'],
                            'head_count': addendum_data['head_count'],
                            'lien_holder_id': addendum_data.get('lien_holder_id'),
                            'part_payment': addendum_data.get('part_payment', 0),
                            'active': addendum_data.get('active', True),
                        })
                        for addendum_data in incoming_addendum_data
                        if not addendum_data.get('id')
                    ]
                    
                    final_command = {'addendum_ids': addendums_to_delete + addendums_to_update + addendums_to_add}
                    
                    lot.write(final_command)
                    
                updated_lot = lot.read()[0]
                
                return request.make_json_response({
                    'message': 'Lot updated successfully',
                    'data': serialize_contract_editable(lot)
                })

            except Exception as e:
                _logger.error("Error updating lot: %s", str(e))
                return request.make_json_response({'error': f"Unexpected error: {str(e)}"})

            return request.make_json_response({'error': 'Method not allowed'})

  # ---------------------------------------------------------- #
  # ------------------------------------------------------ #
  # Contract Endpoints
  # ------------------------------------------------------ #
  # ---------------------------------------------------------- #

    # ----------------------------------------------------------
    # Cattle Contract Endpoints
    # ----------------------------------------------------------

    @core.http.rest_route(
        routes=build_route('/contracts'),
        methods=['GET', 'POST'],
        protected=True,
        docs=dict(
            tags=['Contracts'],
            summary='Get All Contracts / Create Contract',
            description='''Fetches all contracts or creates a new contract.
            
            GET Query Parameters:
            - page (int): Page number for pagination (optional)
            - per_page (int): Items per page, max 100 (optional)
            - auction_id (int): Filter by auction ID (optional)
            - kind_type (string): JSON array of cattle types e.g. ["STEER","HEIFER"] (optional)
            - seller_id (int): Filter by seller ID (optional)
            - representative_id (int): Filter by representative ID (optional)
            - state (string): JSON array of states e.g. ["CREATED","CONTRACTED"] (optional)
            - delivery_date_start (string): ISO date for minimum delivery date (optional)
            - delivery_date_end (string): ISO date for maximum delivery date (optional)
            - weight_min (int): Minimum weight filter (optional)
            - weight_max (int): Maximum weight filter (optional)
            - search (string): Search in seller name, contract number, lot number (optional)
            - sale_type (string): JSON array of sale types e.g. ["video","laxchange","privatetreaty"] (optional)

            Example: /contracts?page=1&per_page=10&kind_type=["STEER"]&seller_id=456&sale_type=["video"]
            ''',
        ),
    )
    def handle_contracts(self, **kw):
        """Handle contracts (GET all, POST create)"""
        
        _logger.info("handle_contracts: entered")
        _logger.info("handle_contracts: method=%s", request.httprequest.method)
        _logger.info("handle_contracts: params=%s", dict(request.params))

        user_id = request.httprequest.headers.get('X-User-Id')

        if not user_id:
            return request.make_json_response({'error': 'User ID not found in request headers'})
        
        user = get_user(user_id)
        user_roles = user.get('roles')

        if request.httprequest.method == 'GET':
            domain = []

            # Get filters from request parameters
            filters = self._get_filter_from_params()
            
            # Apply filters to domain
            domain = self._apply_filters_to_domain(domain, filters)

            # Add pagination parameter handling
            page = kw.get('page')
            per_page = kw.get('per_page')
            use_pagination = page is not None or per_page is not None
            
            if use_pagination:
                try:
                    page = int(page) if page is not None else 1
                    per_page = int(per_page) if per_page is not None else 25
                    
                    if page < 1:
                        return request.make_json_response({'error': 'Page must be >= 1'})
                    if per_page < 1 or per_page > 100:
                        return request.make_json_response({'error': 'Per page must be between 1 and 100'})
                        
                    offset = (page - 1) * per_page
                except (ValueError, TypeError):
                    return request.make_json_response({'error': 'Invalid page or per_page parameter'})

            if 'admin' in user_roles:
                try:
                    contract_list = []
                    Contract = request.env['consignment.contract']
                    
                    if use_pagination:
                        # Paginated response
                        total_count = Contract.search_count(domain)
                        contracts = Contract.search(domain, limit=per_page, offset=offset, order='create_date desc')
                        total_pages = (total_count + per_page - 1) // per_page
                    else:
                        # Non-paginated response (backward compatibility)
                        contracts = Contract.search(domain, order='create_date desc')
                    
                    for contract in contracts:
                        contract_data = serialize_contract_preview(contract)
                        contract_list.append(contract_data)
                    
                    if use_pagination:
                        return request.make_json_response({
                            'contracts': contract_list,
                            'pagination': {
                                'page': page,
                                'per_page': per_page,
                                'total_count': total_count,
                                'total_pages': total_pages
                            },
                            'success': True
                        })
                    else:
                        return request.make_json_response(contract_list)
                except Exception as e:
                    _logger.error("Error getting contracts for admin role: %s", str(e))
                    return request.make_json_response({'error': str(e)})

            elif 'rep' in user_roles:
                try:
                    contract_list = []
                    Contract = request.env['consignment.contract']
                    contract_ids = user.get('contracts_as_rep', [])
                    rep_domain = [('id', 'in', contract_ids)]
                    rep_domain = self._apply_filters_to_domain(rep_domain, filters)
                    
                    if use_pagination:
                        # For rep role with pagination, we need to use search with domain
                        total_count = Contract.sudo().search_count(rep_domain)
                        contracts = Contract.sudo().search(rep_domain, limit=per_page, offset=offset, order='create_date desc')
                        total_pages = (total_count + per_page - 1) // per_page
                    else:
                        # Non-paginated response (backward compatibility)
                        contracts = Contract.sudo().search(rep_domain, order='create_date desc')
                    
                    status_options = dict(Contract._fields['state'].selection)

                    for contract in contracts:
                        reps = serialize_reps_for_contract(contract)
                        contract_data = serialize_contract_preview(contract)
                        contract_list.append(contract_data)
                    
                    if use_pagination:
                        return request.make_json_response({
                            'contracts': contract_list,
                            'pagination': {
                                'page': page,
                                'per_page': per_page,
                                'total_count': total_count,
                                'total_pages': total_pages
                            },
                            'success': True
                        })
                    else:
                        return request.make_json_response(contract_list)
                except Exception as e:
                    _logger.error("Error getting contracts for rep role: %s", str(e))
                    return request.make_json_response({'error': str(e)})
            
            else:
                return request.make_json_response({'error': 'User not authorized to view contracts'})

        elif request.httprequest.method == 'POST':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                contract_data = json.loads(request_body)

                if not contract_data:
                    return request.make_json_response({'error': 'Contract data missing from request body'})

                contract_data.pop("rep_ids", None)

                new_contract = request.env['consignment.contract'].create(contract_data)
                return request.make_json_response({'contract_id': new_contract.contract_id})

            except Exception as e:
                return request.make_json_response({'error': str(e)})

        return request.make_json_response({'error': 'Method not allowed'})

    @core.http.rest_route(
        routes=build_route('/contracts/<string:contract_id>'),
        methods=['GET', 'PUT'],
        protected=True,
        docs=dict(
            tags=['Contracts'],
            summary='Get Contract by ID / Update Contract by ID',
            description='Fetches or updates a contract by its ID.',
        ),
    )
    def handle_contract_by_id(self, contract_id, **kw):
        """Handle contract by ID (GET fetch, PUT update)"""

        if request.httprequest.method == 'GET':
          try:
              contract = request.env['consignment.contract'].search([('contract_id', 'ilike', contract_id)], limit=1)
              if contract:
                view = kw.get('view', 'preview')
                if view == 'detailed':
                    contract_data = serialize_contract_detailed(contract)
                elif view == 'editable':
                    contract_data = serialize_contract_editable(contract)
                else:
                    contract_data = serialize_contract_preview(contract)

                return request.make_json_response(contract_data)
              else:
                  return request.make_json_response({'error': 'Contract not found'})
          except Exception as e:
              return request.make_json_response({'error': str(e)})

        elif request.httprequest.method == 'PUT':
            try:
                request_body = request.httprequest.get_data(as_text=True)
                contract_data = json.loads(request_body)

                if not contract_data:
                    return request.make_json_response({'error': 'Contract data missing from request body'})

                contract = request.env['consignment.contract'].search([('contract_id', '=', contract_id)], limit=1)
                if not contract:
                    return request.make_json_response({'error': 'Contract not found'})

                # Extract rep and addendum data before writing to contract
                incoming_rep_data = contract_data.pop('rep_ids', None)
                incoming_addendum_data = contract_data.pop('addendum_ids', None)

                # Write basic contract data first
                contract.write(contract_data)

                # Handle reps
                if incoming_rep_data is not None:
                    try:
                        # First clear existing reps
                        contract.write({'rep_ids': [(5, 0, 0)]})

                        # Then create new reps if we have data
                        if incoming_rep_data:
                            for rep_data in incoming_rep_data:
                                contract.write({
                                    'rep_ids': [(0, 0, {
                                        'rep_id': rep_data['rep_id'],
                                        'percentage_commission': rep_data['percentage_commission'],
                                        'seller_id': contract.seller_id.id,
                                        'active': True
                                    })]
                                })

                        _logger.info("Successfully updated rep_ids")
                    except Exception as e:
                        _logger.error("Error handling rep_ids: %s", str(e))
                        _logger.error("Input data: %s", incoming_rep_data)
                        import traceback
                        _logger.error("Traceback:\n%s", traceback.format_exc())
                        raise

                # Handle addendums
                if incoming_addendum_data is not None:
                    # Get existing addendums and their IDs
                    existing_addendums = contract.addendum_ids
                    existing_addendum_ids = {addendum.id for addendum in existing_addendums}
                    
                    # Prepare commands for addendums
                    addendums_to_delete = [
                        (2, addendum.id, False)
                        for addendum in existing_addendums
                        if addendum.id not in {addendum_data.get('id') for addendum_data in incoming_addendum_data if addendum_data.get('id')}
                    ]
                    
                    addendums_to_update = [
                        (1, addendum_data['id'], {
                            'seller_id': addendum_data['seller_id'],
                            'head_count': addendum_data['head_count'],
                            'lien_holder_id': addendum_data.get('lien_holder_id'),
                            'part_payment': addendum_data.get('part_payment', 0),
                            'active': addendum_data.get('active', True),
                        })
                        for addendum_data in incoming_addendum_data
                        if addendum_data.get('id') in existing_addendum_ids
                    ]
                    
                    addendums_to_add = [
                        (0, 0, {
                            'seller_id': addendum_data['seller_id'],
                            'head_count': addendum_data['head_count'],
                            'lien_holder_id': addendum_data.get('lien_holder_id'),
                            'part_payment': addendum_data.get('part_payment', 0),
                            'active': addendum_data.get('active', True),
                        })
                        for addendum_data in incoming_addendum_data
                        if not addendum_data.get('id')
                    ]
                    
                    final_command = {'addendum_ids': addendums_to_delete + addendums_to_update + addendums_to_add}
                    
                    contract.write(final_command)
                    
                updated_contract = contract.read()[0]
                
                return request.make_json_response({
                    'message': 'Contract updated successfully',
                    'data': serialize_contract_editable(contract)
                })

            except Exception as e:
                _logger.error("Error updating contract: %s", str(e))
                return request.make_json_response({'error': f"Unexpected error: {str(e)}"})

            return request.make_json_response({'error': 'Method not allowed'})

    @core.http.rest_route(
        routes=build_route('/contracts/<string:contract_id>/activity'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contracts'],
            summary='Get Changes for Contract by ID',
            description='Fetches the changes made to a contract by its ID.',
        ),
    )
    def get_contract_changes(self, contract_id, **kw):
        """Fetch changes made to the contract by ID"""
        changes = []
        
        try:
          #   contract = request.env['consignment.contract'].search([('contract_id', 'ilike', contract_id)], limit=1)
          contracts = request.env['consignment.contract'].search([
            ('contract_id', 'ilike', contract_id)
          ], limit=1)

          # Filter to ensure an exact case-insensitive match
          contract = next((c for c in contracts if c.contract_id.lower() == contract_id.lower()), None)
          
          if not contract:
              return request.make_json_response({'error': 'Contract not found'})
          
          return request.make_json_response({'message': 'No changes found for this contract'})

        #   for message in contract.message_ids:
        #       message_data = message.read()[0]
        #       tracking_value_ids = message_data.get('tracking_value_ids', [])
              
        #       if tracking_value_ids:
        #           tracking_values = request.env['mail.tracking.value'].browse(tracking_value_ids).read()
                  
        #           for tracking_value in tracking_values:
        #               field_name = tracking_value['field_id'][1]
        #               if '(' in field_name and ')' in field_name:
        #                   field_name_cleaned = field_name.split('(')[0].strip()
        #               else:
        #                   field_name_cleaned = field_name

        #               old_value = (
        #                   tracking_value['old_value_char'] or
        #                   tracking_value['old_value_text'] or
        #                   tracking_value['old_value_float'] or
        #                   tracking_value['old_value_integer'] or
        #                   tracking_value['old_value_datetime'] or 'N/A'
        #               )
                      
        #               new_value = (
        #                   tracking_value['new_value_char'] or
        #                   tracking_value['new_value_text'] or
        #                   tracking_value['new_value_float'] or
        #                   tracking_value['new_value_integer'] or
        #                   tracking_value['new_value_datetime'] or 'N/A'
        #               )
                      
        #               changes.append({
        #                   'field_changed': field_name_cleaned,
        #                   'changed_by': tracking_value['write_uid'][1],
        #                   'change_date': tracking_value['write_date'],
        #                   'old_value': old_value,
        #                   'new_value': new_value
        #               })

        #   if changes:
        #       return request.make_json_response(changes)
        #   else:
        #       return request.make_json_response({'message': 'No changes found for this contract'})
        
        except Exception as e:
            return request.make_json_response({'error': str(e)})

    @core.http.rest_route(
        routes=build_route('/fix/contracts'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Contracts'],
            summary='Fix Contract Buyer Numbers',
            description='Updates all contracts to add buyer_number[0] where buyer_id exists and has buyer numbers available.',
        ),
    )
    def fix_contract_buyer_numbers(self, **kw):
        """Fix contract buyer numbers by adding the first available buyer number where buyer_id exists"""
        try:
            # Get and validate user authorization
            user_id = request.httprequest.headers.get('X-User-Id')
            
            if not user_id:
                return request.make_json_response({'error': 'User ID not found in request headers'}, status=401)
            
            user = get_user(user_id)
            
            # Check if user lookup was successful
            if not user.get('isAuthorized', False):
                return request.make_json_response({
                    'error': user.get('error', 'User authorization failed'),
                    'X-User-Id': user_id
                }, status=401)
            
            user_roles = user.get('roles', [])
            
            # Check if user has admin role
            if 'admin' not in user_roles and 'administrator' not in user_roles:
                return request.make_json_response({
                    'error': 'Access denied. Admin role required.',
                    'user_roles': user_roles,
                    'X-User-Id': user_id
                }, status=403)
            
            # User is authorized as admin, proceed with the fix
            updated_count = 0
            skipped_count = 0
            error_count = 0
            already_set_count = 0
            
            # Get all contracts that have a buyer_id but no buyer_number set
            contracts = request.env['consignment.contract'].search([
                ('buyer_id', '!=', False),
                ('buyer_number', '=', False)
            ])
            
            _logger.info(f"Found {len(contracts)} contracts with buyer_id but no buyer_number set")
            
            for contract in contracts:
                try:
                    buyer = contract.buyer_id
                    if buyer and buyer.buyer_number_ids:
                        # Get the first buyer number from the buyer's available numbers
                        first_buyer_number = buyer.buyer_number_ids[0]
                        
                        # Update the contract with the first buyer number
                        contract.write({'buyer_number': first_buyer_number.id})
                        updated_count += 1
                        _logger.info(f"Updated contract {contract.contract_id} with buyer number {first_buyer_number.name}")
                        
                    else:
                        # Buyer exists but has no buyer numbers
                        skipped_count += 1
                        _logger.info(f"Skipped contract {contract.contract_id} - buyer {buyer.name} has no buyer numbers")
                        
                except Exception as contract_error:
                    error_count += 1
                    _logger.error(f"Error processing contract {contract.contract_id}: {str(contract_error)}")
                    continue
            
            # Also check how many contracts already have buyer numbers set
            contracts_with_buyer_numbers = request.env['consignment.contract'].search([
                ('buyer_id', '!=', False),
                ('buyer_number', '!=', False)
            ])
            already_set_count = len(contracts_with_buyer_numbers)
            
            return request.make_json_response({
                'success': True,
                'message': f'Contract buyer number fix completed',
                'updated_contracts': updated_count,
                'skipped_contracts': skipped_count,
                'error_contracts': error_count,
                'already_set_contracts': already_set_count,
                'total_contracts_with_buyers': len(contracts) + already_set_count,
                'executed_by': user.get('name', 'Unknown'),
                'X-User-Id': user_id
            })
            
        except Exception as e:
            _logger.error(f"Error in fix_contract_buyer_numbers: {str(e)}")
            return request.make_json_response({'error': str(e)}, status=500)
