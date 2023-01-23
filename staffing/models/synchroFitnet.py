import requests
import zlib
import os
import json
import datetime
import pytz
from lxml import etree, html

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo import _
          
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)
          
##################################################################
##########                SET PARAMETERS                ##########
##################################################################

proto = "https://"
host = "tasmane.fitnetmanager.com"
api_root = "/FitnetManager/rest/"

cache_mode = False
cache_folder = '/tmp/'

##################################################################
##########                 REST CLIENT                  ##########
##################################################################
class ClientRestFitnetManager:
    def __init__(self,proto, host, api_root, login_password):
        self.proto = proto
        self.host = host
        self.api_root = api_root
        self.login_password = login_password
        url_appel_api = proto+host+api_root
        self.url_appel_api = url_appel_api
        _logger.info("ClientRestFitnetManager : " + self.url_appel_api)

    def get_api(self, target_action):
        path = os.path.join(cache_folder, target_action.replace('/','_'))
        if cache_mode :
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as cf:
                    return json.loads(cf.read())

        headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'Authorization' : "Basic "+self.login_password,
            'Accept': 'application/json',
            'Host': self.host,
            #'Connection': 'Keep-Alive',
            'User-Agent': '007',
        }
        _logger.info("Calling "+ self.url_appel_api+target_action)
        response = requests.get(self.url_appel_api+target_action, headers=headers)
        response_code = response.status_code
        _logger.info("HTTP return code :" + str(response_code))
        res = response.json()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=4)
        return res


class fitnetPartner(models.Model):
    _inherit = "res.partner"
    _sql_constraints = [
        ('fitnet_id_uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objets avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetProjectStage(models.Model):
    _inherit = "project.project.stage"
    _sql_constraints = [
        ('fitnet_id_uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objets avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetEmployee(models.Model):
    _inherit = "hr.employee"
    _sql_constraints = [
        ('fitnet_id_uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objets avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    _sql_constraints = [
        ('fitnet_id_uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objets avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetNeed(models.Model):
    _inherit = "staffing.need"
    _sql_constraints = [
        ('fitnet_id_uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objets avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetLeave(models.Model):
    _inherit = "hr.leave"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetLeaveType(models.Model):
    _inherit = "hr.leave.type"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetAccountMove(models.Model):
    _inherit = "account.move"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetAccountMoveLine(models.Model):
    _inherit = "account.move.line"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetAccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetBankAccount(models.Model):
    _inherit = "res.partner.bank"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetJob(models.Model):
    _inherit = "hr.job"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

class fitnetHrContract(models.Model):
    _inherit = "hr.contract"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")


class fitnetProjectGroup(models.Model):
    _inherit = "project.group"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")







class fitnetProject(models.Model):
    _inherit = "project.project"
    _sql_constraints = [
        ('fitnet_id__uniq', 'UNIQUE (fitnet_id)',  "Impossible d'enregistrer deux objects avec le même Fitnet ID.")
    ]
    fitnet_id = fields.Char("Fitnet ID")

    def import_grille_competences(self):
        file_path = '/home/ubuntu/230122_Grille_competences.csv'
        with open(file_path, 'r', encoding="utf-8") as f :
            import csv
            csvreader = csv.DictReader(f, delimiter=';')
            for row in csvreader:
                #print(row)
                employees = self.env['hr.employee'].search([('first_name', '=', row['prénom']), ('name', '=', row['Nom']), ('work_email', '!=', False)])
                if len(employees) != 1:
                    print("Erreur pour trouver l'employee %s" % row['Nom'])
                    print(employees)
                    continue
                employee = employees[0]
                print('--- Compétences de l\'employee %s' % row['Nom'])

                for skill_name, skill_value in row.items():
                    if skill_name in ["", "Nom", "prénom", "Date de mise à jour"]:
                        continue
                    skills = self.env['hr.skill'].search([('name', '=', skill_name)])
                    if len(skills) != 1:
                        print("Erreur pour trouver la skill %s" % skill_name)
                        print(skills)
                        continue
                    skill = skills[0]

                    if skill_value == '':
                        skill_level_name = "Je ne connais pas du tout"
                    elif skill_value in ['x', 'X']:
                        skill_level_name = 'OUI'
                    elif skill_value in ['1', '2', '3', '4']:
                        skill_level_name = 'Niveau %s' % skill_value
                    else :
                        print("Erreur : donnée inatendue dans la grille Excel pour le niveau %s pour la compétence %s" % (skill_value, skill_name))
                        continue
                    levels = self.env['hr.skill.level'].search([('skill_type_id', '=', skill.skill_type_id.id), ('name', '=', skill_level_name)])
                    if len(levels) != 1:
                        print("Erreur pour trouver le niveau %s pour la compétence %s" % (skill_value, skill_name))
                        print(levels)
                        continue
                    level = levels[0]


                    employee_skills = self.env['hr.employee.skill'].search([('employee_id', '=', employee.id), ('skill_id', '=', skill.id)])
                    if len(employee_skills) > 1:
                        print("Erreur : il y a plus d'une hr.employee.skill pour la compétence %s pour %s" % (skill.id, employee.name))
                        print(employee_skills)
                    elif len(employee_skills) == 1:
                        #mise à jour
                        employee_skill = employee_skills[0]
                        if employee_skill.skill_level_id.id != level.id :
                            print("Mise a jour de la compétence %s au niveau %s pour %s" % (skill.name, level.name, employee.name))
                            employee_skill.skill_level_id = level.id
                    else :
                        #creation
                        print("Créaion de la compétence %s au niveau %s pour %s" % (skill.name, level.name, employee.name))
                        self.env['hr.employee.skill'].create({'employee_id' : employee.id, 'skill_id' : skill.id, 'skill_level_id' : level.id, 'skill_type_id' : skill.skill_type_id.id})



    def synchAllFitnet(self):
        _logger.info(' ############## Début de la synchro Fitnet')
        login_password = self.env['ir.config_parameter'].sudo().get_param("fitnet_login_password") 
        client = ClientRestFitnetManager(proto, host, api_root, login_password)


        #return self.import_grille_competences()

        self.sync_employees(client)
        self.sync_employees_contracts(client)
        self.sync_customers(client)

        #TODO           self.sync_prospect(client)
        self.sync_project(client)
        self.sync_contracts(client)

        self.sync_assignments(client)
        self.sync_assignmentsoffContract(client)
        self.sync_timesheets(client)
        self.sync_forecastedActivities(client)


        #Correctif à passer de manière exceptionnelle
        #self.analytic_line_employee_correction()
        
        self.sync_holidays(client) 
        #TODO : gérer les mises à jour de congés (via sudo() ?) avec des demandes au statut validé

        #self.sync_customer_invoices(client)
        #TODO           self.sync_supplier_invoices(client)


        #TODO : supprimer les objets qui ont un FitnetId et qui ne sont plus dans les retours API Fitnet intégrals (ou plus dispo par GET initaire sur l'ID)
        _logger.info(' ############## Fin de la synchro Fitnet')

    def sync_customer_invoices(self, client):
        _logger.info('---- sync_customer_invoices')
        fitnet_objects = client.get_api('invoices/v2/1/0/01-01-2018/31-12-2050')
        mapping_fields_invoice = {
            'invoiceNumber' : {'odoo_field' : 'name'},
            'customerId' : {'odoo_field' : 'partner_id'},
            'billingDate' : {'odoo_field' : 'invoice_date'},
            'expectedPaymentDate' : {'odoo_field' : 'invoice_date_due'},
            'ibanId' : {'odoo_field' : 'partner_bank_id'},
            'move_type' : {'odoo_field' : 'move_type', 'selection_mapping' : {'out_invoice' : 'out_invoice', 'out_refund':'out_refund'}},
        }
        mapping_fields_invoice_line = {
            'inoviceId' : {'odoo_field' : 'account_move_id'},
            'designation' : {'odoo_field' : 'name'},
            'amountBTax' : {'odoo_field' : 'price_unit'},
            'quantity' : {'odoo_field' : 'quantity'},
            'contractId' : {'odoo_field' : ''},
        }
        invoices_list = []
        invoices_lines_list = []
        for invoice in fitnet_objects:
            if invoice['invoiceId'] not in [1492]:
                continue
            if invoice['bTaxBilling'] < 0:
                continue #avoir
                #invoice['move_type'] = 'out_refund'
            else :
                invoice['move_type'] = 'out_invoice'
            invoices_list.append(invoice)
            for line in invoice['invoiceLines']:
                line['inoviceId'] = invoice['invoiceId']
                line['contractId'] = invoice['contractId']
                line['quantity'] = 1.00
                invoices_lines_list.append(line)
                #if line['vatRate'] != 20.0:
                #    raise ValidationError(_("Taux de TVA != 20%"))
        #TODO generer le project.milestone et y rattacher la facture (date du jalon = bilingDueDate dans le modèle fitnet)
        #TODO générer le paiement dans Odoo (date du paiement = actualPaymentDate dans le modèle fitnet)
        #TODO : gérer les avoir
        #self.create_overide_by_fitnet_values('account.move', invoices_list, mapping_fields_invoice, 'invoiceId',context={})
        #self.create_overide_by_fitnet_values('account.move.line', invoices_lines_list, mapping_fields_invoice_line, 'inoviceLineId',context={})

    def sync_holidays(self, client):
        _logger.info('---- sync_holydays')
        odoo_model_name = 'hr.leave'
        fitnet_leave_contents = {}

        period_list = []

        #for year in range(2020, 2025):
        #    for month in range(1,13):
        #       period_list.append((month, year))

        for i in [-1, 0, 1, 2, 3, 4, 5, 6]: #on synchronise les congés du mois précédent, du mois en cours et des 6 prochain moins
            t = datetime.datetime.today() + relativedelta(months=i)
            period_list.append((t.month, t.year))

        for month, year in period_list :
                _logger.info('Get leaves for %s/%s' % (str(month), str(year)))
                fitnet_objects = client.get_api('leaves/getLeavesWithRepartition/1/%s/%s' % (month, year))
                #_logger.info(fitnet_objects)
                #_logger.info(type(fitnet_objects))
                if isinstance(fitnet_objects, list) : #this id False when there is no leaves for a month
                    _logger.info("Nombre de congés au moins en partie sur ce mois : %s" % len(fitnet_objects))
                    for obj in fitnet_objects:
                        for leaveType in obj['leaveTypes']:
                            #if leaveType['id'] not in [992]: #992 : 3.5 RTT de Takoua a partir du 28/12/202
                            #    continue
                            #_logger.info("Adding leaveType ID=%s" % str(leaveType['id']))
                            #leaveType['master_fitnet_leave_id'] = obj['leaveId']
                            leaveType['designation'] = obj['designation']
                            leaveType['employeeId'] = obj['employeeId']
                            leaveType['status'] = obj['status']
                            if leaveType['startMidday'] == True:
                                leaveType['request_date_from_period'] = 'pm'
                                beginHour = '13:00:00'
                            else :
                                leaveType['request_date_from_period'] = 'am'
                                beginHour = '00:00:01'
                            if leaveType['endMidday'] == True:
                                leaveType['request_date_to_period'] = 'am'
                                endHour = '13:00:00'
                            else :
                                leaveType['request_date_to_period'] = 'pm'
                                endHour = '23:59:59'
                            leaveType['beginDateTime'] = leaveType['beginDate'] + ' ' + beginHour
                            leaveType['endDateTime'] = leaveType['endDate'] + ' ' + endHour
                            fitnet_leave_contents[leaveType['id']] = leaveType

        mapping_fields = {
            'designation' : {'odoo_field' : 'notes'},
            'employeeId' : {'odoo_field' : 'employee_id'},
            'typeId' : {'odoo_field' : 'holiday_status_id'},
            'beginDate' : {'odoo_field' : 'request_date_from'},
            'endDate' : {'odoo_field' : 'request_date_to'},
            'beginDateTime' : {'odoo_field' : 'date_from'},
            'endDateTime' : {'odoo_field' : 'date_to'},
            'numberOfDays' : {'odoo_field' : 'number_of_days'},
            'request_date_from_period' : {'odoo_field' : 'request_date_from_period', 'selection_mapping' : {'am' : 'am', 'pm':'pm'}},
            'request_date_to_period' : {'odoo_field' : 'request_date_to_period', 'selection_mapping' : {'am' : 'am', 'pm':'pm'}},
            'status' : {'odoo_field' : 'state', 'selection_mapping' : {'Demande accordée' : 'validate', 'Demande annulée' : 'canceled', 'Demande refusée' : 'refuse', 'False' : 'draft', '900':'confirm', 'Demande' : 'validate'}},
            }
        _logger.info(len(fitnet_leave_contents.values()))
        with open('/tmp/old_all_leaves', 'w', encoding='utf-8') as f:
            json.dump(fitnet_leave_contents, f, indent=4)
        values = fitnet_leave_contents.values()

        #TODO : bizarre : quand on passer un state qui n'est pas validate, à la création il est surchargé par validate... alors qu'il est bien remplacé par le statut demandé si execute à nouveau le script
        self.create_overide_by_fitnet_values(odoo_model_name, values, mapping_fields, 'id',context={'leave_skip_date_check':True})



    def sync_timesheets(self, client):
        _logger.info('---- sync_timesheets')
        #fitnet_objects = client.get_api("activities/getActivitiesOnContract/1/01-01-2018/01-01-2050") #=> endpoint unitile : il ne comporte pas l'assignementID
        fitnet_objects = client.get_api("timesheet/timesheetAssignment?companyId=1&startDate=01-01-2018&endDate=01-06-2050")
        fitnet_filtered = []
        for obj in fitnet_objects:
            if obj['amount'] == 0.0 : 
                continue
            if obj['activityType'] == 3:
                #Activity type: 1:Contracted activity, 2:Off-Contract activity, 3:Training 
                continue

            if obj['activityType'] == 2:
                obj['assignmentID'] = 'assignmentOffContractID_'+str(obj['assignmentID'])

            obj['category'] = 'project_employee_validated'
            obj['fitnet_id'] = 'timesheet_' + str(obj['timesheetAssignmentID'])
            fitnet_filtered.append(obj)

        #_logger.info(len(fitnet_objects))
        #_logger.info(len(fitnet_filtered))

        odoo_model_name = 'account.analytic.line'

        mapping_fields = {
            'assignmentID' : {'odoo_field' : 'staffing_need_id'},
            'assignmentDate' : {'odoo_field' : 'date'},
            'amount' : {'odoo_field' : 'unit_amount'},
            'category' : {'odoo_field' : 'category', 'selection_mapping' : {'project_employee_validated' : 'project_employee_validated'}},
            }
        self.create_overide_by_fitnet_values(odoo_model_name, fitnet_filtered, mapping_fields, 'fitnet_id')

    def analytic_line_employee_correction(self):
        #Corriger les affectations d'employee si les hr.employee sont créé a posteriori
        lines = self.env['account.analytic.line'].search([('staffing_need_id', '!=', False)])
        count_last_sql_commit = 0
        for line in lines :
            count_last_sql_commit += 1 
            if count_last_sql_commit % 1000 == 0:
                _logger.info('######## SQL COMMIT')
                self.env.cr.commit()
            line.employee_id =  line.staffing_need_id.staffed_employee_id.id
        _logger.info('######## FINAL SQL COMMIT')
        self.env.cr.commit()

    def sync_forecastedActivities(self, client):
        _logger.info('---- sync_forecastedActivities')
        fitnet_objects = client.get_api("forecastedActivities") #TODO : pour éviter les risques d'incohérence utiliser la même ressourcque que sync_timesheets et moduler le filtre
        for obj in fitnet_objects:
            obj['category'] = 'project_forecast'
            obj['fitnet_id'] = 'forecastedActivityAssigment_' + str(obj['forecastedActivityAssigmentId'])
        odoo_model_name = 'account.analytic.line'
        mapping_fields = {
            'assigmentId' : {'odoo_field' : 'staffing_need_id'},
            'date' : {'odoo_field' : 'date'},
            'forecastedAmount' : {'odoo_field' : 'unit_amount'},
            'category' : {'odoo_field' : 'category', 'selection_mapping' : {'project_forecast' : 'project_forecast'}},
            }
        self.create_overide_by_fitnet_values(odoo_model_name, fitnet_objects, mapping_fields, 'fitnet_id')

    def sync_assignments(self, client):
        _logger.info('---- sync_assignments')
        fitnet_objects = client.get_api("assignments?companyId=1&startDate=01-01-2018&endDate=31-12-2040")
        for obj in fitnet_objects:
            obj['status'] = 'done'

        mapping_fields = {
            'assignmentStartDate' : {'odoo_field' : 'begin_date'},
            'assignmentEndDate' : {'odoo_field' : 'end_date'},
            'initialBudget' : {'odoo_field' : 'nb_days_needed'},
            'contractID' : {'odoo_field' : 'project_id'}, 
            'employeeID' : {'odoo_field' : 'staffed_employee_id'}, 
            'status' : {'odoo_field' : 'state', 'selection_mapping' : {'done' : 'done'}},
            }
        odoo_model_name = 'staffing.need'
        self.create_overide_by_fitnet_values(odoo_model_name, fitnet_objects, mapping_fields, 'assignmentOnContractID')

    def sync_assignmentsoffContract(self, client):
        _logger.info('---- sync_assignmentsOffContract')
        fitnet_objects = client.get_api("assignments/offContract/1")
        for obj in fitnet_objects:
            obj['status'] = 'done'
            obj['assignmentOffContractID'] = 'assignmentOffContractID_'+str(obj['assignmentOffContractID'])
            obj['offContractActivityID'] = 'offContractActivityID_'+str(obj['offContractActivityID'])
            obj['assignmentStartDate'] = '01/01/2020'

        mapping_fields = {
            'assignmentStartDate' : {'odoo_field' : 'begin_date'},
            #'assignmentEndDate' : {'odoo_field' : 'end_date'},
            #'initialBudget' : {'odoo_field' : 'nb_days_needed'},
            'offContractActivityID' : {'odoo_field' : 'project_id'},
            'employeeID' : {'odoo_field' : 'staffed_employee_id'},
            'status' : {'odoo_field' : 'state', 'selection_mapping' : {'done' : 'done'}},
            }
        odoo_model_name = 'staffing.need'
        self.create_overide_by_fitnet_values(odoo_model_name, fitnet_objects, mapping_fields, 'assignmentOffContractID')

    def sync_customers(self, client):
        _logger.info('---- sync_customers')
        customers = client.get_api("customers/1")
        for customer in customers:
            odoo_customer = self.env['res.partner'].search([('fitnet_id', '=', customer['clientId']), ('is_company', '=', True)])
            if len(odoo_customer) > 1 :
                #_logger.info("Plus d'un res.partner pour cet id client fitnet")
                continue
            if len(odoo_customer) == 0:
                odoo_customer = self.env['res.partner'].search([('ref', '=ilike', customer['clientCode']), ('is_company', '=', True), ('fitnet_id', '=', False)])
                if len(odoo_customer) > 1 :
                    #_logger.info("Plus d'un res.partner pour cet ref %s" % customer['clientCode'])
                    continue
                if len(odoo_customer) == 0:
                    odoo_customer = self.env['res.partner'].search([('name', '=ilike', customer['clientCode']), ('is_company', '=', True), ('fitnet_id', '=', False)])
                    if len(odoo_customer) > 1 :
                        #_logger.info("Plus d'un res.partner pour ce nom %s" % customer['clientCode'])
                        continue
                    if len(odoo_customer) == 0:
                        _logger.info("Aucun res.partner Odoo pour FitnetID=%s / Fitnet name=%s" % (customer['clientId'], customer['name']))
                        continue
                #get FitnetID
                odoo_customer.fitnet_id = customer['clientId']
                _logger.info("Intégration de l'ID Fitnet pour le res.partner : Odoo ID=%s / Odoo name=%s / FitnetID=%s / Fitnet name=%s" % (odoo_customer.id, odoo_customer.name, customer['clientId'], customer['name']))

            #on appelle pas directement create_overide_by_fitnet_values car on ne veut pas créer le client automatiquement (risque de doublonner) s'il n'a pas pu être mappé sur le nom ou la ref 
                # Dans ce cas on veut le le client soit créé manuellement par Denis ou Margaux
            customer['paymentTermsId'] = customer['companyCustomerLink'][0]['paymentTermsId']
            if customer['siret']:
                customer['siret'] = customer['siret'].replace(' ', '').replace('.', '')
            if customer['vatNumber']:
                customer['vatNumber'] = customer['vatNumber'].replace(' ', '').replace('.', '')
            if customer['phone']:
                customer['phone'] = customer['phone'].replace(' ', '')
            if customer['email']:
                customer['email'] = customer['email'].replace(' ', '')
            if customer['clientCode']:
                customer['clientCode'] = customer['clientCode'].replace(' ', '')

            #if customer['vatNumber'] in ['FR59542051180']:
                # TODO : Le numéro TVA intracom de TotalEnergie FR59542051180 produit une boucle infinie lors de l'enregistrement
                    #https://github.com/odoo/odoo/blob/c5be51a5f02471e745543b3acea4f39664f8a820/addons/base_vat/models/res_partner.py#L635    
            #   del customer['vatNumber']

            mapping_fields = {
                'vatNumber' : {'odoo_field' : 'vat'}, 
                'clientCode' : {'odoo_field' : 'ref'},
                'phone' : {'odoo_field' : 'phone'},
                'email' : {'odoo_field' : 'email'},
                'paymentTermsId' : {'odoo_field' : 'property_payment_term_id'},


                'siret' : {'odoo_field' : 'siret'},
                #adresse par defaut
                #adresse de facturation
                #compte bancaire
                #compte comptable
                #customerGroupId => on ne la synchronise pas car Odoo doit rester maître
                #segmentId => on ne la synchronise pas car Odoo doit rester maître sur le Business Domain (plus à jour que Fitnet)
            }
            res = self.prepare_update_from_fitnet_values('res.partner', customer, mapping_fields, odoo_customer)
            if len(res) > 0:
                _logger.info("Mise à jour du res.partner client Odoo ID= %s avec les valeurs de Fitnet %s" % (str(odoo_customer.id), str(res)))
                odoo_customer.write(res)
        _logger.info('---- END sync_customers')

    def sync_employees_contracts(self, client):
        _logger.info('--- synch_employees_contracts')
        employee_contracts = client.get_api("employmentContracts")

        for contract in employee_contracts:
            contract['name'] = contract['employeeName'] + " - " + contract['effective_date']
            contract['wage'] = 0.0

            contract['leaving_date_previous_day'] = False
            if contract['leaving_date']:
                if contract['effective_date'] == contract['leaving_date']:
                    contract['leaving_date_previous_day'] = contract['leaving_date']
                else:
                    leaving_date_previous_day = datetime.datetime.strptime(contract['leaving_date'], '%d/%m/%Y').date() - datetime.timedelta(days=1)
                    contract['leaving_date_previous_day'] = leaving_date_previous_day.strftime("%d/%m/%Y")

            if contract['leaving_date']:
                contract['state'] = 'close'
            else :
                contract['state'] = 'open'
            #il n'y a pas de statut de contrat dans l'API Fitnet, donc pas d'équivalent au statut annulé
            #TODO : pour les contrat avec une effective_date dans le futur, mettre un statut = draft

        mapping_fields = {
            'name' : {'odoo_field' : 'name'},
            'employee_id' : {'odoo_field' : 'employee_id'},
            'state' : {'odoo_field' : 'state', 'selection_mapping' : {'open' : 'open', 'close' : 'close'}},
            'effective_date' : {'odoo_field' : 'date_start'},
            'leaving_date_previous_day' : {'odoo_field' : 'date_end'},
            'collaboratorProfileId' : {'odoo_field' : 'job_id'},
            'wage' : {'odoo_field' : 'wage'},
            #contract_type_id
            #qualification
            #positionName
            #coefficientSituationName
            #end_date_of_trial_period
            #nb_days_per_year
            #part_time
            }
        odoo_model_name = 'hr.contract'
        self.create_overide_by_fitnet_values(odoo_model_name, employee_contracts, mapping_fields, 'employment_contract_id')
               
    def sync_employees(self, client):
        _logger.info('--- synch_employees')
        employees = client.get_api("employees/1")
        _logger.info('nb employees ' + str(len(employees)))

        #Intégrer l'id Fitnet aux hr.employee si on peut le trouver via l'email du hr.employee ou bien d'un res_users (et dans ce cas création du hr.employee à la volée)
        for employee in employees:
            odoo_employee = self.env['hr.employee'].search([('fitnet_id','=',employee['employee_id']), ('active', 'in', [True, False])])
            if len(odoo_employee) > 1 :
                _logger.info("Plus d'un hr.employee a cet id fitnet %s" % str(employee['employee_id']))
                continue
            if len(odoo_employee) == 0 :
                _logger.info(employee['name'])
                _logger.info(employee['email'])
                if not employee['email']:
                    _logger.info("Pas d'email sur Fitnet")
                    continue
                #intégrer l'ID Fitnet au hr.employee
                odoo_employee = self.env['hr.employee'].search([('work_email','=',employee['email']), ('fitnet_id', '=', False)])
                if len(odoo_employee) > 1 :
                    _logger.info("Erreur : plusieurs hr.employee on ce work_email : %s" % employee['email'])
                    continue
                if len(odoo_employee) == 0:
                    #créer l'employé Odoo s'il existe un user Odoo qui porte le même identifiant
                    odoo_user = self.env['res.users'].search([('login','=',employee['email']), ('employee_id','=',False)])
                    if len(odoo_user) == 1:
                        odoo_user.action_create_employee()
                        _logger.info("Création de l'employée depuis l'utilsiateur avec le login=%s" % odoo_user.login)
                        odoo_employee = odoo_user.employee_id
                    else :
                        _logger.info("Aucun hr.employee ni res.users Odoo pour FitnetID=%s / Fitnet email=%s" % (employee['employee_id'],employee['email']))
                        continue
                odoo_employee.fitnet_id = employee['employee_id']
                _logger.info("Intégration de l'ID Fitnet pour le hr.employee :  Odoo ID=%s / Odoo name=%s / FitnetID=%s / Fitnet name=%s" % (odoo_employee.id, odoo_employee.name, employee['employee_id'], employee['name']))
        
        #Pour les employee qui existent sur Fitnet mais pas sur Odoo (exemple : anciens tasmaniens) : on crée le hr.employee mais sans res_user associé
            #TODO : créer le res_user associé si la date d'entrée fitnet > date du jour et que date de sortie non défini ou > date du jour
        # ... puis mettre à jour les valeurs des employés Odoo
        mapping_fields = {
            'name' : {'odoo_field' : 'name'},
            'profile_id' : {'odoo_field' : 'job_id'},
            'surname' : {'odoo_field' : 'first_name'},
            'email' : {'odoo_field' : 'work_email'},
            'gender' : {'odoo_field' : 'gender', 'selection_mapping' : {'Male' : 'male', 'Female' : 'female'}},
            #registration_id
            #hiringDate => attribut du hr.contract
            #leavingDate => attribut du hr.contract
            #foreignEmployee
            #address
            #zone_23_key_P_1-S_1 #Champ onDemande pour l'email personnel
            #zone_23_key_P_268-S_1 #Champ onDemande pour le mobile personnel
            }
        odoo_model_name = 'hr.employee'
        self.create_overide_by_fitnet_values(odoo_model_name, employees, mapping_fields, 'employee_id', filters=[('active', 'in', [True, False])])


    def sync_project(self, client):
        _logger.info('--- synch projects')
        projects = client.get_api("projects/1")
        mapping_fields = {
            'title' : {'odoo_field' : 'name'},
            'customer' : {'odoo_field' : 'partner_id'},
            }
        odoo_model_name = 'project.group'
        self.create_overide_by_fitnet_values(odoo_model_name, projects, mapping_fields, 'projectId')



    def sync_contracts(self, client):
        _logger.info('---- sync_contracts')
        mapping_fields = {
            'title' : {'odoo_field' : 'name'},
            'projectId' : {'odoo_field' : 'project_group_id'},
            'customerId' : {'odoo_field' : 'partner_id'},
            'beginDate' : {'odoo_field' : 'date_start'},
            'endDate' : {'odoo_field' : 'date'},
            'contractNumber' : {'odoo_field' : 'number'},
            'contractAmount' : {'odoo_field' : 'order_amount'},
            'is_purchase_order_received' : {'odoo_field' : 'is_purchase_order_received'},
            'contractCategoryId' : {
                'odoo_field' : 'outsourcing', 
                'selection_mapping':
                    {
                        '0' : False,
                        '1' : 'no-outsourcing', #Sans Sous-Traitance
                        '2' : 'direct-paiement-outsourcing', #Sous-Traitance paiement direct
                        '3' : 'outsourcing', #Sous-Traitance paiement Tasmane
                        '4' : 'direct-paiement-outsourcing-company', #Sous-Traitance paiement direct + Tasmane
                        '5' : 'co-sourcing', #Avec Cotraitance
                    },
                },
            'remark' : {'odoo_field' : 'remark'},
        #    'description' : {'odoo_field' : 'description'},
        #   TODO : ajouter le contractType qui porte les accords cadre sur Fitnet
            'orderNumber' : {'odoo_field' : 'purchase_order_number'},
            'billedAmount' : {'odoo_field' : 'billed_amount'},
            'payedAmount' : {'odoo_field' : 'payed_amount'},
            'status' : {'odoo_field' : 'stage_id'},
            'project_director_employee_id' : {'odoo_field' : 'project_director_employee_id'},
            'commercialStatusID' : {
                'odoo_field' : 'probability', 
                'selection_mapping':
                    { 
                        '0' : False,
                        '2' : '30',
                        '3' : '70',
                        '5' : '100',
                        '9' : '0',
                    },
                },
            }
        odoo_model_name = 'project.project'
        fitnet_objects = client.get_api("contracts/1")

        for obj in fitnet_objects:
            # Transco de la liste déroulante Bon de commmande reçu en un booléen sur Odoo
            if self.get_proprieteOnDemand_by_id(obj, "zone_13_key_P_1-S_1")  == "Reçu":
                obj['is_purchase_order_received'] = True
            else:
                obj['is_purchase_order_received'] = False
        

            # Recherche du res.user Odoo qui correspond au DM de la mission
            comList = obj['affectedCommercialsList']
            fitnet_employee_id = None
            if len(comList) == 1 :
                fitnet_employee_id = comList[0]['employeeId'] 
            else :
                if len(comList) > 1 :
                    for commercial in comList:
                        if commercial['fullName'] == obj['contractCreator']:
                            fitnet_employee_id = commercial['employeeId']
                    if fitnet_employee_id == None :
                        fitnet_employee_id = comList[0]['employeeId']
            obj['project_director_employee_id'] = fitnet_employee_id

        self.create_overide_by_fitnet_values(odoo_model_name, fitnet_objects, mapping_fields, 'contractId')


    def get_proprieteOnDemand_by_id(self, fitnet_object, prop_id):
        res = None
        for prop in fitnet_object['proprieteOnDemand']:
            if prop['id'] == prop_id:
                res = prop['value']
        return res

    def create_overide_by_fitnet_values(self, odoo_model_name, fitnet_objects, mapping_fields, fitnet_id_fieldname, context={}, filters=[]) :
        _logger.info('--- create_overide_by_fitnet_values')

        count_last_sql_commit = 0
        for fitnet_object in fitnet_objects: 
            count_last_sql_commit += 1 
            if count_last_sql_commit % 1000 == 0:
                _logger.info('######## SQL COMMIT')
                self.env.cr.commit()
            #### chercher l'objet et le créer s'il n'existe pas
            fitnet_id = fitnet_object[fitnet_id_fieldname]
            filter_list = [('fitnet_id', '=', fitnet_id)] + filters
            odoo_objects = self.env[odoo_model_name].search(filter_list)
            odoo_object = False
            if len(odoo_objects) > 1:
                continue
            if len(odoo_objects) == 1 :
                odoo_object = odoo_objects[0]
                res = self.prepare_update_from_fitnet_values(odoo_model_name, fitnet_object, mapping_fields, odoo_object)
                if len(res) > 0:
                    _logger.info("Mise à jour de l'objet %s ID= %s avec les valeurs de Fitnet %s" % (odoo_model_name, str(odoo_object.id), str(res)))
                    odoo_object.with_context(context).write(res)
            if len(odoo_objects) == 0 :
                dic = self.prepare_update_from_fitnet_values(odoo_model_name, fitnet_object, mapping_fields)
                dic['fitnet_id'] = fitnet_id
                _logger.info("Creating Odoo instance of %s object for fitnet %s=%s with values %s" % (odoo_model_name, fitnet_id_fieldname, fitnet_id, str(dic)))
                odoo_object = self.env[odoo_model_name].with_context(context).create(dic)
                #_logger.info("Odoo object created, Odoo ID=%s state=%s" % (str(odoo_object.id), odoo_object.state))
                _logger.info("Odoo object created, Odoo ID=%s" % (str(odoo_object.id)))
            #if not c:
            #    continue
        _logger.info('######## FINAL SQL COMMIT')
        self.env.cr.commit()


    def prepare_update_from_fitnet_values(self, odoo_model_name, fitnet_object, mapping_fields, odoo_object=False) :
            #_logger.info('--- prepare_update_from_fitnet_values')
            #### mise à jour depuis Fitnet
            models = self.env['ir.model'].search([('model','=',odoo_model_name)])
            if len(models) != 1:
                _logger.info("Objet non trouvé %s." % odoo_model_name)
                return False
            model = models[0]

            res = {}
            for fitnet_field_name, odoo_dic in mapping_fields.items():
                #_logger.info('fitnet_field_name %s' % fitnet_field_name)
                odoo_field_name = odoo_dic['odoo_field']
                odoo_field = self.env['ir.model.fields'].search([('model_id', '=', model.id), ('name', '=', odoo_field_name)])[0]
                odoo_value = None

                if fitnet_field_name in fitnet_object.keys():
                    fitnet_value = fitnet_object[fitnet_field_name]
                else : 
                    onDemand = self.get_proprieteOnDemand_by_id(fitnet_object, fitnet_field_name)
                    if onDemand is not None:
                        fitnet_value = onDemand
                    else :
                        _logger.info("Champ inexistant dans l'objet dans l'objet Fitnet %s" % fitnet_field_name)

                if odoo_field.ttype in ["char", "html", "text", "date", "datetime", "float", "integer", "boolean", "selection", "monetary"]  :
                    if fitnet_value == None:
                        fitnet_value = False
                    odoo_value = fitnet_value

                    if odoo_field.ttype in ["date"]  :
                        if fitnet_value :
                            odoo_value = datetime.datetime.strptime(fitnet_value, '%d/%m/%Y').date()

                    if odoo_field.ttype in ["datetime"]  :
                        #Fitnet dates are implicitly  in Paris Timezone
                        #Odoo expects dates in UTC format without timezone
                        if fitnet_value:
                            odoo_value = datetime.datetime.strptime(fitnet_value, '%d/%m/%Y %H:%M:%S')
                            local = pytz.timezone("Europe/Paris")
                            local_dt = local.localize(odoo_value, is_dst=None)
                            odoo_value = local_dt.astimezone(pytz.utc)
                            odoo_value = odoo_value.replace(tzinfo=None)


                    if odoo_field.ttype in ["float", "monetary"] :
                        odoo_value = float(fitnet_value)

                    if odoo_field.ttype in ["integer"] :
                        odoo_value = int(fitnet_value)

                    if odoo_field.ttype in ["boolean"] :
                        odoo_value = bool(fitnet_value)

                    if odoo_field.ttype in ["selection"] :
                        odoo_value = odoo_dic['selection_mapping'][str(fitnet_value)]

                    if odoo_field.ttype in ["html"] :
                        if fitnet_value and len(fitnet_value.strip())>0: 
                            #TODO : cette conversion ne donne pas le bon encodage => les commentaires avect des accent sont toujours raffraichis, même si Odoo a déjà la bonne valeur
                            html_fitnet = html.tostring(html.fromstring(fitnet_value)).decode('utf-8')
                            #_logger.info(html_fitnet)
                            odoo_value = html_fitnet

                            #html_fitnet5 = html.tostring(html.fromstring(fitnet_value.encode('utf-8'))).decode('utf-8')
                            #_logger.info(html_fitnet5)
                            #html_fitnet4 = html.tostring(html.fromstring(fitnet_value.encode('utf-8')), encoding='utf-8').decode('utf-8')
                            #_logger.info(html_fitnet4)
                            #html_fitnet3 = html.tostring(html.fromstring(fitnet_value, parser=html.HTMLParser(encoding='utf-8'))).decode('utf-8')
                            #_logger.info(html_fitnet3)
                            #html_fitnet2 = html.tostring(html.fromstring(fitnet_value))
                            #_logger.info(html_fitnet2)

                            #html_odoo =  html.tostring(odoo_object[odoo_field_name])
                            #if html_fitnet == html_odoo:
                            #    odoo_value = odoo_object[odoo_field_name]

                    if odoo_object :
                        if odoo_object[odoo_field_name] != odoo_value:
                            #_logger.info(odoo_object[odoo_field_name])
                            #_logger.info(odoo_value)
                            res[odoo_field_name] = odoo_value
                    else :
                            res[odoo_field_name] = odoo_value


                if odoo_field.ttype == "many2one" :
                    if fitnet_value == None : #le champ manu2one était valorisé sur Fitnet, mais a été remis à blanc sur Fitnet
                        if odoo_object :
                            if odoo_object[odoo_field_name] :
                                res[odoo_field_name] = False
                        else:
                            res[odoo_field_name] = False
                        continue
                    filter_list = [('fitnet_id','=',fitnet_value)]
                    if odoo_field.relation in ['hr.employee']:
                        tup = ('active', 'in', [True, False])
                        filter_list.append(tup)
                    target_objects = self.env[odoo_field.relation].search(filter_list)
                    if len(target_objects) > 1 :
                        _logger.info("Plusieurs objets Odoo %s ont le fitnet_id %s" % (odoo_field.relation, fitnet_value))
                        continue
                    if len(target_objects) == 1 :
                        target_object = target_objects[0]
                        odoo_value = target_object.id
                        if odoo_object :
                            if odoo_object[odoo_field_name] != target_object:
                                res[odoo_field_name] = odoo_value
                        else :
                            res[odoo_field_name] = odoo_value
                    if len(target_objects) == 0 :
                        _logger.info("Erreur : aucun objet %s n'a de fitnet_id valorisé à %s" % (odoo_field.relation, fitnet_value))
                        continue
                #écraser la valeur Odoo par la valeur Fitnet si elles sont différentes
                if odoo_value is None:
                    _logger.info("Type %s non géré pour le champ Fitnet %s = %s" % (odoo_field.ttype, fitnet_field_name, fitnet_value))
                    continue

            return res

