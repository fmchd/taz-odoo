from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo import _

import logging
_logger = logging.getLogger(__name__)


class event(models.Model):
    _inherit = "event.event"


    def _get_registration_form_url(self):
        for rec in self :
            if rec.id :
                #url = rec._notify_get_action_link('controller', controller='/eventlight/'+str(rec.id)+'/registration/new')
                web_base_url = self.env['ir.config_parameter'].sudo().get_param("web.base.url")
                url = web_base_url + '/eventlight/' + str(rec.id) + '/registration/new'
                rec.registration_form_url = url
            else:
                rec.registration_form_url = False

    registration_form_url = fields.Char("URL du formulaire d'inscription", compute=_get_registration_form_url)
    description_web_form = fields.Html("Bloc HTML affiché sur le formulaire d'inscription")
