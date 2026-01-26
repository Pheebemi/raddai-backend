from django.core.management.base import BaseCommand
from core.models import Student, Class


class Command(BaseCommand):
    help = 'Assign students to classes based on grade level'

    def add_arguments(self, parser):
        parser.add_argument(
            '--grade',
            type=int,
            help='Grade level to assign students to',
        )
        parser.add_argument(
            '--academic-year',
            type=str,
            help='Academic year name',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        grade = options['grade']
        academic_year_name = options['academic_year']
        dry_run = options['dry_run']

        if not grade:
            self.stdout.write(
                self.style.ERROR('Grade is required. Use --grade to specify the grade level.')
            )
            return

        # Find students without classes in the specified grade
        students_to_assign = Student.objects.filter(
            current_class__isnull=True
        ).select_related('user')

        # Find available classes for this grade
        classes_query = Class.objects.filter(grade=grade)
        if academic_year_name:
            classes_query = classes_query.filter(academic_year__name=academic_year_name)

        available_classes = list(classes_query.order_by('section'))

        if not available_classes:
            self.stdout.write(
                self.style.ERROR(f'No classes found for grade {grade}')
            )
            return

        self.stdout.write(f'Found {len(available_classes)} classes for grade {grade}:')
        for cls in available_classes:
            self.stdout.write(f'  - {cls.name} (Current students: {cls.students.count()})')

        # Assign students to classes
        assignments = []
        class_index = 0

        for student in students_to_assign:
            # Simple round-robin assignment
            assigned_class = available_classes[class_index % len(available_classes)]
            assignments.append((student, assigned_class))
            class_index += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would assign {len(assignments)} students to classes')
            )
            for student, assigned_class in assignments:
                self.stdout.write(f'  {student.user.get_full_name()} -> {assigned_class.name}')
        else:
            assigned_count = 0
            for student, assigned_class in assignments:
                student.current_class = assigned_class
                student.save()
                assigned_count += 1

            self.stdout.write(
                self.style.SUCCESS(f'Successfully assigned {assigned_count} students to classes')
            )