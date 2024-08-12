from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo import _

from datetime import datetime, timedelta

import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    

    def get_dest_analytic_distribution(self, analytic_distribution, dest_company):
        dest_analytic_distribution = {}

        for analytic_account_id, rate in analytic_distribution.items() :
            if analytic_account_id.project_count != 1:
                raise ValidationError(_("Ce compte analytic ne peut pas être traité automatiquement car il n'est pas lié à exactement un projet."))
            project_id = analytic_account_id.project_ids[0] 
            project_outsourcing_link_ids = self.env['project.outsourcing.link'].search([('project_id', '=', project_id.id), ('partner_id', '=', dest_company.partner_id.id)])
            if len(project_outsourcing_link_ids) != 1:
                raise ValidationError(_("Le projet %s n'a pas de lien projet/sous-traitant avec la société %s" % (project_id.name_get(), dest_company.partner_id.name())))
            project_outsourcing_link_id = project_outsourcing_link_ids[0]
            dest_project = project_outsourcing_link_id.get_or_generate_inter_company_mirror_project()
            dest_analytic_distribution[str(dest_project.analytic_account_id.id)] = rate

        return dest_analytic_distribution



    def _prepare_sale_order_line_data(self, purchase_line, dest_company, sale_order):
        new_line = super()._prepare_sale_order_line_data(purchase_line, dest_company, sale_order)
        """
        dest_analytic_distribution = {}
        for analytic_account_id, rate in purchase_line.analytic_distribution.items() :
            if analytic_account_id.project_count != 1:
                raise ValidationError(_("Ce compte analytic ne peut pas être traité automatiquement car il n'est pas lié à exactement un projet."))
            project_id = analytic_account_id.project_ids[0] 
            project_outsourcing_link_ids = self.env['project.outsourcing.link'].search([('project_id', '=', project_id.id), ('partner_id', '=', dest_company.partner_id.id)])
            if len(project_outsourcing_link_ids) != 1:
                raise ValidationError(_("Le projet %s n'a pas de lien projet/sous-traitant avec la société %s" % (project_id.name_get(), dest_company.partner_id.name())))
            project_outsourcing_link_id = project_outsourcing_link_ids[0]
            dest_project = project_outsourcing_link_id.get_or_generate_inter_company_mirror_project()
            dest_analytic_distribution[str(dest_project.analytic_account_id.id)] = rate
        new_line.analytic_distribution = dest_analytic_distribution
        """
        new_line.analytic_distribution = self.get_dest_analytic_distribution(purchase_line.analytic_distribution, dest_company)

        return new_line