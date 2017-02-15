from openerp import api, fields, models
import datetime
import time
from datetime import date,timedelta
from dateutil.relativedelta import relativedelta
from openerp.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)
#         _logger.info("PAYROLL ID=%i",record.payroll_id.name.id)
# _logger.info should be inside function
class hr_contract(models.Model):
    _inherit = 'hr.contract'
    _description = 'Extends hr.contract to add new fields'
    bagged_mult = fields.Float('Bagged Multiplier', digits=(5, 2), required=True, default=2,
                               help="Multiplier for Bagger Commission. Varies per Bagger")
    bagsold_mult = fields.Float('Bags Sold Multiplier', digits=(5, 2), required=True, default=1,
                               help="Multiplier for Bag Seller Commission. Varies per seller")
    cratesold_mult = fields.Float('Crates Sold Multiplier', digits=(5, 2), required=True, default=5,
                               help="Multiplier for Crates Seller Commission. Varies per seller")
    dispsold_mult = fields.Float('Dispenser Sold Multiplier', digits=(5, 2), required=True, default=25,
                               help="Multiplier for Dispenser Seller Commission. Varies per seller")
    sal_adv = fields.Float('Salary Advance Ded', digits=(7, 2), required=True, 
                               help="Salary Advance. Varies per individual")
    loan_adv = fields.Float('Loan Advance Ded', digits=(7, 2), required=True, 
                               help="Loan Advance. Varies per individual")
    payee = fields.Float('PAYEE TAX Ded', digits=(7, 2), required=True, 
                               help="PAYEE TAX. Varies per individual")
    days_absent = fields.Float('Days Absent', digits=(4,2), required=True,
                               help="Days absent from Work in Month. Affects Base Salary")

    
class fido_payroll(models.Model):
    _name = "fido.payroll"
    _inherit = 'mail.thread'
    _description = 'Fido Payroll Architecture'
    name = fields.Many2one('hr.employee', string='Payroll Staff', domain="[('company_id','=','FIDO PRODUCING LTD')]", required=True)
    emp_userid = fields.Char(readonly=True,string='user_id')
    emp_name = fields.Char(readonly=True,string='emp_name')
    emp_id = fields.Char(readonly=True,string='emp_id')
    emp_userid_name = fields.Char(readonly=True,string='emp_id')
    phone = fields.Char(related='name.mobile_phone')
    start_date = fields.Date('Date Begin',default=(date.today() + relativedelta(day=1)))
    end_date = fields.Date('Date End',default=date.today())
        
    work_days_tot = fields.Integer(compute='get_workdays', string='Total Work Days',store=True)
    note = fields.Text(string='Miscellaneous Notes')
    payroll_ref = fields.Char(compute='get_workdays',readonly=True,string='Payroll ID',store=True)
    payroll_line_ids = fields.One2many('fido.payroll.line', 'payroll_id')
    f_mnth = fields.Char('Month',required=True, readonly=True, store=True, default=date.today().strftime('%B'))
    pay_year = fields.Char('Year',required=True, readonly=True, store=True, default=date.today().strftime('%Y'))
    payroll_total = fields.Float(compute='create_lines',digits=(9, 2), string='Total', store=True)
    absent_days = fields.Float(compute='get_absentdays',digits=(4,2),string='Absent Days',store=True)
    
    job_title = fields.Char(related='name.job_id.name',store=True)
    
    bank_account = fields.Char(related='name.bank_account_id.acc_number',store=True)
    item_id = fields.Char(compute='create_lines',string='Item Name',store=True)
    item_qty = fields.Float(string='Qty',store=True)
    item_mult = fields.Float(string='Multiplier',store=True)
#     line_total = fields.Float(string='Amount',store=True)
    product_cat = fields.Char( string='Product Category')

    @api.one
    @api.constrains('start_date', 'end_date')
    def _check_valids(self):
        if self.start_date > self.end_date:
            raise ValidationError("Field start_date must be before end_date")
        clause = [('payroll_ref', '=', self.payroll_ref)]
        if self.search(clause):
            raise ValidationError("Payroll Already Created for this staff, Delete First")
        
    def create_batch(self):
        emp_obj = self.env['hr.employee']
        clause = []
        for employee in emp_obj.search(clause):
            self.emp_id = employee.id 
            self.emp_name = employee.name
            self.emp_userid = employee.user_id
            self.emp_userid_name = employee.user_id.name
            self.create_lines()
        
    @api.one
    @api.depends('name')
    def get_absentdays(self):
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = self.env['hr.contract'].search(clause_contract)
        for contract in contract_ids:
            self.absent_days = contract.days_absent
    
    @api.one
    @api.depends('payroll_line_ids.line_total')
    def compute_payroll_total(self):
        self.payroll_total = sum(line.line_total for line in self.payroll_line_ids)
    
    top_name = fields.Char(compute='get_top_name', store=True)
    @api.one
    @api.depends('f_mnth','name')
    def get_top_name(self):
        if (self.f_mnth and self.emp_name):            
            self.top_name = self.f_mnth.upper() + ' Record' + ' for ' + self.emp_name
        else:
            self.top_name = date.today().strftime('%B') + ' Payslip '
       
    @api.one
    @api.depends('name','start_date','end_date')
    def get_workdays(self):
        
        fmt = '%Y-%m-%d'
        workdays = datetime.datetime.strptime(self.end_date, fmt) - datetime.datetime.strptime(self.start_date, fmt)          
        sundays = workdays.days / 7 
        self.work_days_tot = workdays.days - sundays
        self.payroll_ref =  'Payslip/' + str(self.emp_name) + '/' + str(self.f_mnth)

    @api.one
    @api.depends('name','start_date','end_date')
    def get_invoice_totals(self):
        
        account_invoice_obj = self.env['account.invoice.report']
        clause = [('date','>=',self.start_date),('date','<=',self.end_date),('categ_id.name','=',self.product_cat),('user_id.name','=', self.userid_name)]
        gotten_fields = account_invoice_obj.search(clause)
        _logger.info("*** LOGGING Processing INVOICE ids len %i, CATEG %s",len(gotten_fields), self.product_cat)
        total=0.0
        for account_invoice in gotten_fields:
            total += account_invoice.product_qty
        self.item_qty = total
        
    @api.one
    def get_mult(self):
        
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
        
        for contract in contract_ids:
            if self.item_id == 'Bags Sales Commission':
                self.item_mult = contract.bagsold_mult
            elif self.item_id == 'Crates Sales Commission':
                self.item_mult = contract.cratesold_mult
            elif self.item_id == 'Dispenser Sales Commission':
                self.item_mult = contract.dispsold_mult
            
    
    @api.one
    @api.depends('name','start_date','end_date')
    def get_bagger_totals(self):
        self.item_qty = 0
        self.item_mult = 0
        bagger_obj = self.env['fido.bagger']
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
#         month_f_end_date = datetime.datetime.strftime(date.today(), '%B').lower()
        month_f_end_date = self.f_mnth.lower()
        _logger.info("*** LOGGING Processing BAGGER MONTH %s",month_f_end_date)
        clause =  [('name.name', '=', self.emp_name),('x_month', '=', month_f_end_date)]
        bagger_ids = bagger_obj.search(clause)
        _logger.info("*** LOGGING Processing LEN BAGGER ids %s",len(bagger_ids))
        if len(contract_ids) > 0:
            for contract in contract_ids:
                self.item_mult = contract.bagged_mult
        if len(bagger_ids) > 0:
            for bagger in bagger_ids:            
                self.item_qty = bagger.qty_total
                _logger.info("*** LOGGING Processing BAGGER TOTALs %s",bagger.qty_total)
            
            
    @api.one    
    def get_wage(self):
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
        for contract in contract_ids:
            if contract.date_end and contract.date_end <= self.start_date:
                self.item_qty = 0
                self.item_mult = 0
            else:
                self.item_qty = contract.wage
                self.item_mult = 1
            
    @api.one   
    def get_loan(self):
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
        for contract in contract_ids:
            self.item_qty = -1
            self.item_mult = contract.loan_adv
            
    @api.one    
    def get_sal(self):
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
        for contract in contract_ids:
            self.item_qty = -1
            self.item_mult = contract.sal_adv

    @api.one    
    def get_tax(self):
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
        for contract in contract_ids:
            self.item_qty = -1
            self.item_mult = contract.payee
    
    @api.one    
    def get_bag_mult(self):
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
        for contract in contract_ids:
            self.item_mult = contract.bagged_mult
    
    
    @api.one    
    def get_absentee(self):
        contract_obj = self.env['hr.contract']
        clause_contract =  [('employee_id', '=', self.emp_id)]
        contract_ids = contract_obj.search(clause_contract)
        self.item_qty = -1
        for contract in contract_ids:
            if contract.date_end and contract.date_end <= self.start_date:
                self.item_qty = 0
                self.item_mult = 0        
            else:
                try:       
                    self.item_mult = (contract.days_absent / float(self.work_days_tot)) * contract.wage
                except ZeroDivisionError:
                    _logger.exception("division by zero error work days total")
        
    @api.one
    @api.depends('name','start_date','end_date')
    def create_lines(self):
        item_obj = self.env['fido.payroll.item']
        itemid = item_obj.search([])    
        for item in itemid:
           
            self.item_id = item.name
            self.set_items(item.name)
            item_id = self.item_id
            item_qty = self.item_qty
            item_mult = self.item_mult
            line_total = item_qty * item_mult
            self.payroll_total += line_total
            #self.line_total = line_total
            # self.item_id = item.name       
            _logger.info("*** MAJOR CREATE_LINE ITEM ID,QTY, MULT %s %s %s",item_id, item_qty, item_mult)
            self.env['fido.payroll.line'].create({'payroll_id':self.id,'item_id':item_id,'item_qty':item_qty,'item_mult':item_mult,'line_total':line_total})
#             self.env['fido.payroll.line'].create({'payroll_id':self.id,'item_id':self.item_id,'item_qty':self.item_qty,'item_mult':self.item_mult,'line_total':self.line_total})
            #self.line_total = 0.0
    
    @api.one
    def set_items(self,item_id):        
        self.item_id = item_id
        self.item_qty = 0
        self.item_mult = 0
               
        # self.item_id = item_id
        if self.item_id == 'Bags Sales Commission':            
            self.product_cat = 'PUREWATER'
            _logger.info("*** LOGGING Processing BAGS SALES Entering INVOICE %s ",self.item_id)
            self.get_invoice_totals()
            self.get_mult()    
          
        elif self.item_id == 'Dispenser Sales Commission':
            self.product_cat = 'DISPENSER'
            self.get_invoice_totals()
            self.get_mult()
    #       
        elif self.item_id == 'Crates Sales Commission':
            self.product_cat = 'BOTTLE CRATES'
            self.get_invoice_totals()
            self.get_mult()
        elif self.item_id == 'Bagging Commission': 
            self.get_bagger_totals()                                
                
        elif self.item_id == 'Salary Advance Deduction(-ve)':
            _logger.info("*** LOGGING Processing  %s ",self.item_id)
            self.get_sal()
            
        elif self.item_id == 'Base Salary':
            self.get_wage()        
                
        elif self.item_id == 'Loan Advance Deduction(-ve)':
            _logger.info("*** LOGGING Processing  = %s ",self.item_id)
            self.get_loan()
                
        elif self.item_id == 'PAYEE TAX Deduction(-ve)':
            _logger.info("*** LOGGING Processing  = %s ",self.item_id)
            self.get_tax()
        elif self.item_id == 'Absentee Deductions':
            _logger.info("*** LOGGING Processing  = %s ",self.item_id)
            self.get_absentee()
            
                        
class fido_payroll_item(models.Model):
    _name = "fido.payroll.item"
    _description = "Fido Payroll Items"
    name = fields.Char("Fido Payroll Commission Item")


class fido_payroll_line(models.Model):
    _name = "fido.payroll.line"
    _description = "Fido Payroll lines"
    payroll_id = fields.Many2one('fido.payroll', string='Fido Reference')
#  Fields for Bags, disp and crates sold totals
    
# base_salary pick from staff record
#  Each line is for a payroll commission item
# Items vary and can be bags, dispensers, crates
# See Model payroll items
#     item_id = fields.Many2one('fido.payroll.item','Commission Item')
    item_id = fields.Char('Commission Item')
    item_qty = fields.Float(string='Qty')
    item_mult = fields.Float(string='Multiplier')
    line_total = fields.Float(string='Amount')

            
class fido_payroll_employee_inherit(models.Model):
    _inherit ='hr.employee'
    _name = 'hr.employee'
    _description = "Fido Payroll Inherits from hr.employee to add payroll counts"
    pay_log = fields.Float(compute='pay_count', string='Fido Slip')
    
    @api.one
    def pay_count(self):
        for record in self:
            record_count = self.pool.get('fido.payroll')
            pay_logger = record_count.search(self._cr,self._uid, [('name','=',record.id)])
            record.pay_log = len(pay_logger)

# class account_invoice_inherit(models.Model):
#     _inherit = 'account.invoice'
#     _description = 'Changes the link between Customer name and salesperson'
#     partner_id = fields.Many2one('res.partner', string='Partner', change_default=True,
#         required=True, readonly=True, states={'draft': [('readonly', False)]},
#         track_visibility='always')
#     user_id = fields.Many2one(related='partner_id.user_id',string='Salesperson', track_visibility='onchange',
#         readonly=True, states={'draft': [('readonly', False)]})
#     date_invoice = fields.Date(string='Invoice Date',default=date.today(),
#         readonly=True, states={'draft': [('readonly', False)]}, index=True,
#         help="Change to correct date.", copy=False)
#     
      
    