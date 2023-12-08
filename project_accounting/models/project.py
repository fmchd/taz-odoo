from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo import _

from datetime import datetime, timedelta, date
import json

import logging
_logger = logging.getLogger(__name__)

from bokeh.plotting import figure
from bokeh.embed import components
import json
import pandas as pd
from bokeh.models import Label, Title, NumeralTickFormatter, Band
import time
import locale
locale.setlocale(locale.LC_ALL, 'fr_FR')

class projectAccountProject(models.Model):
    _inherit = "project.project"
    _order = "number desc"
    _sql_constraints = [
        ('number_uniq', 'UNIQUE (number)',  "Impossible d'enregistrer deux projets avec le même numéro.")
    ]

    @api.model_create_multi
    def create(self, vals_list):
        #_logger.info('---- MULTI create project from accounting_project')
        projects = self.browse()
        for vals in vals_list:
            vals['number'] = self.env['ir.sequence'].next_by_code('project.project') or ''
            vals['state_last_change_date'] = datetime.today()
            #_logger.info('Numéro de projet auto : %s' % str(vals['number']))
            projects |= super().create(vals)
        return projects

    def name_get(self):
        res = []
        for rec in self:
            display_name = "%s %s" % (rec.number or "", rec.name or "")
            if rec.partner_id : 
                display_name += "("+str(rec.partner_id.name)+")"
            res.append((rec.id, display_name))
        return res

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        if name :
            args += ['|', ('name', operator, name), ('number', operator, name)]
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)


    def get_book_by_year(self, year):
        #_logger.info('-- RES.PARTNER get_book_by_year')
        for book_period_id in self.book_period_ids:
            if book_period_id.reference_period == str(year):
                return book_period_id.period_project_book
        return 0.0

    #inspiré de https://github.com/odoo/odoo/blob/fa58938b3e2477f0db22cc31d4f5e6b5024f478b/addons/hr_timesheet/models/hr_timesheet.py#L116
    @api.depends('project_director_employee_id')
    def _compute_user_id(self):
        for rec in self:
            rec.user_id = rec.project_director_employee_id.user_id if rec.project_director_employee_id else False

    def write(self, vals):
        #_logger.info('----- projet WRITE odooID=%s' % str(self.id))
        #_logger.info(vals)
        for record in self :
            if 'stage_id' in vals.keys():
                #_logger.info('stage ID est dans le dic vals')
                vals['state_last_change_date'] = datetime.today()
                stage_id = self.env['project.project.stage'].browse(vals['stage_id'])
                if stage_id.state == 'closed' :
                    is_closable, error_message = record.is_closable(stage_id)
                    if not is_closable :
                        raise ValidationError(_(error_message))
        return super().write(vals)

    """
    def corriger_vendor_facture(self, stage_id):
        self.ensure_one()
        for invoice in self.env['account.move'].search([]) :
            if invoice.invoice_user_id.id not in [1, 2]:
                _logger.info(invoice.invoice_user_id.id)
                continue
            project_id = None
            for line in invoice.invoice_line_ids :
                if len(line.rel_project_ids) > 0:
                    project_id = line.rel_project_ids[0]
                    break
            if project_id and project_id.user_id:
                invoice.invoice_user_id = project_id.user_id.id
                self.env.cr.commit()
        _logger.info(' ==================== FIN revue invoice.invoice_user_id')

    def corriger_vendor_PO(self):
        self.ensure_one()
        for purchase_order in self.env['purchase.order'].search([]) :
            if purchase_order.user_id.id not in [1, 2, 105]:
                _logger.info(purchase_order.user_id.id)
                continue
            project_id = None
            for line in purchase_order.order_line :
                if len(line.rel_project_ids) > 0:
                    project_id = line.rel_project_ids[0]
                    break
            if project_id and project_id.user_id:
                purchase_order.user_id = project_id.user_id.id
                self.env.cr.commit()
        _logger.info(' ==================== FIN revue purchase_order.user_id')
    """

    def is_closable(self, stage_id):
        self.ensure_one()
        #_logger.info('----- is_closable ID odoo = %s' % str(self.id))

        error_message = "Impossible de cloturer/annuler le projet %s :\n" % (str(self.number))
        is_closable = True
        self.compute()
        self.compute_has_provision_running()

        #_logger.info('----- stage_id.name %s' % str(stage_id.name))

        if "Termin" in stage_id.name: #TODO : rendre plus robuste cette condition (si le nom du statut change ou que son ID change...)
            if not (self.env.user.has_group('account.group_account_user') or self.env.user.has_group('account.group_account_manager')):
                raise ValidationError(_("Seul un ADV peut paser un projet au statut Temriné."))
            if not(self.book_validation_employee_id):
                is_closable = False
                error_message += "   - Le book n'est pas validé par le DM.\n"
            if self.is_review_needed:
                is_closable = False
                error_message += "   - Au moins l'un des messages d'erreur de la fiche projet n'est pas résolu.\n"
            if self.company_to_invoice_left != 0.0 :
                is_closable = False
                error_message += "   - Le reste à facturer (onglet Facturation) n'est pas nul.\n"
            if self.company_residual != 0.0 :
                is_closable = False
                error_message += "   - Le reste à payer (onglet Facturation) n'est pas nul.\n"
            if self.has_provision_running :
                is_closable = False
                error_message += "   - Il reste des provisions ou du stock sur la dernière clôture.\n"
            for link in self.project_outsourcing_link_ids:
                if link.order_company_payment_to_invoice != 0.0 :
                    #Ce contrôle est partculièrement important car il permet d'assurer que pour tout type de outsourcing link (notamment les type "other" en cas de frais mission divers) 
                        # qu'un BC Fournisseur existe et que son montant correspond au montant facturé en fin de mission.
                        # Ce qui permet d'assurer que le montant de book calculé par année pour le projet (qui se fonde sur la somme des BCC et des BCF et non pas des factures) est bon.
                        # ==> En synthèse, il n'est pas possible "d'oublier" de déduire des factures fournisseurs puisqu'elles ont toutes un BCF.
                    is_closable = False
                    error_message += "   - Il reste des factures founisseur à venir de "+str(link.partner_id.name)+" (ou des factures de régularisation à émettre par Tasmane envers ce fournisseur).\n"
                if link.company_residual != 0.0 :
                    is_closable = False
                    error_message += "   - Il reste des factures founisseur à payer pour "+str(link.partner_id.name)+" (ou des factures de régularisation à payer à Tasmane par ce fournisseur).\n"
                if link.order_direct_payment_to_do != 0.0 :
                    is_closable = False
                    error_message += "   - Il reste des factures founisseur en paiement direct à déposer par/valider pour "+str(link.partner_id.name)+".\n"



        if "Annul" in stage_id.name or "Perdu" in stage_id.name: #TODO : rendre plus robuste cette condition (si le nom du statut change ou que son ID change...)
            if self.order_sum_sale_order_lines_with_draft != 0.0 :
                is_closable = False
                error_message += "   - Il existe au moins un BC client dont le statut n'est pas annulé.\n"

            if self.outsourcing_link_purchase_order_with_draft != 0.0 :
                is_closable = False
                error_message += "   - Il existe au moins un BC fournisseur dont le statut n'est pas annulé.\n"

            if self.company_part_cost_current != 0.0 :
                is_closable = False
                error_message += "   - La valorisation du pointage (coût de production du dispositif Tasmane) n'est pas nulle.\n"
            if self.has_provision_running :
                is_closable = False
                error_message += "   - Il reste des provisions ou du stock sur la dernière clôture.\n"


        return is_closable, error_message


    @api.depends('project_director_employee_id')
    def _compute_user_enrolled_ids(self):
        #surchargée dans le module staffing
        for rec in self:
            user_enrolled_ids = []
            if rec.user_id :
                user_enrolled_ids.append(rec.user_id.id)
            rec.user_enrolled_ids = [(6, 0, user_enrolled_ids)]


    user_enrolled_ids = fields.Many2many('res.users', string="Utilisateurs concernés par ce projet", compute=_compute_user_enrolled_ids, store=True)

    state_last_change_date = fields.Date('Date de dernier changement de statut', help="Utilisé pour le filtre Nouveautés de la semaine")
    color_rel = fields.Selection(related="stage_id.color", store=True)
    rel_partner_industry_id = fields.Many2one(related='partner_id.industry_id')
    number = fields.Char('Numéro', readonly=True, required=False, copy=False, default='')
    name = fields.Char(required = False) #Ne peut pas être obligatoire pour la synchro Fitnet
    stage_is_part_of_booking = fields.Boolean(related="stage_id.is_part_of_booking")
    partner_id = fields.Many2one(domain="[('is_company', '=', True)]")
    project_group_id = fields.Many2one('project.group', string='Groupe de projets', domain="[('partner_id', '=', partner_id)]", check_company=True)
        #TODO : pour être 100% sur ajouter une contrainte pour vérifier que tous les projets du groupe ont TOUJOURS le client du groupe
    project_director_employee_id = fields.Many2one('hr.employee', "Directeur de mission", required=False, check_company=True) #Si required=True ça bloque la création de nouvelle company 
    #TODO : synchroniser cette valeur avec user_id avec un oneChange
    project_manager = fields.Many2one('hr.employee', "Contact ADV", help="Personne à contatcer par l'ADV, notamment lors des clôtures comptables mensuelles.", check_company=True)
    user_id = fields.Many2one(compute=_compute_user_id, store=True)
    remark = fields.Text("Remarques")

    amount = fields.Float('Montant net S/T Fitnet', readonly=True) #Attribut temporaire Fitnet à supprimer
    billed_amount = fields.Float('Montant facturé Fitnet', readonly=True) #Attribut temporaire Fitnet à supprimer
    payed_amount = fields.Float('Montant payé Fitnet', readonly=True) #Attribut temporaire Fitnet à supprime
    is_purchase_order_received = fields.Boolean('Bon de commande reçu Fitnet', readonly=True) #Attribut temporaire Fitnet à supprimer
    purchase_order_number = fields.Char('Numéro du bon de commande Fitnet', readonly=True) #Attribut temporaire Fitnet à supprimer (le numéro de BC est sur le bon de commande client et non sur le projet en cible)
    outsourcing = fields.Selection([
            ('no-outsourcing', 'Sans sous-traitance'),
            ('co-sourcing', 'Avec Co-traitance'),
            ('direct-paiement-outsourcing', 'Sous-traitance paiement direct'),
            ('direct-paiement-outsourcing-company', 'Sous-traitance paiement direct + Tasmane'),
            ('outsourcing', 'Sous-traitance paiement Tasmane'),
        ], string="Type de sous-traitance") #Attribut temporaire Fitnet à supprimer
    agreement_id = fields.Many2one(
        comodel_name="agreement",
        string="Marché par défaut sur les BC clients",
        ondelete="restrict",
        tracking=True,
        readonly=False,
        copy=False,
        check_company=True,
    ) #Attribut temporaire Fitnet à supprimer (l'agreement_id est sur le bon de commande client et non sur le projet en cible)


    #le modèle analytic_mixin est surchargé dans ce module project_accounting afin d'appeller cette fonction compute lorsqu'une ligne avec une distribution analytque liée à ce projet est créée/modifiée
    @api.depends(
	'state',
	'company_part_amount_initial',
	'company_part_cost_initial',
        'outsource_part_amount_initial',
        'outsource_part_cost_initial',
        'cosource_part_amount_initial',
        'cosource_part_cost_initial',
	'other_part_amount_initial',
	'other_part_cost_initial',
	'project_outsourcing_link_ids',
	'book_period_ids', 'book_employee_distribution_ids', 'book_employee_distribution_period_ids', 'book_validation_employee_id', 'book_validation_datetime',
    )
    def compute(self):
        _logger.info('====================================================================== project.py COMPUTE')
        for rec in self:
            _logger.info(str(rec.number) + "=>" +str(rec.name))
            rec.check_partners_objects_consitency() #forcer l'appel à cette fonction même si cette fonction compute n'écrit rien... car elle est appelée par les lignes de factures/sale.order/purchase.order et assure que tous ces objets liés à ce projet sont bien portés par un res.partner qui est soit le client final, soit un client intermédiaire soit un fournisseur d'un outsourcing_link
            old_default_book_end = rec.default_book_end

            rec.company_invoice_sum_move_lines, rec.company_invoice_sum_move_lines_with_tax, rec.company_paid, lines = rec.compute_account_move_total()
            rec.company_residual = rec.company_invoice_sum_move_lines_with_tax - rec.company_paid

            rec.order_sum_sale_order_lines = rec.compute_sale_order_total(with_direct_payment=True, with_draft_sale_order=False)[0]
            rec.order_sum_sale_order_lines_with_draft = rec.compute_sale_order_total(with_direct_payment=True, with_draft_sale_order=True)[0]
            rec.order_to_invoice_company, rec.order_to_invoice_company_with_tax = rec.compute_sale_order_total(with_direct_payment=False, with_draft_sale_order=False)

            rec.company_to_invoice_left = rec.order_to_invoice_company - rec.company_invoice_sum_move_lines
            rec.company_to_invoice_left_with_tax = rec.order_to_invoice_company_with_tax - rec.company_invoice_sum_move_lines_with_tax


            ###### COMMON project_outsourcing_link computations
                                                               
            outsource_part_amount_current = 0.0
            outsource_part_cost_current = 0.0
            outsource_part_cost_futur = 0.0
            cosource_part_amount_current = 0.0
            cosource_part_cost_current = 0.0
            cosource_part_cost_futur = 0.0
            outsourcing_link_purchase_order_with_draft = 0.0
            other_part_amount_current = 0.0
            other_part_cost_current = 0.0
            other_part_cost_futur = 0.0
            for link in rec.project_outsourcing_link_ids:
                link.compute()
                outsourcing_link_purchase_order_with_draft += link.compute_purchase_order_total(with_direct_payment=True, with_draft_purchase_order=True)
                if link.link_type == 'outsourcing' :
                    outsource_part_amount_current += link.outsource_part_amount_current
                    outsource_part_cost_current += link.sum_account_move_lines + link.order_direct_payment_done
                    outsource_part_cost_futur += link.order_company_payment_to_invoice + link.order_direct_payment_to_do
                elif link.link_type == 'cosourcing' :
                    cosource_part_amount_current += link.outsource_part_amount_current
                    cosource_part_cost_current += link.sum_account_move_lines + link.order_direct_payment_done
                    cosource_part_cost_futur += link.order_company_payment_to_invoice + link.order_direct_payment_to_do
                elif link.link_type == 'other' :
                    other_part_cost_current += link.sum_account_move_lines + link.order_direct_payment_done
                    other_part_amount_current += link.outsource_part_amount_current
                    other_part_cost_futur += link.order_company_payment_to_invoice + link.order_direct_payment_to_do
                else :
                    raise ValidationError(_("Type d'achat non géré : %s" % str(link.link_type)))

            rec.outsourcing_link_purchase_order_with_draft = outsourcing_link_purchase_order_with_draft


            ######## OUTSOURCE PART
            rec.outsource_part_marging_amount_initial =  rec.outsource_part_amount_initial - rec.outsource_part_cost_initial
            if rec.outsource_part_amount_initial != 0 :                
                rec.outsource_part_marging_rate_initial = rec.outsource_part_marging_amount_initial / rec.outsource_part_amount_initial * 100
            else:
                rec.outsource_part_marging_rate_initial = 0.0 
 
            rec.outsource_part_amount_current = outsource_part_amount_current
            rec.outsource_part_cost_current = outsource_part_cost_current
            rec.outsource_part_cost_futur = outsource_part_cost_futur


            rec.outsource_part_marging_amount_current =  rec.outsource_part_amount_current - rec.outsource_part_cost_current - rec.outsource_part_cost_futur
            if rec.outsource_part_amount_current != 0 :
                rec.outsource_part_marging_rate_current = rec.outsource_part_marging_amount_current / rec.outsource_part_amount_current * 100
            else :
                rec.outsource_part_marging_rate_current = 0.0 

            ######## COSOURCE PART
            rec.cosource_part_marging_amount_initial =  rec.cosource_part_amount_initial - rec.cosource_part_cost_initial
            if rec.cosource_part_amount_initial != 0 :
                rec.cosource_part_marging_rate_initial = rec.cosource_part_marging_amount_initial / rec.cosource_part_amount_initial * 100
            else:
                rec.cosource_part_marging_rate_initial = 0.0 

            rec.cosource_part_amount_current = cosource_part_amount_current
            rec.cosource_part_cost_current = cosource_part_cost_current
            rec.cosource_part_cost_futur = cosource_part_cost_futur

            rec.cosource_part_marging_amount_current =  rec.cosource_part_amount_current - rec.cosource_part_cost_current - rec.cosource_part_cost_futur
            if rec.cosource_part_amount_current != 0 :
                rec.cosource_part_marging_rate_current = rec.cosource_part_marging_amount_current / rec.cosource_part_amount_current * 100
            else :
                rec.cosource_part_marging_rate_current = 0.0

            ######## OTHER PART
            rec.other_part_marging_amount_initial =  rec.other_part_amount_initial - rec.other_part_cost_initial
            if rec.other_part_amount_initial != 0 :
                rec.other_part_marging_rate_initial = rec.other_part_marging_amount_initial / rec.other_part_amount_initial * 100
            else:
                rec.other_part_marging_rate_initial = 0.0

            rec.other_part_cost_current = other_part_cost_current
            rec.other_part_amount_current = other_part_amount_current
            rec.other_part_cost_futur = other_part_cost_futur

            rec.other_part_marging_amount_current =  rec.other_part_amount_current - rec.other_part_cost_current - rec.other_part_cost_futur
            if rec.other_part_amount_current != 0 :
                rec.other_part_marging_rate_current = rec.other_part_marging_amount_current / rec.other_part_amount_current * 100
            else:
                rec.other_part_marging_rate_current = 0.0

            ######## COMPANY PART

            rec.company_part_marging_amount_initial =  rec.company_part_amount_initial - rec.company_part_cost_initial
            if rec.company_part_amount_initial != 0 :
                rec.company_part_marging_rate_initial = rec.company_part_marging_amount_initial / rec.company_part_amount_initial * 100
            else :
                rec.company_part_marging_rate_initial = 0.0
    
            rec.company_part_amount_current = rec.order_sum_sale_order_lines_with_draft - rec.outsource_part_amount_current - rec.cosource_part_amount_current - rec.other_part_amount_current

            last_monday = (datetime.today() - timedelta(days=datetime.today().weekday())).date() #Chez Tasmane, on pointe en fin de chaque semaine, donc on compte le forecast pour la semaine en cours
            rec.company_part_cost_current = -rec.get_production_cost(filters=[('category', '=', 'project_employee_validated'), ('date', '<', last_monday)])[0]
            rec.company_part_cost_futur = -rec.get_production_cost(filters=[('category', '=', 'project_forecast'), ('date', '>=', last_monday)])[0]

            rec.company_part_marging_amount_current =  rec.company_part_amount_current - rec.company_part_cost_current - rec.company_part_cost_futur
            if rec.company_part_amount_current != 0 :
                rec.company_part_marging_rate_current = rec.company_part_marging_amount_current / rec.company_part_amount_current * 100
            else :
                rec.company_part_marging_rate_current = 0.0
 
            ######## TOTAL
            rec.order_amount_initial = rec.company_part_amount_initial + rec.outsource_part_amount_initial + rec.other_part_amount_initial
            rec.sale_order_amount_initial = rec.order_amount_initial + rec.cosource_part_amount_initial

            rec.order_cost_initial = rec.company_part_cost_initial + rec.outsource_part_cost_initial + rec.other_part_cost_initial
            rec.order_marging_amount_initial = rec.order_amount_initial - rec.order_cost_initial
            if rec.order_amount_initial != 0 : 
                rec.order_marging_rate_initial = rec.order_marging_amount_initial / rec.order_amount_initial * 100
            else:
                rec.order_marging_rate_initial = 0.0

            rec.order_amount_current = rec.company_part_amount_current + rec.outsource_part_amount_current + rec.other_part_amount_current
            rec.order_cost_current = rec.company_part_cost_current + rec.outsource_part_cost_current + rec.other_part_cost_current
            rec.order_cost_futur = rec.company_part_cost_futur + rec.outsource_part_cost_futur + rec.other_part_cost_futur
            rec.order_marging_amount_current = rec.order_amount_current - rec.order_cost_current - rec.order_cost_futur
            if rec.order_amount_current != 0 : 
                rec.order_marging_rate_current = rec.order_marging_amount_current / rec.order_amount_current * 100
            else:
                rec.order_marging_rate_current = 0.0


            
            ######## DATA CONTROL
            is_consistant_prevent_napta_creation = True
            if not(rec.date) or rec.date > date(2023,1,1):
                if rec.is_prevent_napta_creation and (rec.company_part_amount_current != 0.0 or rec.company_part_cost_current != 0.0):
                    is_consistant_prevent_napta_creation = False
            rec.is_consistant_prevent_napta_creation = is_consistant_prevent_napta_creation

            is_validated_order = True
            sale_order_line_ids = rec.get_sale_order_line_ids()
            for line_id in sale_order_line_ids:
                line = rec.env['sale.order.line'].browse(line_id)
                if line.state in ['draft', 'sent']:
                    is_validated_order = False
                    break
            rec.is_validated_order = is_validated_order

            is_sale_order_with_draft = True
            if len(sale_order_line_ids) == 0 and rec.stage_id.is_part_of_booking :
                is_sale_order_with_draft = False
            rec.is_sale_order_with_draft = is_sale_order_with_draft

            is_validated_book = False
            if rec.book_validation_datetime :
                is_validated_book = True
            rec.is_validated_book = is_validated_book

            is_affected_book = True
            if not(rec.is_validated_book) and len(rec.book_employee_distribution_ids) == 0:
                is_affected_book = False
            rec.is_affected_book = is_affected_book

            is_consistant_outsourcing = True
            if not(rec.outsourcing):
                is_consistant_outsourcing = False
            else :
                if rec.outsourcing in ['direct-paiement-outsourcing', 'direct-paiement-outsourcing-company', 'outsourcing']:
                    if rec.outsource_part_amount_current == 0:
                         is_consistant_outsourcing = False
            rec.is_consistant_outsourcing = is_consistant_outsourcing

            is_validated_purchase_order = True
            reselling_subtotal_by_order_id = {}
            for link in rec.project_outsourcing_link_ids:
                POL_ids = link.get_purchase_order_line_ids()
                for purchase_order_line in POL_ids:
                    line = rec.env['purchase.order.line'].browse(purchase_order_line)
                    if line.state in ['draft', 'sent', 'to approve']:
                        is_validated_purchase_order = False
                    if (link.link_type != 'other') :
                        if (line.order_id.id not in reselling_subtotal_by_order_id.keys()):
                            reselling_subtotal_by_order_id[line.order_id.id] = 0.0
                        reselling_subtotal_by_order_id[line.order_id.id] += line.reselling_subtotal
            rec.is_validated_purchase_order = is_validated_purchase_order

            is_outsource_part_amount_current = True
            if 0.0 in reselling_subtotal_by_order_id.values():
                is_outsource_part_amount_current = False
            rec.is_outsource_part_amount_current = is_outsource_part_amount_current
            
            if not(rec.number):
                rec.is_review_needed = False
            else:
                if not(rec.is_validated_order) or not (rec.is_validated_book) or not(rec.is_validated_purchase_order) or not(rec.is_consistant_outsourcing) or not(rec.is_consistant_prevent_napta_creation) or not(rec.is_outsource_part_amount_current) or not(rec.is_sale_order_with_draft) or not(rec.is_affected_book):
                    rec.is_review_needed = True
                else :
                    rec.is_review_needed = False

            #BOOK
            if rec.stage_is_part_of_booking :
                rec.default_book_end = rec.order_sum_sale_order_lines_with_draft - rec.outsourcing_link_purchase_order_with_draft
            else :
                rec.default_book_end = 0.0


            if rec.is_book_manually_computed == True :
                for book_employee_distribution in rec.book_employee_distribution_ids:
                    book_employee_distribution.unlink()

            else :
                rec.book_comment = ""

                if (old_default_book_end != rec.default_book_end) and rec.stage_id.state != 'closed':
                    #on modifie le montant de l'année en cours
                    t = datetime.today()
                    current_year = t.year
                    book_period_current_year = False
                    pasted_years_book = 0.0
                    for book_period in rec.book_period_ids:
                        if int(book_period.reference_period) == current_year :
                            book_period_current_year = book_period
                        elif int(book_period.reference_period) < current_year :
                            pasted_years_book += book_period.period_project_book
                        elif int(book_period.reference_period) > current_year :
                            book_period.unlink()
                    default_current_year_book_amount = rec.default_book_end - pasted_years_book

                    if book_period_current_year == False :
                        dic = {
                                'project_id' : rec._origin.id,
                                'reference_period' : str(current_year),
                            }
                        book_period_current_year = rec.env['project.book_period'].create(dic)

                    if book_period_current_year.period_project_book != default_current_year_book_amount:
                        book_period_current_year.period_project_book = default_current_year_book_amount

                    #TODO : provque une erreur "Enregistrement inexistant ou supprimé.(Enregistrement : project.book_period(380,), Utilisateur : 2) "
                    #if book_period_current_year.period_project_book == 0.0 :
                    #    book_period_current_year.unlink()


    def compute_sale_order_total(self, with_direct_payment=True, with_draft_sale_order=False): 
        _logger.info('----------compute_sale_order_total => with_direct_payment=' + str(with_direct_payment))
        self.ensure_one()
        rec = self
        line_ids = rec.get_sale_order_line_ids()
        total = 0.0
        total_with_tax = 0.0

        status_list_to_keep = ['sale']
        if with_draft_sale_order :
            status_list_to_keep.append('draft')
        for line_id in line_ids:
            line = rec.env['sale.order.line'].browse(line_id)
            #_logger.info(line.read())
            if line.direct_payment_purchase_order_line_id and with_direct_payment==False :
                continue
            if line.state not in status_list_to_keep:
                continue
            total += line.price_subtotal * line.analytic_distribution[str(self.analytic_account_id.id)]/100.0
            total_with_tax += line.price_total * line.analytic_distribution[str(self.analytic_account_id.id)]/100.0
        #_logger.info(total)
        _logger.info('----------END compute_sale_order_total')
        return total, total_with_tax
        
    def action_open_sale_order_lines(self):
        line_ids = self.get_sale_order_line_ids()

        action = {
            'name': _('Lignes de commande client'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.line',
            'views': [[False, 'tree'], [False, 'form'], [False, 'kanban']],
            'domain': [('id', 'in', line_ids)],
            'target' : 'current',
            'limit' : 150,
            'groups_limit' : 150,
            'context': {
                'create': False,
                'default_analytic_distribution': {str(self.analytic_account_id.id): 100},
                'search_default_order' : 1,
            }
        }

        #if len(invoice_ids) == 1:
        #    action['views'] = [[False, 'form']]
        #    action['res_id'] = invoice_ids[0]

        return action


    
    def get_sale_order_line_ids(self, filter_list=[]):
        _logger.info('-- project sale.order.lines computation')
        query = self.env['sale.order.line']._search(filter_list)
        #_logger.info(query)
        if query == []:
            return []
        query.add_where('analytic_distribution ? %s', [str(self.analytic_account_id.id)])
        query.order = None
        query_string, query_param = query.select('sale_order_line.*') #important car Odoo fait un LEFT join obligatoire, donc si on fait SELECT * on a plusieurs colonne ID dans le résultat
        #_logger.info(query_string)
        #_logger.info(query_param)
        self._cr.execute(query_string, query_param)
        dic =  self._cr.dictfetchall()
        line_ids = [line.get('id') for line in dic]
        #_logger.info(line_ids)
        return line_ids



    def get_account_move_line_ids(self, filter_list=[]):
        _logger.info('--get_account_move_line_ids')
        query = self.env['account.move.line']._search(filter_list)
        #_logger.info(query)
        if query == []:
            return []
        query.add_where('analytic_distribution ? %s', [str(self.analytic_account_id.id)])
        query.order = None
        query_string, query_param = query.select('account_move_line.*')
        #_logger.info(query_string)
        #_logger.info(query_param)
        self._cr.execute(query_string, query_param)
        dic =  self._cr.dictfetchall()
        line_ids = [line.get('id') for line in dic]
        #_logger.info(line_ids)

        return line_ids


    def get_all_customer_ids(self):
        return [self.partner_id.id] + self.partner_secondary_ids.ids + self.partner_id.child_ids_address.ids + self.partner_id.child_ids_company.ids

    def get_all_supplier_ids(self):
        outsourcing_link_partner_ids = []
        for link in self.project_outsourcing_link_ids :
            outsourcing_link_partner_ids.append(link.partner_id.id)
        return outsourcing_link_partner_ids
        

    def compute_account_move_total(self, filter_list=[('parent_state', 'in', ['posted'])]):
        _logger.info("--compute_account_move_total")
        all_customers = self.get_all_customer_ids()
        _logger.info(all_customers)
        return self.compute_account_move_total_all_partners(filter_list + [('move_type', 'in', ['out_refund', 'out_invoice', 'in_invoice', 'in_refund']), ('partner_id', 'in', all_customers)])


    def compute_account_move_total_all_partners(self, filter_list):
        line_ids = self.get_account_move_line_ids(filter_list + [('display_type', 'not in', ['line_note', 'line_section'])])
        subtotal = 0.0
        total = 0.0
        paid = 0.0
        for line_id in line_ids:
            line = self.env['account.move.line'].browse(line_id)
            subtotal += line.price_subtotal_signed * line.analytic_distribution[str(self.analytic_account_id.id)]/100.0
            total += line.price_total_signed * line.analytic_distribution[str(self.analytic_account_id.id)]/100.0
            paid += line.amount_paid * line.analytic_distribution[str(self.analytic_account_id.id)]/100.0
        return subtotal, total, paid, line_ids

    def action_open_out_account_move_lines(self):
        all_customers = self.get_all_customer_ids()
        line_ids = self.get_account_move_line_ids([('partner_id', 'in', all_customers), ('move_type', 'in', ['out_refund', 'out_invoice', 'in_invoice', 'in_refund']), ('display_type', 'in', ['product'])])

        action = {
            'name': _("Lignes de factures / avoirs"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            #'views': [[False, 'tree'], [False, 'form'], [False, 'kanban']],
            'domain': [('id', 'in', line_ids)],
            'view_type': 'form',
            'view_mode': 'tree',
            'target' : 'current',
            'limit' : 150,
            'groups_limit' : 150,
            'view_id': self.env.ref("project_accounting.view_invoicelines_tree").id,
            'context': {
                'create': False,
                'default_analytic_distribution': {str(self.analytic_account_id.id): 100},
                'default_move_type' : 'out_invoice',
                'search_default_group_by_move' : 1,
            }
        }

        #if len(invoice_ids) == 1:
        #    action['views'] = [[False, 'form']]
        #    action['res_id'] = invoice_ids[0]

        return action

    def action_open_all_account_move_lines(self):
        line_ids = self.get_account_move_line_ids()
            #On ne met pas le partenr_id dans le filtre car dans certains cas, Tasmane ne facture pas le client final, mais un intermédiaire (Sopra par exemple) 
            #TODO : on devrait exlure les sous-traitants mais intégrer in_refund, out_invoice.. mais dans ce cas ça mélangerait les factures de frais généraux...

        action = {
            'name': _('Invoice and refound lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            #'views': [[False, 'tree'], [False, 'form'], [False, 'kanban']],
            'domain': [('id', 'in', line_ids)],
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': self.env.ref("account.view_move_line_tree").id,
            'context': {
                'create': False,
                'default_analytic_distribution': {str(self.analytic_account_id.id): 100},
            }
        }

        #if len(invoice_ids) == 1:
        #    action['views'] = [[False, 'form']]
        #    action['res_id'] = invoice_ids[0]

        return action


    @api.onchange('book_validation_employee_id')
    def onchange_book_validation_employee_id(self):
        if self.book_validation_employee_id :
            self.book_validation_datetime = datetime.now()
        else :
            self.book_validation_datetime = None


    def create_sale_order(self):
        _logger.info('--- create_sale_order')
        self.ensure_one()
        
        return  {
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'context': {
                'create': False,
                'default_company_id' : self.company_id.id,
                'default_partner_id' : self.partner_id.id,
                'default_agreement_id' : self.agreement_id.id,
                'default_user_id' : self.user_id.id,
                'default_analytic_distribution': {str(self.analytic_account_id.id): 100},
                'default_previsional_invoice_date' : self.date,
                #'default_price_unit' : price_unit,
            }
        }


    def get_production_cost(self, filters=[], force_recompute_amount=False):
        production_period_amount = 0.0
        lines = self.env['account.analytic.line'].search(filters + [('project_id', '=', self.id)])
        for line in lines :
            if force_recompute_amount :
                line.refresh_amount()
            production_period_amount += line.amount
        return production_period_amount, lines


    @api.constrains('partner_id', 'partner_secondary_ids', 'project_outsourcing_link_ids')
    def check_partners_consistency(self):
        for rec in self:

            if rec.partner_id.id in rec.partner_secondary_ids.ids:
                raise ValidationError(_("Le client final ne peut pas être un client intermédiaire (onglet Facturation)."))
                # Nota bene : on peut avoir des projets avec un BCC pour la maison mère et un BCC pour l'une de ses filiales, comme sur le projet 23138 commandé en partie par Total Energies et en partie par TGITS
            
            supplier_ids = rec.get_all_supplier_ids()
            for partner_id in [rec.partner_id.id] + rec.partner_id.child_ids_address.ids + rec.partner_id.child_ids_company.ids:
                if partner_id in supplier_ids:
                    raise ValidationError(_("Le client final (et ses établissements/filiales) ne peut pas être un fournisseur (onglet Achats) pour ce même projet."))
            
            for sec_part in rec.partner_secondary_ids:
                for sp in [sec_part.id] + sec_part.child_ids_address.ids + sec_part.child_ids_company.ids:
                    if sp in supplier_ids:
                        raise ValidationError(_("Le client intermédiaire (onglet Facturation) ni ses établissements/filiales ne peuvent être fournisseur (onglet Achats) pour ce même projet."))
            
            rec.check_partners_objects_consitency()

    def check_partners_objects_consitency(self):
        _logger.info('-- check_partners_objects_consitency')
        for rec in self:
            all_customer = rec.get_all_customer_ids()
            all_supplier = rec.get_all_supplier_ids()
            all_partner = all_customer + all_supplier

            account_move_line_ids = self.get_account_move_line_ids([('partner_id', 'not in', all_partner)])
            if len(account_move_line_ids) :
                _logger.info(all_partner)
                for line in account_move_line_ids:
                    _logger.info(self.env['account.move.line'].browse([line]).read())
                raise ValidationError(_("Enregistrement impossible pour le projet %s - %s : les écritures comptables liées à un projet doivent obligatoirement concerner soit le client final, soit le client intermédiaire (onglet Facturation), soit l'un des fourisseurs (onglet Achats) enregistrés sur la fiche du projet." % (rec.number, rec.name)))

            sale_order_line_ids = rec.get_sale_order_line_ids([('order_partner_id', 'not in', all_customer)])
            if len(sale_order_line_ids) :
                raise ValidationError(_("Enregistrement impossible pour le projet %s - %s : les bons de commande clients liées à un projet doivent obligatoirement concerner soit le client final, soit le client intermédiaire (onglet Facturation)." % (rec.number, rec.name)))
                #TODO : réduire au client final ?

            purchase_order_line_ids = self.env['project.outsourcing.link'].get_purchase_order_line_ids(filter_list=[('partner_id', 'not in', all_supplier)], analytic_account_ids=[str(rec.analytic_account_id.id)]) 
            if len(purchase_order_line_ids) :
                raise ValidationError(_("Enregistrement impossible pour le projet %s - %s : les bons de commande fournisseurs liés à un projet doivent obligatoirement concerner l'un des fournisseurs liés au projet (onglet Achat)." % (rec.number, rec.name)))

    @api.depends('accounting_closing_ids', 'accounting_closing_ids.closing_date', 'accounting_closing_ids.is_validated', 'accounting_closing_ids.pca_balance', 'accounting_closing_ids.fae_balance', 'accounting_closing_ids.fnp_balance', 'accounting_closing_ids.cca_balance')
    def compute_has_provision_running(self):
        for rec in self:
            rec.has_provision_running = False
            last_closing_sorted = rec.accounting_closing_ids.filtered(lambda r: r.is_validated==True).sorted(key=lambda r: r.closing_date, reverse=True)
            if len(last_closing_sorted):
                last_closing = last_closing_sorted[0]
                if last_closing.pca_balance or last_closing.fae_balance or last_closing.fnp_balance or last_closing.cca_balance or last_closing.production_balance :
                    rec.has_provision_running = True


    def compute_margin_graph(self):
        _logger.info('---- compute_margin_graph')

        for rec in self:
            lines = self.env['account.analytic.line'].search([('project_id', '=', rec.id), '|', ('category', '=', 'project_employee_validated'), ('category', '=', 'project_forecast')], order="date asc, category")
            real_lines_reversed = lines.filtered(lambda x: x.category == 'project_employee_validated').sorted(key=lambda r: r.date, reverse=True)
            if len(real_lines_reversed) > 0:
                date_last_real = real_lines_reversed[0].date
                date_ante_last_real = date_last_real
                if len(real_lines_reversed) > 1:
                    date_ante_last_real = real_lines_reversed[1].date
            else :
                if len(lines) > 0 : 
                    date_last_real = lines[0].date
                    date_ante_last_real = lines[0].date

            data_dic = {}
            cumul_real_amount = False
            cumul_forecast_amount = 0.0
            cumul_projected_amount = False
            cumul_real_unit = False
            cumul_forecast_unit = 0.0
            cumul_projected_unit = False
            for line in lines :
                date_str = str(line.date)
                if date_str not in data_dic.keys() :
                    data_dic[date_str] = {
                                'date_fr' : line.date.strftime("%A %d %B %Y"),
                                'real_amount' : False,
                                'forecast_amount' : 0.0,
                                'projected_amount' : False,
                                'real_unit' : False,
                                'forecast_unit' : 0.0,
                                'projected_unit' : False,
                                'margin_amount' : rec.company_part_cost_initial,
                            }

                if line.date <= date_last_real :
                    if line.category == 'project_employee_validated':
                        cumul_real_amount += -line.amount
                        cumul_real_unit += line.unit_amount
                        cumul_projected_amount += -line.amount
                        cumul_projected_unit += line.unit_amount
                        data_dic[date_str]['real_amount'] = cumul_real_amount
                        data_dic[date_str]['real_unit'] = cumul_real_unit


                if line.date >= date_ante_last_real :
                    if line.category == 'project_forecast':
                        cumul_projected_amount += -line.amount
                        cumul_projected_unit += line.unit_amount
                    data_dic[date_str]['projected_amount'] = cumul_projected_amount
                    data_dic[date_str]['projected_unit'] = cumul_projected_unit

                if line.category == 'project_forecast':
                    cumul_forecast_amount += -line.amount
                    cumul_forecast_unit += line.unit_amount

                data_dic[date_str]['forecast_amount'] = cumul_forecast_amount
                data_dic[date_str]['forecast_unit'] = cumul_forecast_unit
            
            #_logger.info(data_dic)

            data = {
                        'date' : [],
                        'date_fr' : [],
                        'real_amount' : [],
                        'forecast_amount' : [],
                        'projected_amount' : [],
                        'real_unit' : [],
                        'forecast_unit' : [],
                        'projected_unit' : [],
                        'margin_amount' : []
                    }

            for date_str, values in data_dic.items():
                data['date'].append(date_str)
                data['date_fr'].append(values['date_fr'])
                data['real_amount'].append(values['real_amount'])
                data['forecast_amount'].append(values['forecast_amount'])
                data['projected_amount'].append(values['projected_amount'])
                data['real_unit'].append(values['real_unit'])
                data['forecast_unit'].append(values['forecast_unit'])
                data['projected_unit'].append(values['projected_unit'])
                data['margin_amount'].append(values['margin_amount'])

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])


            ##################### AMOUNT CHART
            TOOLTIPS_AMOUNT = [
                        ("", "@date_fr"),
                        ("Réel (vert)", "@real_amount{0 0.00 €}"),
                        ("Prévisionnel (noir)", "@forecast_amount{0 0.00 €}"),
                        ("Projeté (violet)", "@projected_amount{0 0.00 €}"),
                    ]

            p = figure(width=600, height=300, x_axis_type="datetime", tooltips=TOOLTIPS_AMOUNT, title="Coûts des pointages cumulés (€) du dispositif Tasmane")
            #p.left[0].formatter.use_scientific = False
            p.left[0].formatter = NumeralTickFormatter(format="0 0 €", language="fr")
            p.line(y='forecast_amount', x='date', source=df, line_color="black", line_width=2, line_dash="dashed", legend_label="Prévisionnel (€)")
            p.line(y='projected_amount', x='date', source=df.query('projected_amount != False'), line_color="darkviolet", line_width=2, line_dash="dashed", legend_label="Projeté (€)")
            p.line(y='real_amount', x='date', source=df.query('real_amount != False'), line_color="green", line_width=2, legend_label="Réel (€)")
            p.line(y='margin_amount', x='date', source=df, line_color="red", line_width=2, legend_label="Coût prévu/staf. init. (€)")
            p.legend.location = "top_left"
            p.legend.click_policy="hide"

            tod = date.today()
            p.segment(tod, 0, tod, max(df['forecast_amount'].max(), df['projected_amount'].max()), color="red", line_width=2, line_dash="dashed")

            #band = Band(base=df['date'], upper=df['real_amount'], source=df, level='underlay', fill_alpha=0.2, fill_color='#55FF88')
            #p.add_layout(band)

            #p.segment(df['date'], df['real'], df['date'], df['forecasted'], color="lightgrey", line_width=3)
            #p.circle(df['date'], df['real'], color="blue", size=5)
            #p.circle(df['date'], df['forecasted'], color="red", size=5)

            script, div = components(p, wrap_script=False)
            rec.margin_graph = json.dumps({"div": div, "script": script})

            ##################### UNIT CHART
            TOOLTIPS_UNIT = [
                        ("", "@date_fr"),
                        ("Réel (vert)", "@real_unit{0 0.00 €}"),
                        ("Prévisionnel (noir)", "@forecast_unit{0 0.00 €}"),
                        ("Projeté (violet)", "@projected_unit{0 0.00 €}"),
                    ]

            p2 = figure(width=600, height=300, x_axis_type="datetime", tooltips=TOOLTIPS_UNIT, title="Charges des pointages cumulés (jours) du dispositif Tasmane")
            #p2.left[0].formatter.use_scientific = False
            p2.left[0].formatter = NumeralTickFormatter(format="0 0 €", language="fr")
            p2.line(y='forecast_unit', x='date', source=df, line_color="black", line_width=2, line_dash="dashed", legend_label="Prévisionnel (j)")
            p2.line(y='projected_unit', x='date', source=df.query('projected_unit != False'), line_color="darkviolet", line_width=2, line_dash="dashed", legend_label="Projeté (j)")
            p2.line(y='real_unit', x='date', source=df.query('real_unit != False'), line_color="green", line_width=2, legend_label="Réel (j)")
            p2.legend.location = "top_left"
            p2.legend.click_policy="hide"

            tod = date.today()
            p2.segment(tod, 0, tod, max(df['forecast_unit'].max(), df['projected_unit'].max()), color="red", line_width=2, line_dash="dashed")
            script, div = components(p2, wrap_script=False)
            rec.activity_graph = json.dumps({"div": div, "script": script})




    state = fields.Selection(related='stage_id.state')
    partner_id = fields.Many2one(string='Client final')
    partner_secondary_ids = fields.Many2many('res.partner', string='Clients intermediaires', help="Dans certains projet, le client final n'est pas le client facturé par Tasmane. Un client intermédie Tasmane. Enregistrer ce(s) client(s) intermédiaire(s) ici afin de permettre sa(leur) facturation pour ce projet.")
    ######## TOTAL
    sale_order_amount_initial = fields.Monetary('Montant HT commandé par le client', store=True, compute=compute)
    order_amount_initial = fields.Monetary('Montant HT piloté par Tasmane initial', store=True, compute=compute)
    order_amount_current = fields.Monetary('Montant HT piloté par Tasmane actuel', store=True, compute=compute)
    order_sum_sale_order_lines_with_draft = fields.Monetary("Total HT commandé à Tasmane (y/c BCC à l'état Devis)", store=True, compute=compute)
    order_sum_sale_order_lines = fields.Monetary("Total HT commandé à Tasmane (uniquement à l'état BDC)", store=True, compute=compute, help="Somme des commandes passées à Tasmane par le client final ou bien le sur-traitant")

    order_cost_initial = fields.Monetary('Coût total initial', compute=compute, store=True)
    order_marging_amount_initial = fields.Monetary('Marge totale (€) initiale', compute=compute, store=True)
    order_marging_rate_initial = fields.Float('Marge totale (%) initiale', compute=compute, store=True)

    order_cost_current = fields.Monetary('Somme des coûts actuels', compute=compute, store=True)
    order_cost_futur = fields.Monetary('Somme des coûts à venir ', compute=compute, store=True)
    order_marging_amount_current = fields.Monetary('Marge totale (€) projetée', compute=compute, store=True)
    order_marging_rate_current = fields.Float('Marge totale (%) projetée', compute=compute, store=True)

    order_to_invoice_company = fields.Monetary('Montant HT à facturer par Tasmane au client', compute=compute, store=True)
    order_to_invoice_company_with_tax = fields.Monetary('Montant TTC à facturer par Tasmane au client', compute=compute, store=True)
    company_invoice_sum_move_lines = fields.Monetary('Montant HT déjà facturé par Tasmane au client', compute=compute, store=True)
    company_invoice_sum_move_lines_with_tax = fields.Monetary('Montant déjà TTC facturé par Tasmane au client', compute=compute, store=True)
    company_to_invoice_left = fields.Monetary('Montant HT restant à facturer par Tasmane au client', compute=compute, store=True)
    company_to_invoice_left_with_tax = fields.Monetary('Montant TTC restant à facturer par Tasmane au client', compute=compute, store=True)

    company_paid = fields.Monetary('Montant TTC déjà payé par le client à Tasmane', compute=compute, store=True)
    company_residual = fields.Monetary('Montant TTC restant à payer par le client à Tasmane', compute=compute, store=True)

    ######## COMPANY PART
    company_part_amount_initial = fields.Monetary('Montant HT dispositif Tasmane initial', 
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            help="Valorisation de la part produite par les salariés Tasmane ou bien les sous-traitants payés au mois indépedemment de leur charge")
    company_part_cost_initial = fields.Monetary('Valo des pointages Tasmane (€) initial', 
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            help="Montant du pointage Tasmane valorisé (pointage par les salariés Tasmane ou bien les sous-traitants payés au mois indépedemment de leur charge) : CJM * nombre de jours pointés")
    company_part_marging_amount_initial = fields.Monetary('Marge sur dispo Tasmane (€) initiale', store=True, compute=compute, help="Montant dispositif Tasmane - Coût de production dispo Tasmane") 
    company_part_marging_rate_initial = fields.Float('Marge sur dispo Tasmane (%) initiale', store=True, compute=compute)

    company_part_amount_current = fields.Monetary('Montant HT dispositif Tasmane actuel', 
            compute=compute,
            store=True,
            help="Valorisation de la part produite par les salariés Tasmane ou bien les sous-traitants payés au mois indépedemment de leur charge")
    company_part_cost_current = fields.Monetary('Valo des pointages Tasmane (€) actuelle', store=True, compute=compute, help="Montant du pointage Tasmane valorisé (pointage par les salariés Tasmane ou bien les sous-traitants payés au mois indépedemment de leur charge) : CJM * nombre de jours pointés. Seuls les pointage strictement antérieur au dernier lundi sont pris en compte.")
    company_part_cost_futur = fields.Monetary('Valo des pointages Tasmane (€) à venir', store=True, compute=compute, help="Montant du staffing futur Tasmane valorisé (pointage par les salariés Tasmane ou bien les sous-traitants payés au mois indépedemment de leur charge) : CJM * nombre de jours staffés. Seul le staffing postérieur ou égal au dernier lundi sont pris en compte.")
    company_part_marging_amount_current = fields.Monetary('Marge sur dispo Tasmane (€) projetée', store=True, compute=compute)
    company_part_marging_rate_current = fields.Float('Marge sur dispo Tasmane (%) projetée', store=True, compute=compute)

    ######## OUTSOURCE PART
    outsource_part_amount_initial = fields.Monetary('Montant HT de revente S/T initial', 
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            help="Montant de revevent de ce qui est produit par les sous-traitants de Tasmane")
    outsource_part_cost_initial = fields.Monetary('Montant HT acheté au S/T initial',
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            )
    outsource_part_marging_amount_initial = fields.Monetary('Marge sur part sous-traitée (€) initiale', store=True, compute=compute)
    outsource_part_marging_rate_initial = fields.Float('Marge sur part sous-traitée (%) initiale', store=True, compute=compute)

    outsource_part_amount_current = fields.Monetary('Montant HT de revente S/T actuel', help="Montant de revente de ce qui est produit par les sous-traitants de Tasmane, fondé sur les BC fournisseurs enregistrés sur TaskForce", store=True, compute=compute)
    outsource_part_cost_current = fields.Monetary('Montant HT facturé par le S/T actuel', help="En cas de paiement direct par le client au S/T, ce montant comprend les factures émises par le S/T vers le client et qui ont été validées par Tasmane sous Chorus", store=True, compute=compute)
    outsource_part_cost_futur = fields.Monetary('Montant HT restant à facturer par le S/T', help="En cas de paiement direct par le client au S/T, ce montant comprend les factures restant à émettre par le S/T vers le client et qui devront être validées par Tasmane sous Chorus", store=True, compute=compute)
    outsourcing_link_purchase_order_with_draft = fields.Monetary('Somme de toutes les lignes d\'achats', store=True, compute=compute)
    outsource_part_marging_amount_current = fields.Monetary('Marge sur part sous-traitée (€) projetée', store=True, compute=compute)
    outsource_part_marging_rate_current = fields.Float('Marge sur part sous-traitée (%) projetée', store=True, compute=compute)

    project_outsourcing_link_ids = fields.One2many('project.outsourcing.link', 'project_id')

    ######## COSOURCE PART
    cosource_part_amount_initial = fields.Monetary('Montant HT de la part co-traitée initial', 
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            help="Montant produit par les co-traitants de Tasmane : part produite par les co-traitants")
    cosource_part_cost_initial = fields.Monetary('Montant HT facturé par le co-traitant au client final',
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            )
    cosource_part_marging_amount_initial = fields.Monetary('Marge sur part co-traitée (€) initiale', store=True, compute=compute)
    cosource_part_marging_rate_initial = fields.Float('Marge sur part co-traitée (%) initiale', store=True, compute=compute)

    cosource_part_amount_current = fields.Monetary('Montant HT de la part co-traitée actuel', help="Montant produit par les co-traitants de Tasmane : part produite par les co-traitants.", store=True, compute=compute)
    cosource_part_cost_current = fields.Monetary('Montant HT des factures du co-traitant validées par Tasmane sur Chorus', store=True, compute=compute)
    cosource_part_cost_futur = fields.Monetary('Montant HT restant à valider par Tasmane sur Chorus', store=True, compute=compute)
    cosource_part_marging_amount_current = fields.Monetary('Marge sur part co-traitée (€) projetée', store=True, compute=compute)
    cosource_part_marging_rate_current = fields.Float('Marge sur part co-traitée (%) projetée', store=True, compute=compute)



    ######## OTHER PART
    other_part_amount_initial = fields.Monetary('Montant HT de revente "autres presta" initial', 
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            help="Les autres prestations peuvent être la facturation d'un séminaire dans les locaux de Tasmane ou des frais de déplacement par exemple.")
    other_part_cost_initial = fields.Monetary('Montant HT acheté "autres presta." initial',
            #TODO : reactiver lorsque les DM auront initialisé les données historiques
            #states={'before_launch' : [('readonly', False)], 'launched':[('readonly', True)], 'closed':[('readonly', True)]},
            tracking=True,
            )
    other_part_marging_amount_initial = fields.Monetary('Marge sur les autres prestations (€) initiale', store=True, compute=compute)
    other_part_marging_rate_initial = fields.Float('Marge sur les autres prestations (%) initiale', store=True, compute=compute)

    other_part_amount_current = fields.Monetary('Montant HT de revente "autres presta" actuel', 
            compute=compute,
            store=True,
            help="Les autres prestations peuvent être la facturation d'un séminaire dans les locaux de Tasmane ou des frais de déplacement par exemple.")
    other_part_cost_current = fields.Monetary('Montant HT facturés par les prestataires actuel', store=True, compute=compute)
    other_part_cost_futur = fields.Monetary('Montant HT restant à facturer par les pretataires actuel', store=True, compute=compute)
    other_part_marging_amount_current = fields.Monetary('Marge sur les autres prestations (€) projetée', store=True, compute=compute)
    other_part_marging_rate_current = fields.Float('Marge sur les autres prestations (%) projetée', store=True, compute=compute)


    ######## BOOK
    default_book_end = fields.Monetary('Valeur du book par défaut à terminaison', store=True, compute=compute, help="Si l'étape projet est paramétrée pour compter dans le book, ce champ correspond à la valeur du book par défaut projetée à terminaison : somme des commandes clients (validées ou non) diminuée des commandes d'achats (validées ou non). Sinon ce champ a une valeur nulle.")
    is_book_manually_computed = fields.Boolean('Book géré manuellement')
    book_comment = fields.Text('Commentaire sur le book')
    book_period_ids = fields.One2many('project.book_period', 'project_id', string="Book par année")
    book_employee_distribution_ids = fields.One2many('project.book_employee_distribution', 'project_id', string="Book par salarié")
    book_employee_distribution_period_ids = fields.One2many('project.book_employee_distribution_period', 'project_id', 'Book par salarié et par an')
    book_validation_employee_id = fields.Many2one('hr.employee', string="Book validé par", tracking=True)
        #TODO : il faudrait que seul le groupe TAZ_management puisse modifier le champ book_validation_employee_id, mais en attendant on log les changements dans le chatter.
    book_validation_datetime = fields.Datetime("Book validé le", tracking=True)


    # ACCOUNTING CLOSING
    accounting_closing_ids = fields.One2many('project.accounting_closing', 'project_id', 'Clôtures comptables')
    has_provision_running = fields.Boolean('Provisions/stock prod. en cours', store=True, help="Il y a des provisions courrantes ou du stock de production au sein de la dernière cloture VALIDÉE du projet.", compute=compute_has_provision_running)


    # INVOICING MANAGEMENT DATA
    is_prevent_napta_creation = fields.Boolean("Ne pas créer sur Napta (dont portage pur)")

    is_sale_order_with_draft = fields.Boolean("BC Client existants", store=True, compute=compute, help="FAUX si le projet est en statut Accord client/Commandé/Terminé (on devrait avoir du book) mais que le total des BC client (quelque soit leur statut) est nul")
    is_validated_order = fields.Boolean("BC clients tous validés", store=True, compute=compute, help="VRAI si tous les BC clients sont à l'état 'Bon de commande'.")
    is_validated_purchase_order = fields.Boolean("BC fournisseurs tous validés", store=True, compute=compute, help="VRAI si tous les BC fournissuers sont à l'état 'Bon de commande'.")
    is_validated_book = fields.Boolean("Répartition book validée", store=True, compute=compute, help="VRAI si la répartition du book est validée.")
    is_consistant_outsourcing = fields.Boolean("BCF présents", store=True, compute=compute, help="VRAI si le type de sous-traitance est renseigné et qu'il est cohérent avec les Bons de commande fournisseur du projet.")
    is_consistant_prevent_napta_creation = fields.Boolean("Absent Napta et pas de prod. Tasmane", store=True, compute=compute, help="FAUX si la case Ne pas créer sur Napta est cochée et que le montant HT du dispositif Tasmane à date n'est pas nul.")
    is_outsource_part_amount_current = fields.Boolean("Prix de revente S/T renseigné", store=True, compute=compute, help="VRAI si, pour chaque BC Fournisseur, la somme des prix de revente n'est pas nulle.")
    is_affected_book = fields.Boolean("Book affecté", store=True, compute=compute, help="VAI si le book est validé OU qu'il existe au moins une ligne de book")

    is_review_needed = fields.Boolean('A revoir avec le DM', store=True, compute=compute, help="Projet à revoir avec le DM : au moins un contrôle est KO ou bien le champ 'Commentaire ADV' contient du texte.")
    invoicing_comment = fields.Text("Commentaire ADV")
    project_book_factor = fields.Float("Facteur de bonus/malus", default=1.0)


    # CHART
    margin_graph = fields.Char("Margin graph", compute=compute_margin_graph)
    activity_graph = fields.Char("Activity graph", compute=compute_margin_graph)
