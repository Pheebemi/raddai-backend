from django.core.management.base import BaseCommand
from core.models import AcademicYear, Class


CLASSES = [
    # (name, grade)
    ('Primary 1', 1),
    ('Primary 2', 2),
    ('Primary 3', 3),
    ('Primary 4', 4),
    ('Primary 5', 5),
    ('Primary 6', 6),
    ('JSS 1',     7),
    ('JSS 2',     8),
    ('JSS 3',     9),
    ('SS 1',      10),
    ('SS 2',      11),
    ('SS 3',      12),
]

SECTIONS = ['A', 'B', 'C']


class Command(BaseCommand):
    help = 'Create all classes (Primary 1-6, JSS 1-3, SS 1-3) with sections A/B/C for 2025/2026'

    def handle(self, *args, **options):
        # Get or create the academic year
        academic_year, created = AcademicYear.objects.get_or_create(
            name='2025/2026',
            defaults={
                'start_date': '2025-09-01',
                'end_date': '2026-07-31',
                'is_active': True,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('Created academic year 2025/2026'))
        else:
            self.stdout.write('Academic year 2025/2026 already exists')

        created_count = 0
        skipped_count = 0

        for class_name, grade in CLASSES:
            for section in SECTIONS:
                full_name = f'{class_name} {section}'
                obj, was_created = Class.objects.get_or_create(
                    grade=grade,
                    section=section,
                    academic_year=academic_year,
                    defaults={'name': full_name}
                )
                if was_created:
                    self.stdout.write(f'  Created: {full_name}')
                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone — {created_count} classes created, {skipped_count} already existed.'
            )
        )
