# -*- coding: utf-8 -*-
# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json
import logging
from typing import Dict, List, Optional, Any, Tuple

from odoo import http
from odoo.http import request
from odoo.models import Model 
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import consteq

from odoo.addons.liveag_muk_rest.tools.http import build_route
from odoo.addons.liveag_muk_rest import core
from odoo.addons.liveag_api.controllers.liveag import LiveAgController

_logger = logging.getLogger(__name__)

class LiveAgDeliveryController(LiveAgController):
    """Controller for managing Consignment Delivery endpoints."""

    _MODEL = 'consignment.delivery'

    def _make_error_response(self, error: str, status_code: int = 400, **kwargs) -> Dict:
        """Create consistent error response format."""
        response_data = {
            'success': False,
            'error': error
        }
        response_data.update(kwargs)
        return request.make_json_response(response_data, status=status_code)

    def _make_success_response(self, data: Any, status_code: int = 200, **kwargs) -> Dict:
        """Create consistent success response format."""
        response_data = {
            'success': True,
            'data': data
        }
        response_data.update(kwargs)
        return request.make_json_response(response_data, status=status_code)

    def _parse_request_data(self) -> Dict:
        """Parse JSON data from the request body."""
        try:
            return request.get_json_data()
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format in request body.")
        except Exception as e:
            raise ValueError(f"Error parsing request data: {str(e)}")

    def _get_record(self, record_id: int) -> Optional[Model]:
        """Fetch a single delivery record by ID, handling not found cases."""
        record = request.env[self._MODEL].browse(record_id).exists()
        if not record:
            raise ValueError(f"Delivery record with ID {record_id} not found.")
        return record

    @core.http.rest_route(
        routes=build_route('/deliveries'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Deliveries'],
            summary='List Deliveries',
            description='Retrieves a list of consignment deliveries based on optional filters.',
            parameters=[
                {
                    'name': 'domain',
                    'in': 'query',
                    'description': 'Odoo domain filter (JSON string)',
                    'schema': {'type': 'string'}
                },
                {
                    'name': 'fields',
                    'in': 'query',
                    'description': 'List of fields to return (comma-separated)',
                    'schema': {'type': 'string'}
                },
                {
                    'name': 'limit',
                    'in': 'query',
                    'description': 'Maximum number of records to return',
                    'schema': {'type': 'integer'}
                },
                {
                    'name': 'offset',
                    'in': 'query',
                    'description': 'Number of records to skip',
                    'schema': {'type': 'integer'}
                },
                {
                    'name': 'order',
                    'in': 'query',
                    'description': 'Sort order (e.g., "name asc")',
                    'schema': {'type': 'string'}
                }
            ]
        ),
    )
    def list_deliveries(self, domain: Optional[str] = None, fields: Optional[str] = None,
                        limit: Optional[int] = None, offset: Optional[int] = 0,
                        order: Optional[str] = None, **kw) -> Dict:
        """Lists consignment deliveries."""
        try:
            search_domain = json.loads(domain) if domain else []
            field_list = fields.split(',') if fields else None
            records = request.env[self._MODEL].search_read(
                domain=search_domain,
                fields=field_list,
                limit=limit,
                offset=offset,
                order=order
            )
            count = request.env[self._MODEL].search_count(search_domain)
            return self._make_success_response(records, total_count=count)
        except (AccessError, UserError, ValidationError) as e:
            return self._make_error_response(str(e), status_code=403 if isinstance(e, AccessError) else 400)
        except json.JSONDecodeError:
            return self._make_error_response("Invalid JSON format for domain.", status_code=400)
        except Exception as e:
            _logger.error("Error listing deliveries: %s", str(e), exc_info=True)
            return self._make_error_response(f"An unexpected error occurred: {str(e)}", status_code=500)

    @core.http.rest_route(
        routes=build_route('/deliveries/<int:delivery_id>'),
        methods=['GET'],
        protected=True,
        docs=dict(
            tags=['Deliveries'],
            summary='Get Delivery Details',
            description='Retrieves details for a specific consignment delivery.',
            parameters=[
                {
                    'name': 'delivery_id',
                    'in': 'path',
                    'required': True,
                    'description': 'ID of the delivery record',
                    'schema': {'type': 'integer'}
                },
                {
                    'name': 'fields',
                    'in': 'query',
                    'description': 'List of fields to return (comma-separated)',
                    'schema': {'type': 'string'}
                }
            ]
        ),
    )
    def get_delivery(self, delivery_id: int, fields: Optional[str] = None, **kw) -> Dict:
        """Gets details of a specific consignment delivery."""
        try:
            record = self._get_record(delivery_id)
            field_list = fields.split(',') if fields else None
            data = record.read(field_list)[0] # read returns a list
            return self._make_success_response(data)
        except (AccessError, UserError, ValidationError, ValueError) as e:
            status_code = 404 if isinstance(e, ValueError) else (403 if isinstance(e, AccessError) else 400)
            return self._make_error_response(str(e), status_code=status_code)
        except Exception as e:
            _logger.error("Error getting delivery %d: %s", delivery_id, str(e), exc_info=True)
            return self._make_error_response(f"An unexpected error occurred: {str(e)}", status_code=500)

    @core.http.rest_route(
        routes=build_route('/deliveries'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Deliveries'],
            summary='Create Delivery',
            description='Creates a new consignment delivery record.',
            requestBody={
                'description': 'Delivery data',
                'required': True,
                'content': {
                    'application/json': {
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'vals': {
                                    'type': 'object',
                                    'description': 'Dictionary of values for the new delivery record'
                                }
                            }
                        }
                    }
                }
            }
        ),
    )
    def create_delivery(self, **kw) -> Dict:
        """Creates a new consignment delivery."""
        try:
            data = self._parse_request_data()
            vals = data.get('vals')
            if not vals or not isinstance(vals, dict):
                return self._make_error_response("Missing or invalid 'vals' in request body.", status_code=400)

            new_record = request.env[self._MODEL].create(vals)
            return self._make_success_response({'id': new_record.id, 'name': new_record.name}, status_code=201)
        except (AccessError, UserError, ValidationError, ValueError) as e:
            status_code = 403 if isinstance(e, AccessError) else 400
            return self._make_error_response(str(e), status_code=status_code)
        except Exception as e:
            _logger.error("Error creating delivery: %s", str(e), exc_info=True)
            return self._make_error_response(f"An unexpected error occurred: {str(e)}", status_code=500)

    @core.http.rest_route(
        routes=build_route('/deliveries/<int:delivery_id>'),
        methods=['PUT'],
        protected=True,
        docs=dict(
            tags=['Deliveries'],
            summary='Update Delivery',
            description='Updates an existing consignment delivery record.',
            parameters=[
                {
                    'name': 'delivery_id',
                    'in': 'path',
                    'required': True,
                    'description': 'ID of the delivery record to update',
                    'schema': {'type': 'integer'}
                }
            ],
            requestBody={
                'description': 'Delivery data to update',
                'required': True,
                'content': {
                    'application/json': {
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'vals': {
                                    'type': 'object',
                                    'description': 'Dictionary of values to update'
                                }
                            }
                        }
                    }
                }
            }
        ),
    )
    def update_delivery(self, delivery_id: int, **kw) -> Dict:
        """Updates an existing consignment delivery."""
        try:
            record = self._get_record(delivery_id)
            data = self._parse_request_data()
            vals = data.get('vals')
            if not vals or not isinstance(vals, dict):
                return self._make_error_response("Missing or invalid 'vals' in request body.", status_code=400)

            record.write(vals)
            return self._make_success_response({'id': record.id, 'message': 'Delivery updated successfully.'})
        except (AccessError, UserError, ValidationError, ValueError) as e:
            status_code = 404 if isinstance(e, ValueError) else (403 if isinstance(e, AccessError) else 400)
            return self._make_error_response(str(e), status_code=status_code)
        except Exception as e:
            _logger.error("Error updating delivery %d: %s", delivery_id, str(e), exc_info=True)
            return self._make_error_response(f"An unexpected error occurred: {str(e)}", status_code=500)

    @core.http.rest_route(
        routes=build_route('/deliveries/<int:delivery_id>'),
        methods=['DELETE'],
        protected=True,
        docs=dict(
            tags=['Deliveries'],
            summary='Delete Delivery',
            description='Deletes a specific consignment delivery record.',
            parameters=[
                {
                    'name': 'delivery_id',
                    'in': 'path',
                    'required': True,
                    'description': 'ID of the delivery record to delete',
                    'schema': {'type': 'integer'}
                }
            ]
        ),
    )
    def delete_delivery(self, delivery_id: int, **kw) -> Dict:
        """Deletes a consignment delivery."""
        try:
            record = self._get_record(delivery_id)
            record.unlink()
            # Return 204 No Content on successful deletion is standard REST practice
            return request.make_json_response({}, status=204)
        except (AccessError, UserError, ValidationError, ValueError) as e:
            status_code = 404 if isinstance(e, ValueError) else (403 if isinstance(e, AccessError) else 400)
            # UserError often implies a business logic constraint preventing deletion (e.g., linked records)
            error_message = str(e)
            if isinstance(e, UserError):
                error_message = f"Cannot delete delivery: {error_message}"
            return self._make_error_response(error_message, status_code=status_code)
        except Exception as e:
            _logger.error("Error deleting delivery %d: %s", delivery_id, str(e), exc_info=True)
            return self._make_error_response(f"An unexpected error occurred: {str(e)}", status_code=500)

    # --- Action Endpoints ---

    def _execute_action(self, delivery_id: int, action_name: str) -> Dict:
        """Generic helper to execute an action on a delivery record."""
        try:
            record = self._get_record(delivery_id)
            action_method = getattr(record, action_name, None)
            if not callable(action_method):
                _logger.warning("Action '%s' not found or not callable on %s", action_name, self._MODEL)
                return self._make_error_response(f"Action '{action_name}' is not available.", status_code=400)

            action_method()
            # Fetch updated state after action
            updated_state = record.read(['state'])[0]['state']
            return self._make_success_response({
                'id': record.id,
                'state': updated_state,
                'message': f'Delivery action {action_name} executed successfully.'
            })
        except (AccessError, UserError, ValidationError, ValueError) as e:
            status_code = 404 if isinstance(e, ValueError) else (403 if isinstance(e, AccessError) else 400)
            return self._make_error_response(str(e), status_code=status_code)
        except Exception as e:
            _logger.error("Error executing action %s on delivery %d: %s", action_name, delivery_id, str(e), exc_info=True)
            return self._make_error_response(f"An unexpected error occurred: {str(e)}", status_code=500)

    @core.http.rest_route(
        routes=build_route('/deliveries/<int:delivery_id>/confirm'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Deliveries Actions'],
            summary='Confirm Delivery',
            description='Executes the confirm action on a specific delivery.',
            parameters=[{
                'name': 'delivery_id', 'in': 'path', 'required': True,
                'description': 'ID of the delivery to confirm', 'schema': {'type': 'integer'}
            }]
        )
    )
    def confirm_delivery_action(self, delivery_id: int, **kw):
        """Confirms the delivery."""
        return self._execute_action(delivery_id, 'action_confirm')

    @core.http.rest_route(
        routes=build_route('/deliveries/<int:delivery_id>/deliver'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Deliveries Actions'],
            summary='Mark as Delivered',
            description='Executes the deliver action on a specific delivery.',
             parameters=[{
                'name': 'delivery_id', 'in': 'path', 'required': True,
                'description': 'ID of the delivery to mark as delivered', 'schema': {'type': 'integer'}
            }]
       )
    )
    def deliver_delivery_action(self, delivery_id: int, **kw):
        """Marks the delivery as delivered."""
        return self._execute_action(delivery_id, 'action_deliver')

    @core.http.rest_route(
        routes=build_route('/deliveries/<int:delivery_id>/cancel'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Deliveries Actions'],
            summary='Cancel Delivery',
            description='Executes the cancel action on a specific delivery.',
             parameters=[{
                'name': 'delivery_id', 'in': 'path', 'required': True,
                'description': 'ID of the delivery to cancel', 'schema': {'type': 'integer'}
            }]
       )
    )
    def cancel_delivery_action(self, delivery_id: int, **kw):
        """Cancels the delivery."""
        return self._execute_action(delivery_id, 'action_cancel')

    @core.http.rest_route(
        routes=build_route('/deliveries/<int:delivery_id>/reset-to-draft'),
        methods=['POST'],
        protected=True,
        docs=dict(
            tags=['Deliveries Actions'],
            summary='Reset to Draft',
            description='Executes the reset to draft action on a specific delivery.',
             parameters=[{
                'name': 'delivery_id', 'in': 'path', 'required': True,
                'description': 'ID of the delivery to reset to draft', 'schema': {'type': 'integer'}
            }]
       )
    )
    def draft_delivery_action(self, delivery_id: int, **kw):
        """Resets the delivery to draft state."""
        return self._execute_action(delivery_id, 'action_draft')
