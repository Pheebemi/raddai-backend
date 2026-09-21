from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import FeePayment
from core.views import _resolve_tuition_fee


class Command(BaseCommand):
    help = 'Recalculate existing fee payment totals and statuses from current fee structures.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the repairs. Without this, only show a dry-run.')
        parser.add_argument('--student-id', type=int, help='Repair one student only.')
        parser.add_argument('--academic-year', type=int, help='Repair one academic year only.')

    def handle(self, *args, **options):
        payments = FeePayment.objects.select_related(
            'student__current_class', 'academic_year', 'fee_structure'
        ).order_by('id')
        if options.get('student_id'):
            payments = payments.filter(student_id=options['student_id'])
        if options.get('academic_year'):
            payments = payments.filter(academic_year_id=options['academic_year'])

        changes = []
        skipped = 0
        today = date.today()

        for payment in payments:
            fee_structure = _resolve_tuition_fee(payment.student, payment.academic_year)
            if not fee_structure:
                skipped += 1
                continue

            total_amount = Decimal(fee_structure.amount)
            amount_paid = Decimal(payment.amount_paid or 0)
            if amount_paid >= total_amount:
                status = FeePayment.PaymentStatus.PAID
            elif amount_paid > 0:
                status = (
                    FeePayment.PaymentStatus.OVERDUE
                    if payment.due_date and payment.due_date < today
                    else FeePayment.PaymentStatus.PARTIAL
                )
            else:
                status = (
                    FeePayment.PaymentStatus.OVERDUE
                    if payment.due_date and payment.due_date < today
                    else FeePayment.PaymentStatus.PENDING
                )

            if (
                payment.fee_structure_id != fee_structure.id
                or payment.total_amount != total_amount
                or payment.status != status
            ):
                changes.append((payment, fee_structure, total_amount, status))

        mode = 'Applying' if options['apply'] else 'Dry run'
        self.stdout.write(f'{mode}: {len(changes)} payment(s) need repair; {skipped} skipped without a matching fee.')
        for payment, fee_structure, total_amount, status in changes:
            self.stdout.write(
                f'  Payment {payment.id}: total {payment.total_amount} -> {total_amount}, '
                f'status {payment.status} -> {status}, fee structure {fee_structure.id}'
            )

        if options['apply'] and changes:
            with transaction.atomic():
                for payment, fee_structure, total_amount, status in changes:
                    payment.fee_structure = fee_structure
                    payment.total_amount = total_amount
                    payment.status = status
                    payment.save(update_fields=['fee_structure', 'total_amount', 'status'])
            self.stdout.write(self.style.SUCCESS(f'Repaired {len(changes)} payment(s).'))