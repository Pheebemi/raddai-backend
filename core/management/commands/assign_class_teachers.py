from django.core.management.base import BaseCommand
from core.models import Staff, Class


class Command(BaseCommand):
    help = 'Assign class teachers to classes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--staff-id',
            type=str,
            help='Staff ID to assign as class teacher',
        )
        parser.add_argument(
            '--class-id',
            type=str,
            help='Class name to assign teacher to',
        )
        parser.add_argument(
            '--auto-assign',
            action='store_true',
            help='Automatically assign available teachers to classes',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        staff_id = options['staff_id']
        class_name = options['class_id']
        auto_assign = options['auto_assign']
        dry_run = options['dry_run']

        if staff_id and class_name:
            # Assign specific staff to specific class
            self.assign_specific_staff_to_class(staff_id, class_name, dry_run)
        elif auto_assign:
            # Auto-assign available teachers to classes
            self.auto_assign_teachers(dry_run)
        else:
            # Show current assignments and available options
            self.show_assignments()

    def assign_specific_staff_to_class(self, staff_id, class_name, dry_run):
        try:
            staff = Staff.objects.get(staff_id=staff_id)
        except Staff.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Staff member with ID {staff_id} not found'))
            return

        try:
            class_obj = Class.objects.get(name=class_name)
        except Class.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Class {class_name} not found'))
            return

        if class_obj.class_teacher:
            self.stdout.write(self.style.WARNING(
                f'Class {class_name} already has a teacher: {class_obj.class_teacher.user.get_full_name()}'
            ))
            return

        if staff.class_teacher:
            self.stdout.write(self.style.WARNING(
                f'Staff {staff.user.get_full_name()} is already assigned to class: {staff.class_teacher.name}'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would assign {staff.user.get_full_name()} as teacher for {class_name}'
            ))
        else:
            class_obj.class_teacher = staff
            class_obj.save()
            self.stdout.write(self.style.SUCCESS(
                f'Assigned {staff.user.get_full_name()} as teacher for {class_name}'
            ))

    def auto_assign_teachers(self, dry_run):
        # Find classes without teachers
        classes_without_teachers = Class.objects.filter(class_teacher__isnull=True).order_by('grade', 'section')

        # Find staff without class assignments
        available_staff = Staff.objects.filter(class_teacher__isnull=True).order_by('joining_date')

        if not classes_without_teachers:
            self.stdout.write(self.style.SUCCESS('All classes already have teachers assigned'))
            return

        if not available_staff:
            self.stdout.write(self.style.WARNING('No available staff members for assignment'))
            return

        assignments = []
        staff_index = 0

        for class_obj in classes_without_teachers:
            if staff_index < len(available_staff):
                staff = available_staff[staff_index]
                assignments.append((staff, class_obj))
                staff_index += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would make {len(assignments)} assignments'))
            for staff, class_obj in assignments:
                self.stdout.write(f'  {staff.user.get_full_name()} -> {class_obj.name}')
        else:
            assigned_count = 0
            for staff, class_obj in assignments:
                class_obj.class_teacher = staff
                class_obj.save()
                assigned_count += 1

            self.stdout.write(self.style.SUCCESS(f'Successfully assigned {assigned_count} teachers to classes'))

    def show_assignments(self):
        self.stdout.write('Current Class Teacher Assignments:')
        self.stdout.write('=' * 50)

        classes = Class.objects.select_related('class_teacher__user').order_by('grade', 'section')
        for class_obj in classes:
            teacher_name = class_obj.class_teacher.user.get_full_name() if class_obj.class_teacher else 'Not Assigned'
            self.stdout.write(f'{class_obj.name:15} | {teacher_name}')

        self.stdout.write('\nUnassigned Classes:')
        unassigned_classes = Class.objects.filter(class_teacher__isnull=True)
        for class_obj in unassigned_classes:
            self.stdout.write(f'  - {class_obj.name}')

        self.stdout.write('\nAvailable Staff:')
        available_staff = Staff.objects.filter(class_teacher__isnull=True).select_related('user')
        for staff in available_staff:
            self.stdout.write(f'  - {staff.user.get_full_name()} ({staff.staff_id})')