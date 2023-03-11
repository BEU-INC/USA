# -*- coding: utf-8 -*-

from odoo.tools import format_amount
from odoo import api, fields, models, _


class AccountMove(models.Model):

    _inherit = "account.move"

    def get_product_names(self):
        s = ''
        if self.invoice_line_ids:
            s = ', '.join(self.invoice_line_ids.filtered(lambda line: line.display_type == 'product').mapped('product_id').mapped('name'))
        return s

    def get_invoice_url(self):
        token = self.access_token
        if token == '':
            token = self._portal_ensure_token()
        url = '/my/invoices/{0}?access_token={1}'.format(str(self.id), str(token))
        return url

    def get_amount_str(self, amount):
        return str(format_amount(self.env, amount, self.currency_id)).replace('$', '').replace('€', '')

    def get_invoice_date_print(self):
        s = ''
        if self.invoice_date:
            s += self.invoice_date.strftime('%d de')
            s += " " + self.invoice_date.strftime('%m de').replace('01','Enero').replace('02','Febrero').replace('03','Marzo').replace('04','Abril').replace('05','Mayo').replace('06','Junio').replace('07','Julio').replace('08','Agosto').replace('09','Septiembre').replace('10','Octubre').replace('11','Noviembre').replace('12','Diciembre')
            s += " " + self.invoice_date.strftime('%Y')
        return s

    def _get_mail_template(self):
        """
        :return: the correct mail template based on the current move type
        """
        return (
            'account.email_template_edi_credit_note'
            if all(move.move_type == 'out_refund' for move in self)
            else 'custom_invoice_email_template.email_template_edi_invoice_custom'
        )

    def action_send_and_print(self):
        return {
            'name': _('Send Invoice'),
            'res_model': 'account.invoice.send',
            'view_mode': 'form',
            'context': {
                'default_email_layout_xmlid': False,
                'default_template_id': self.env.ref(self._get_mail_template()).id,
                'mark_invoice_as_sent': True,
                'active_model': 'account.move',
                # Setting both active_id and active_ids is required, mimicking how direct call to
                # ir.actions.act_window works
                'active_id': self.ids[0],
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def action_invoice_sent(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        template = self.env.ref(self._get_mail_template(), raise_if_not_found=False)
        lang = False
        if template:
            lang = template._render_lang(self.ids)[self.id]
        if not lang:
            lang = get_lang(self.env).code
        compose_form = self.env.ref('account.account_invoice_send_wizard_form', raise_if_not_found=False)
        ctx = dict(
            default_model='account.move',
            default_res_id=self.id,
            # For the sake of consistency we need a default_res_model if
            # default_res_id is set. Not renaming default_model as it can
            # create many side-effects.
            default_res_model='account.move',
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            mark_invoice_as_sent=True,
            default_email_layout_xmlid=False,
            model_description=self.with_context(lang=lang).type_name,
            force_email=True,
            active_ids=self.ids,
        )

        report_action = {
            'name': _('Send Invoice'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.invoice.send',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

        if self.env.is_admin() and not self.env.company.external_report_layout_id and not self.env.context.get('discard_logo_check'):
            return self.env['ir.actions.report']._action_configure_external_report_layout(report_action)

        return report_action