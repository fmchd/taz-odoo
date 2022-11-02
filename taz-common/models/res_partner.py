# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo import _

import logging
_logger = logging.getLogger(__name__)

class tazResPartner(models.Model):
     _inherit = "res.partner"
     
     @api.depends('child_ids')
     def _compute_child_mail_address_domain_list(self):
         domain_list = []
         for child in self.child_ids:
             if child.email:
                 domain = child.email.split("@")[1]
                 if ',' in domain :
                     continue
                 if domain and domain not in domain_list:
                     domain_list.append(domain)
         self.child_mail_address_domain_list = ','.join(domain_list)

     first_name = fields.Char(string="Prénom")
     parent_industry_id = fields.Many2one('res.partner.industry', string='Secteur du parent', related='parent_id.industry_id', store=True)

     business_action_ids = fields.One2many('taz.business_action', 'partner_id') 
     child_mail_address_domain_list = fields.Char('Liste domaines mail', compute=_compute_child_mail_address_domain_list, store=True)

     customer_book_goal_ids = fields.One2many('taz.customer_book_goal', 'partner_id')  
     customer_book_followup_ids = fields.One2many('taz.customer_book_followup', 'partner_id')  

     def name_get(self):
         res = []
         for rec in self:
             if (rec.is_company == False):
                 res.append((rec.id, "%s %s (%s)" % (rec.first_name or "", rec.name or "", rec.parent_id.name or "")))
             else:
                 res.append((rec.id, "%s" % rec.name))
         return res

     @api.constrains('email')
     def _check_email(self):
         count_email = self.search_count([('email', '=', self.email), ('is_company', '=', False), ('type', '=', 'contact')])
         if count_email > 1 and self.email is not False:
             raise ValidationError(_('Cette adresse email est déjà utilisée sur une autre fiche contact. Enregistrement impossible (il ne faudrait pas créer des doublons de contact ;-)) !'))

     @api.constrains('first_name')
     def _check_firstname(self):
         if (self.is_company == False and self.type=='contact'):
             if not(self.first_name):
                raise ValidationError(_('Vous devez indiquer un prénom et un nom.'))

     @api.constrains('name')
     def _check_name(self):
         if (self.is_company == True and self.type=='contact'):
             count_name = self.search_count([('name', '=ilike', self.name), ('is_company', '=', True), ('type', '=', 'contact')])
             if count_name > 1 and self.name is not False:
                raise ValidationError(_('Cette nom est déjà utilisé sur une autre fiche entreprise. Enregistrement impossible (il ne faudrait pas créer des doublons d\'entreprises ;-)) !'))


     @api.onchange('email', 'parent_id')
     def _onchange_email_parent_id(self):
         _logger.info('TRIGGER onchange_email_parent_id')
         if (self.is_company == False and self.type=='contact'):
             _logger.info(self._origin.parent_id)
             _logger.info(self.parent_id)
             #_compute_child_mail_address_domain_list()
             if self.email:
                 domain = self.email.split("@")[1] 
                 lc = self.env['res.partner'].search([('child_mail_address_domain_list', 'ilike', domain), ('is_company', '=', True)], order="write_date desc")
                 #Mise à jour des _compute_child_mail_address_domain_list
                 #self._origin.parent_id._compute_child_mail_address_domain_list()
                 #self.parent_id._compute_child_mail_address_domain_list()
                 if len(lc) > 0:
                     if self.parent_id:
                         coherent = False
                         for c in lc:
                            if self.parent_id == c:
                                coherent = True
                         if coherent == False :
                            return {
                                'warning': {
                                    'title': _("Attention : est-ce la bonne entreprise ?"),
                                    'message': _("Le domaine de l'adresse email est présent dans les contacts d'une autre entreprise... mais pas celle sélectionnée. N'y aurait-il pas un soucis quelque part ?")
                                    }
                                }
                     else:
                         self.parent_id = lc[0].id

     @api.onchange('first_name', 'name')
     def _onchange_name(self):
         if (self.first_name and self.name):
             if (self.is_company == False and self.type=='contact'):
                 count_name = self.search([('first_name', '=ilike', self.first_name), ('name', '=ilike', self.name), ('is_company', '=', False), ('type', '=', 'contact')])
                 if len(count_name) > 0:
                    liste_match = []
                    for i in count_name :
                         match = _("ID = %s, Entreprise = %s" % (str(i.id), i.parent_id.name or ""))
                         liste_match.append(match)
                    return {
                        'warning': {
                            'title': _("Attention : possibilité de doublons !"),
                            'message': _("%s autre(s) contact(s) a(ont) le même nom et le même prénom, vérifiez bien que vous n'êtes pas en train de créer un contact en doublon ! \n    => S'il s'agit d'un réel homonyme, vous pouvez continuer. \n    => S'il s'agit d'un doublon, merci de cliquer sur le bouton d'annulation (en haut de l'écran, à droit de 'Nouveau') \n\n\nListe des contacts :\n%s" % (str(count_name), '\n'.join(liste_match) or ""))
                                  }
                    } 


     @api.onchange('parent_id')
     def onchange_parent_id(self):
        _logger.info('TRIGGER onchange_parent_id')
        # return values in result, as this method is used by _fields_sync()
        if not self.parent_id:
            return
        result = {}
        partner = self._origin
        #if partner.parent_id and partner.parent_id != self.parent_id:
        #    result['warning'] = {
        #        'title': _('Warning'),
        #        'message': _('Changing the company of a contact should only be done if it '
        #                     'was never correctly set. If an existing contact starts working for a new '
        #                     'company then a new contact should be created under that new '
        #                     'company. You can use the "Discard" button to abandon this change.')}
        if partner.type == 'contact' or self.type == 'contact':
            # for contacts: copy the parent address, if set (aka, at least one
            # value is set in the address: otherwise, keep the one from the
            # contact)
            address_fields = self._address_fields()
            if any(self.parent_id[key] for key in address_fields):
                def convert(value):
                    return value.id if isinstance(value, models.BaseModel) else value
                result['value'] = {key: convert(self.parent_id[key]) for key in address_fields}
        return result

     #@api.model
     #def create(self, vals):
     #   if not vals.get("parent_id"):
     #       vals["parent_id"] = self._context.get("default_parent_id")
     #   return super().create(vals)



#Wizzard de fusion / déduplication :
    #https://github.com/odoo/odoo/blob/fa58938b3e2477f0db22cc31d4f5e6b5024f478b/odoo/addons/base/wizard/base_partner_merge.py
    #https://github.com/odoo/odoo/blob/fa58938b3e2477f0db22cc31d4f5e6b5024f478b/odoo/addons/base/wizard/base_partner_merge_views.xml
