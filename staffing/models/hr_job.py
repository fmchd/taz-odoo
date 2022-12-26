from odoo import models, fields, api
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo import _
import logging
_logger = logging.getLogger(__name__)


class HrJob(models.Model):
    _inherit = "hr.job"

    def _get_daily_cost(self, date):
        res = False
        for cost_line in self.cost_ids:
            if res == False :
                if cost_line.begin_date <= date:
                    res = cost_line
            else :
                if cost_line.begin_date <= date and cost_line.begin_date > res.begin_date:
                    res = cost_line

        if res == False :
            return False

        return res.cost

    cost_ids = fields.One2many('hr.cost', 'job_id', string="CJM / TJM historisés")


class HrCost(models.Model):
    _name = "hr.cost"
    _description = "Cost history"
    _order = 'begin_date desc'

    _sql_constraints = [
        ('begin_date__uniq', 'UNIQUE (begin_date, job_id)',  "Impossible d'enregistrer deux objets pour le même poste et la même date d'effet.")
    ]

    job_id = fields.Many2one('hr.job', string="Poste", required=True)
    begin_date = fields.Date("Date d'effet", required=True)
    cost = fields.Float("CJM", help="Coût journalier moyen imputé sur les lignes de pointage.", required=True)
    revenue = fields.Float("TJM", help="Taux journalier moyen HT vendu au client (prix catalogue).", required=True)
    