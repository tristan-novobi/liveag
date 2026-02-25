from odoo import models
from odoo.http import request
from odoo.exceptions import AccessDenied

from odoo.addons.liveag_consignment.tools.security import get_user_from_bearer_token


class IrHttp(models.AbstractModel):
	_inherit = 'ir.http'

	@classmethod
	def _auth_method_bearer_token(cls):
		uid = get_user_from_bearer_token()
		if not uid:
			raise AccessDenied()
		request.update_env(user=uid)
