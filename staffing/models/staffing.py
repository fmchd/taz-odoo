# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo import _
import logging
_logger = logging.getLogger(__name__)


class staffingNeed(models.Model):
    _name = "staffing.need"
    _description = "Record the staffing need"
    _order = 'project_id'

    @api.depends('project_id')
    def _compute_name(self):
        for record in self:
            record.name = "%s - %s" % (record.project_id.name or "", record.job_id.name or "")
            if record.staffed_employee_id:
                record.name = "%s - %s %s" % (record.project_id.name or "", record.staffed_employee_id.first_name or "", record.staffed_employee_id.name or "")

    @api.onchange('project_id')
    def onchange_project_id(self):
        _logger.info('onchange_project_id')
        if self.project_id:
            need_ids = self.env['staffing.need'].search([('project_id', '=', self.project_id.id), ('state', 'in', ['waitt', 'open'])])
            if len(need_ids) > 0 :
                need = need_ids[0]
                _logger.info(need.name)
                self.begin_date = need.begin_date
                self.end_date = need.end_date
            else: 
                self.begin_date = self.project_id.date_start
                self.end_date = self.project_id.date

    @api.onchange('begin_date', 'end_date')
    def onchnage_dates(self):
        #if not self.nb_days_needed:
        if self.begin_date and self.end_date:
            nb = self.env['hr.employee'].number_work_days_period(self.begin_date, self.end_date)
            #_logger.info("onchange_project_id NB jours : %s" % str(nb))
            self.nb_days_needed = nb

    def staffing_proposal_ids(self):
        for rec in self :
            rec.staffing_proposal_ids = self.env['staffing.proposal'].search([('employee_job', '=', rec.job_id.id), ('staffing_need_id', '=', rec.id)])

    def staffing_proposal_other_job_ids(self):
        for rec in self :
            rec.staffing_proposal_other_job_ids = self.env['staffing.proposal'].search([('employee_job', '!=', rec.job_id.id), ('staffing_need_id', '=', rec.id)])

    name = fields.Char("Nom", compute=_compute_name)

    project_id = fields.Many2one('project.project', string="Projet", ondelete="restrict", required=True)
    project_stage = fields.Many2one(related='project_id.stage_id')
    job_id = fields.Many2one('hr.job', string="Grade souhaité") #TODO : impossible de le metrte en required car la synchro fitnet importe des assignments qui n'ont pas de job_i
    skill_id = fields.Many2one('hr.skill', string="Compétences") #TODO : si on veut pouvoir spécifier le niveau, il faut un autre objet technique qui porte le skill et le level
    considered_employee_ids = fields.Many2many('hr.employee', string="Équipier(s) envisagé(s)")
    #Pour le moment, un staffing.need ne porte qu'un seul employé. Si besion de plusieurs employés avec le même profil, il faudra créer plusieurs besoins
    staffed_employee_id = fields.Many2one('hr.employee', string='Équipier satffé')
    begin_date = fields.Date('Date début', required=True)
    end_date = fields.Date('Date fin', required=True)
    nb_days_needed = fields.Float('Nb jours')
    description = fields.Text("Description du besoin")
    ##TODO : impossible de le metrte en required car la synchro fitnet importe des assignments qui ont un budget jour initial à 0
    #percent_needed = fields.Float('Pourcentage besoin')

    state = fields.Selection([
        ('wait', 'En attente'),
        ('open', 'Ouvert'),
        ('done', 'Staffé'),
        ('canceled', 'Annulé'),
        ], 'Statut', default='open')

    staffing_proposal_ids = fields.One2many('staffing.proposal', 'staffing_need_id', compute=staffing_proposal_ids)
    staffing_proposal_other_job_ids = fields.One2many('staffing.proposal', 'staffing_need_id', compute=staffing_proposal_other_job_ids)
    def open_record(self):
        # first you need to get the id of your record
        # you didn't specify what you want to edit exactly
        rec_id = self.id
        # then if you have more than one form view then specify the form id
        form_id = self.env.ref("staffing.need_form")

        # then open the form
        return {
                'type': 'ir.actions.act_window',
                'name': 'Besoins de staffing',
                'res_model': 'staffing.need',
                'res_id': rec_id,
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': form_id.id,
                'context': {},
                # if you want to open the form in edit mode direclty
                'flags': {'initial_mode': 'edit'},
                'target': 'current',
            }

    @api.model
    def create(self, vals):
        needs = super().create(vals)
        for need in needs:
            need.generate_staffing_proposal()
        return needs

    def write(self, vals):
        res = super().write(vals)
        self.generate_staffing_proposal()
        if "staffed_employee_id" in vals:
            if vals["staffed_employee_id"] :
                self.state = 'done'
            else :
                self.state = 'open'
        return res

    def generate_staffing_proposal(self):
        if self.state != 'open':
            return

        employees = self.env['hr.employee'].search([('active', '=', True)]) #TODO : montrer ceux qui seront présent à date de début de la mission mais pas encore chez Tasmane
        for employee in employees:
            employee_job = employee._get_job_id(self.begin_date)
            if not employee_job:
                continue
            #_logger.info("generate_staffing_proposal %s" % employee.name)
            needs = self.env['staffing.proposal'].search([('staffing_need_id', '=', self.id),('employee_id', '=', employee.id)])
            if len(needs) == 0:
                dic = {}
                dic['employee_id'] = employee.id
                dic['staffing_need_id'] = self.id
                self.env['staffing.proposal'].create(dic)
        #TODO supprimer les propositions qui ne sont pas sur ces employés (cas de changement de grade de la demande)

    #TODO : lorsqu'une affectation est validée, créer les prévisionnels ET RECALCULER LES autres prorposals de l'employee


class staffingProposal(models.Model):
    _name = "staffing.proposal"
    _description = "Computed staffing proposal"
    _order = "ranked_proposal desc"

    _sql_constraints = [
        ('need_employee_uniq', 'UNIQUE (staffing_need_id, employee_id)',  "Impossible d'enregistrer deux propositions de staffing pour le même besoin et le même consultant.")
    ]

    @api.depends('staffing_need_id', 'staffing_need_id.begin_date', 'staffing_need_id.end_date', 'employee_id')
    def compute(self):
        for rec in self :
            #_logger.info('staffingProposal compute %s' % rec.employee_id.name)
            #TODO : relancer cette fonction si les timesheet évoluent sur cette période
            need = rec.staffing_need_id
            rec.employee_availability = rec.employee_id.number_days_available_period(need.begin_date, need.end_date)
            rec.ranked_employee_availability = rec.employee_availability / need.nb_days_needed * 100
            rec.ranked_proposal = rec.ranked_employee_availability


    @api.depends('staffing_need_id', 'employee_id')
    def _compute_name(self):
        for record in self:
            record.name = "%s - %s" % (record.staffing_need_id.name or "", record.employee_id.name or "")

    @api.depends('staffing_need_id', 'staffing_need_id.staffed_employee_id', 'employee_id')
    def _compute_is_staffed(self):
        for record in self:
            res = False
            if record.staffing_need_id.staffed_employee_id.id == record.employee_id.id:
                res = True
            record.is_staffed = res

    @api.depends('staffing_need_id', 'staffing_need_id.considered_employee_ids', 'employee_id')
    def _compute_is_considered(self):
        for record in self:
            res = False
            if record.employee_id in record.staffing_need_id.considered_employee_ids :
                res = True
            record.is_considered = res

    def action_staff_employee(self):
        for record in self:
            record.staffing_need_id.staffed_employee_id = record.employee_id.id

    def action_consider_employee(self):
        for record in self:
            record.staffing_need_id.considered_employee_ids = [(4,record.employee_id.id)]

    def action_unconsider_employee(self):
        for record in self:
            if record.employee_id in record.staffing_need_id.considered_employee_ids:
                record.staffing_need_id.considered_employee_ids = [(3,record.employee_id.id)]

    def action_open_employee(self):
        rec_id = self.employee_id.id
        form_id = self.env.ref("staffing.employee_form")
        return {
                'type': 'ir.actions.act_window',
                'name': 'Employee',
                'res_model': 'hr.employee',
                'res_id': rec_id,
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': form_id.id,
                'context': {},
                # if you want to open the form in edit mode direclty
                'flags': {'initial_mode': 'edit'},
                'target': 'current',
            }

    name = fields.Char("Nom", compute=_compute_name)
    is_staffed = fields.Boolean('Staffé', compute=_compute_is_staffed, store=True)
    is_considered = fields.Boolean('Envisagé', compute=_compute_is_considered, store=True)
    #Ajouter un lien vers les autres staffing proposal en concurrence (même personne, même période avec une quotité totale de temps > 100%)
    staffing_need_id = fields.Many2one('staffing.need', ondelete="cascade")
    staffing_need_state = fields.Selection(related='staffing_need_id.state')
    employee_id = fields.Many2one('hr.employee')

    employee_job_id = fields.Many2one(string="Grade", related='employee_id.job_id') #TODO : remplacer le hr.employee.job_id par une fonction qui retourne get_job_id()
    employee_skill_ids = fields.One2many(string="Compétences", related='employee_id.employee_skill_ids')
    employee_staffing_wishes = fields.Html(string="Souhaits de staffing COD", related='employee_id.staffing_wishes')

    employee_availability = fields.Float("Dispo sur la période", compute='compute', store=True)
    ranked_proposal = fields.Float('Note globale', compute='compute', store=True)
    ranked_employee_availability = fields.Float('Note disponibilité', compute='compute', store=True)
    ranked_employee_skill = fields.Float('Note adéquation compétences', compute='compute', store=True)
    ranked_employee_explicit_voluntary = fields.Float('A explicitement demandé à être sur cette misison', compute='compute', store=True)
    ranked_employee_worked_on_proposal = fields.Float('A travaillé sur la proposition commerciale', compute='compute', store=True)
    ranked_employee_wished_on_need = fields.Float('Envisagé dans la desciption du besoin', compute='compute', store=True)

    #Champs related pour le Kanban
    employee_image = fields.Binary(related="employee_id.image_128")
    employee_job = fields.Many2one(related="employee_id.job_id") #TODO : remplacer cette ligne par une conditin de recherche lorsque la job_id aura été transformé en fonction
    employee_coach = fields.Many2one(related="employee_id.coach_id")
    staffing_need_nb_days_needed = fields.Float(related="staffing_need_id.nb_days_needed")

