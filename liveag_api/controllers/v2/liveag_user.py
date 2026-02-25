import json
import logging
from typing import Dict, List, Optional, Any, Tuple

from odoo import http
from odoo.http import request
from odoo.models import Model

from odoo.addons.liveag_muk_rest.tools.http import build_route
from odoo.addons.liveag_muk_rest import core
from odoo.addons.liveag_api.controllers.liveag import LiveAgController

_logger = logging.getLogger(__name__)

class LiveAgUsersController(LiveAgController):
    """Controller for managing LiveAg user-related endpoints."""

    def _make_error_response(self, error: str, status: bool = False, **kwargs) -> Dict:
        """Create consistent error response format.
        
        Args:
            error: Error message
            status: Success status
            **kwargs: Additional response fields
            
        Returns:
            Error response dictionary
        """
        response = {
            'success': status,
            'error': error
        }
        response.update(kwargs)
        return request.make_json_response(response)

    def _get_partner_and_user(self, clerk_user_id: str) -> Tuple[Optional[Model], Optional[Model]]:
        """Get partner and user records from clerk_user_id.
        
        Args:
            clerk_user_id: Unique Clerk user identifier
            
        Returns:
            Tuple of (partner, user) records
        """
        if not clerk_user_id:
            return None, None
            
        partner = request.env['res.partner'].search(
            [('clerk_user_id', '=', clerk_user_id)], 
            limit=1
        )
        user = partner.user_ids[0] if partner and partner.user_ids else None
        return partner, user

    def _validate_partner_user(self, clerk_user_id: str) -> Tuple[Optional[Model], Optional[Model]]:
        """Validate and get partner and user records, with error handling.
        
        Args:
            clerk_user_id: Unique Clerk user identifier
            
        Returns:
            Tuple of (partner, user) records
            
        Raises:
            ValueError: If partner or user not found
        """
        if not clerk_user_id:
            raise ValueError('Missing required parameter: clerk_user_id')
            
        partner, user = self._get_partner_and_user(clerk_user_id)
        if not partner:
            raise ValueError('No partner found with this clerk_user_id')
        if not user:
            raise ValueError('No user found for this partner')
            
        return partner, user

    @core.http.rest_route(
        routes=build_route('/users/create_clerkid'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='Create User',
            description='Creates a new user with Clerk integration.',
        ),
    )
    def create_user(self, **kw) -> Dict:
        """Creates a new user with Clerk integration."""
        try:
            vals = request.params.get('vals')
            if not vals:
                return self._make_error_response('Missing required parameter: vals')

            try:
                creation_values = json.loads(vals)
                self._validate_creation_values(creation_values)
                
                # Check for existing user by login
                if user := self._check_existing_user(creation_values):
                    return self._make_error_response(
                        'User already exists with this login',
                        user_id=user.id
                    )

                # Check for existing user by clerk_user_id
                if partner := self._check_existing_clerk_user(creation_values):
                    return self._make_error_response(
                        'User already exists with this clerk_user_id',
                        user_id=partner.user_ids[0].id if partner.user_ids else None
                    )

                user = self._create_user_with_groups(creation_values)
                if user and user.partner_id:
                    user.partner_id.write({
                        'clerk_user_id': creation_values.get('clerk_user_id')
                    })
                    
                return request.make_json_response({
                    'success': True,
                    'user_id': user.id,
                    'message': 'Portal user created successfully with Consignment access'
                })
                    
            except json.JSONDecodeError as e:
                return self._make_error_response(f'Invalid JSON format: {str(e)}')

        except Exception as e:
            _logger.error("Error creating user: %s", str(e))
            return self._make_error_response(str(e))

    def _validate_creation_values(self, values: Dict) -> None:
        """Validate user creation values.
        
        Args:
            values: Dictionary of creation values
            
        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ['login', 'name', 'clerk_user_id']
        missing_fields = [field for field in required_fields if not values.get(field)]
        if missing_fields:
            raise ValueError(f'Missing required fields: {", ".join(missing_fields)}')

    def _check_existing_user(self, values: Dict) -> Optional[Model]:
        """Check if user exists with given login.
        
        Args:
            values: Dictionary of creation values
            
        Returns:
            Existing user record if found, None otherwise
        """
        return request.env['res.users'].search([
            ('login', '=', values.get('login'))
        ], limit=1)

    def _check_existing_clerk_user(self, values: Dict) -> Optional[Model]:
        """Check if partner exists with given clerk_user_id.
        
        Args:
            values: Dictionary of creation values
            
        Returns:
            Existing partner record if found, None otherwise
        """
        return request.env['res.partner'].search([
            ('clerk_user_id', '=', values.get('clerk_user_id'))
        ], limit=1)

    def _create_user_with_groups(self, values: Dict) -> Model:
        """Create user with portal and consignment access.
        
        Args:
            values: Dictionary of creation values
            
        Returns:
            Created user record
        """
        portal_group = request.env.ref('base.group_portal')
        consignment_user_group = request.env.ref('liveag_consignment.group_consignment_user')
        
        return request.env['res.users'].create({
            'login': values.get('login'),
            'name': values.get('name'),
            'email': values.get('email') or values.get('login'),
            'group_ids': [(6, 0, [portal_group.id, consignment_user_group.id])],
            'active': True
        })

    @core.http.rest_route(
        routes=build_route('/users/assign-contact-types'),
        methods=['PUT'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='Assign Contact Types',
            description='Assigns contact types to a user based on their Clerk ID.',
        ),
    )
    def assign_contact_types(self, **kw) -> Dict:
        """Assigns contact types to a user based on their Clerk ID."""
        try:
            clerk_user_id = request.params.get('clerk_user_id')
            contact_type_ids = request.params.get('contact_type_ids')

            if not clerk_user_id:
                return self._make_error_response('Missing required parameter: clerk_user_id')
            if not contact_type_ids:
                return self._make_error_response('Missing required parameter: contact_type_ids')

            partner, _ = self._validate_partner_user(clerk_user_id)
            return self._update_partner_contact_types(partner, contact_type_ids, clerk_user_id)

        except ValueError as e:
            return self._make_error_response(str(e))
        except Exception as e:
            _logger.error("Error assigning contact types: %s", str(e))
            return self._make_error_response(str(e))

    @core.http.rest_route(
        routes=build_route('/users/update-contact-types'),
        methods=['PUT'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='Update Contact Types',
            description='Updates contact types for a user based on their Clerk ID using JSON payload.',
        ),
    )
    def update_contact_types(self, **kw) -> Dict:
        """Updates contact types for a user based on their Clerk ID using JSON payload."""
        try:
            vals = request.params.get('vals')
            if not vals:
                return self._make_error_response('Missing required parameter: vals')

            try:
                data = json.loads(vals)
                clerk_user_id = data.get('clerk_user_id')
                contact_type_ids = data.get('contact_type_ids')
                
                if not clerk_user_id:
                    return self._make_error_response('Missing required field: clerk_user_id')
                elif contact_type_ids is None:  # Allow empty list but not None
                    return self._make_error_response('Missing required field: contact_type_ids')
                
                partner, _ = self._validate_partner_user(clerk_user_id)
                return self._process_contact_types_update(partner, contact_type_ids, clerk_user_id)
                    
            except json.JSONDecodeError as e:
                return self._make_error_response(f'Invalid JSON format: {str(e)}')
                
        except ValueError as e:
            return self._make_error_response(str(e))
        except Exception as e:
            _logger.error("Error updating contact types: %s", str(e))
            return self._make_error_response(str(e))

    def _update_partner_contact_types(self, partner: Model, contact_type_ids: str, clerk_user_id: str) -> Dict:
        """Update partner's contact types from comma-separated string.
        
        Args:
            partner: Partner record
            contact_type_ids: Comma-separated string of contact type IDs
            clerk_user_id: Clerk user identifier
            
        Returns:
            Response dictionary
        """
        try:
            type_ids = [int(x) for x in contact_type_ids.split(',')]
            contact_types = request.env['res.contact.type'].browse(type_ids)
            
            if not all(contact_types):
                return self._make_error_response('One or more contact types not found')

            partner.write({'contact_type_ids': [(6, 0, type_ids)]})
            updated_types = [{'id': ct.id, 'name': ct.name} for ct in partner.contact_type_ids]
            
            return request.make_json_response({
                'success': True,
                'message': 'Contact types updated successfully',
                'partner_id': partner.id,
                'clerk_user_id': clerk_user_id,
                'contact_types': updated_types
            })
            
        except ValueError:
            return self._make_error_response('Invalid contact type IDs format')

    def _process_contact_types_update(self, partner: Model, contact_type_ids: List[int], clerk_user_id: str) -> Dict:
        """Process contact types update from list.
        
        Args:
            partner: Partner record
            contact_type_ids: List of contact type IDs
            clerk_user_id: Clerk user identifier
            
        Returns:
            Response dictionary
        """
        if not contact_type_ids:
            partner.write({'contact_type_ids': [(6, 0, [])]})
            return request.make_json_response({
                'success': True,
                'message': 'All contact types removed successfully',
                'partner_id': partner.id,
                'clerk_user_id': clerk_user_id,
                'contact_types': []
            })

        contact_types = request.env['res.contact.type'].browse(contact_type_ids)
        existing_ids = contact_types.exists().ids
        
        if len(existing_ids) != len(contact_type_ids):
            missing_ids = set(contact_type_ids) - set(existing_ids)
            return self._make_error_response(
                f'Contact types not found: {list(missing_ids)}'
            )
        
        partner.write({'contact_type_ids': [(6, 0, existing_ids)]})
        updated_types = [{
            'id': ct.id,
            'name': ct.name
        } for ct in partner.contact_type_ids]
        
        return request.make_json_response({
            'success': True,
            'message': 'Contact types updated successfully',
            'partner_id': partner.id,
            'clerk_user_id': clerk_user_id,
            'contact_types': updated_types
        })

    @core.http.rest_route(
        routes=build_route('/users/check-record-rules'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='Check Record Rules',
            description='Check record rules for a model that apply to the user based on their Clerk ID.',
        ),
    )
    def check_record_rules(self, **kw) -> Dict:
        """Check record rules for a model that apply to the user based on their Clerk ID."""
        try:
            clerk_user_id = request.params.get('clerk_user_id')
            model = request.params.get('model')
            
            if not model:
                return self._make_error_response('Missing required parameter: model')
            
            partner, user = self._validate_partner_user(clerk_user_id)
            
            # Use sudo() to avoid access rights issues
            rules = request.env['ir.rule'].sudo().search([('model_id.model', '=', model)])
            rule_info = [self._prepare_rule_data(rule) for rule in rules]
            
            return request.make_json_response({
                'success': True,
                'clerk_user_id': clerk_user_id,
                'user_id': user.id,
                'model': model,
                'rules': rule_info
            })
            
        except ValueError as e:
            return self._make_error_response(str(e))
        except Exception as e:
            _logger.error("Error checking record rules: %s", str(e))
            return self._make_error_response(str(e))

    def _prepare_rule_data(self, rule: Model) -> Dict:
        """Prepare record rule data for response.
        
        Args:
            rule: Record rule
            
        Returns:
            Rule data dictionary
        """
        return {
            'id': rule.id,
            'name': rule.name,
            'domain_force': rule.domain_force,
            'groups': [{'id': g.id, 'name': g.name} for g in rule.groups],
            'permissions': {
                'read': rule.perm_read,
                'write': rule.perm_write,
                'create': rule.perm_create,
                'unlink': rule.perm_unlink
            }
        }

    @core.http.rest_route(
        routes=build_route('/users/check-groups'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='Check User Groups',
            description='Check which groups a user belongs to based on their Clerk ID.',
        ),
    )
    def check_user_groups(self, **kw) -> Dict:
        """Check which groups a user belongs to based on their Clerk ID."""
        try:
            clerk_user_id = request.params.get('clerk_user_id')
            partner, user = self._validate_partner_user(clerk_user_id)
            
            groups = [self._prepare_group_data(g) for g in user.group_ids]
            return request.make_json_response({
                'success': True,
                'clerk_user_id': clerk_user_id,
                'user_id': user.id,
                'groups': groups
            })
            
        except ValueError as e:
            return self._make_error_response(str(e))
        except Exception as e:
            _logger.error("Error checking user groups: %s", str(e))
            return self._make_error_response(str(e))

    def _prepare_group_data(self, group: Model) -> Dict:
        """Prepare group data for response.
        
        Args:
            group: Group record
            
        Returns:
            Group data dictionary
        """
        return {
            'id': group.id,
            'name': group.name,
            'full_name': group.full_name,
            'category_id': group.category_id.name if group.category_id else None
        }

    @core.http.rest_route(
        routes=build_route('/users/clerkid-contact-types'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Users'],
            summary='List Contact Types',
            description='Get contact types for a user based on their Clerk ID.',
        ),
    )
    def get_contact_types(self, **kw) -> Dict:
        """Get contact types for a user based on their Clerk ID."""
        try:
            clerk_user_id = request.params.get('clerk_user_id')
            partner, _ = self._validate_partner_user(clerk_user_id)
            
            contact_types = [self._prepare_contact_type_data(ct) for ct in partner.contact_type_ids]
            return request.make_json_response({
                'success': True,
                'clerk_user_id': clerk_user_id,
                'partner_id': partner.id,
                'contact_types': contact_types
            })
            
        except ValueError as e:
            return self._make_error_response(str(e))
        except Exception as e:
            _logger.error("Error getting contact types: %s", str(e))
            return self._make_error_response(str(e))

    def _prepare_contact_type_data(self, contact_type: Model) -> Dict:
        """Prepare contact type data for response.
        
        Args:
            contact_type: Contact type record
            
        Returns:
            Contact type data dictionary
        """
        return {
            'id': contact_type.id,
            'name': contact_type.name
        }
