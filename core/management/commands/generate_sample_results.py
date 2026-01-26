import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Student, Subject, AcademicYear, Result, Staff


class Command(BaseCommand):
    help = 'Generate sample result data with CA and exam scores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--academic-year',
            type=str,
            default='2023-2024',
            help='Academic year for the results',
        )
        parser.add_argument(
            '--term',
            type=str,
            choices=['first', 'second', 'third', 'final'],
            default='first',
            help='Term for the results',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing results before generating new ones',
        )

    def handle(self, *args, **options):
        academic_year_name = options['academic_year']
        term = options['term']
        clear_existing = options['clear_existing']

        # Get academic year
        try:
            academic_year = AcademicYear.objects.get(name=academic_year_name)
        except AcademicYear.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Academic year {academic_year_name} not found')
            )
            return

        # Get all subjects
        subjects = list(Subject.objects.all())
        if not subjects:
            self.stdout.write(self.style.ERROR('No subjects found. Please create subjects first.'))
            return

        # Get all students
        students = list(Student.objects.filter(current_class__isnull=False))
        if not students:
            self.stdout.write(self.style.ERROR('No students with class assignments found.'))
            return

        # Get staff for uploading results
        try:
            staff = Staff.objects.filter(designation='teacher').first()
            if not staff:
                staff = Staff.objects.first()
        except Staff.DoesNotExist:
            self.stdout.write(self.style.ERROR('No staff members found to assign as result uploader.'))
            return

        if clear_existing:
            deleted_count = Result.objects.filter(
                academic_year=academic_year,
                term=term
            ).delete()[0]
            self.stdout.write(f'Cleared {deleted_count} existing results.')

        created_count = 0
        for student in students:
            for subject in subjects:
                # Check if result already exists
                existing_result = Result.objects.filter(
                    student=student,
                    subject=subject,
                    academic_year=academic_year,
                    term=term
                ).first()

                if existing_result and not clear_existing:
                    continue

                # Generate CA scores (0-10 each)
                ca1_score = round(random.uniform(6, 10), 1)
                ca2_score = round(random.uniform(6, 10), 1)
                ca3_score = round(random.uniform(6, 10), 1)
                ca4_score = round(random.uniform(6, 10), 1)

                # Generate exam score (0-60)
                exam_score = round(random.uniform(35, 60), 1)

                # Create or update result
                result, created = Result.objects.get_or_create(
                    student=student,
                    subject=subject,
                    academic_year=academic_year,
                    term=term,
                    defaults={
                        'ca1_score': ca1_score,
                        'ca2_score': ca2_score,
                        'ca3_score': ca3_score,
                        'ca4_score': ca4_score,
                        'exam_score': exam_score,
                        'uploaded_by': staff,
                    }
                )

                if not created:
                    # Update existing result
                    result.ca1_score = ca1_score
                    result.ca2_score = ca2_score
                    result.ca3_score = ca3_score
                    result.ca4_score = ca4_score
                    result.exam_score = exam_score
                    result.uploaded_by = staff
                    result.save()

                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated {created_count} result records for {len(students)} students '
                f'and {len(subjects)} subjects in {academic_year_name} term {term}.'
            )
        )

        # Show some statistics
        results = Result.objects.filter(academic_year=academic_year, term=term)
        if results:
            avg_percentage = sum(result.percentage for result in results) / len(results)
            grade_distribution = {}
            for result in results:
                grade = result.grade
                grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

            self.stdout.write(f'\nStatistics for {term} term {academic_year_name}:')
            self.stdout.write('.1f')
            self.stdout.write('Grade Distribution:')
            for grade, count in sorted(grade_distribution.items()):
                self.stdout.write(f'  {grade}: {count} students')