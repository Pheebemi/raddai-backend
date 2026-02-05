from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django import forms
from .models import (
    User, AcademicYear, Class, Subject, Student, Staff, Parent,
    Result, FeeStructure, FeePayment, Announcement, Attendance
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Custom admin for User model with role-based display"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone_number', 'date_of_birth', 'address')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone_number', 'date_of_birth', 'address')}),
    )


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date')
    search_fields = ('name',)


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade', 'section', 'academic_year', 'class_teacher', 'get_student_count', 'get_teacher_status')
    list_filter = ('grade', 'academic_year', 'section', 'class_teacher')
    search_fields = ('name', 'class_teacher__user__first_name', 'class_teacher__user__last_name')
    autocomplete_fields = ('class_teacher', 'academic_year')

    def get_teacher_status(self, obj):
        if obj.class_teacher:
            return '✓ Assigned'
        return '⚠ Needs Teacher'
    get_teacher_status.short_description = 'Teacher Status'
    get_teacher_status.admin_order_field = 'class_teacher'

    def get_student_count(self, obj):
        return obj.students.count()
    get_student_count.short_description = 'Students'

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'grade', 'section', 'academic_year')
        }),
        ('Assignments', {
            'fields': ('class_teacher',),
            'description': 'Assign a class teacher for this class. Only staff members will appear in the dropdown.'
        }),
    )

    # Custom queryset for class_teacher field to only show staff members
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "class_teacher":
            kwargs["queryset"] = Staff.objects.select_related('user')
            # Format the display to show staff name and designation
            kwargs["empty_label"] = "Select Class Teacher"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Add an inline for students in this class
    class StudentInline(admin.TabularInline):
        model = Student
        verbose_name = "Student"
        verbose_name_plural = "Students"
        fields = ('user', 'student_id', 'admission_date')
        readonly_fields = ('user', 'student_id', 'admission_date')
        can_delete = False
        max_num = 0  # Read-only
        extra = 0

        def has_add_permission(self, request, obj=None):
            return False

        def has_delete_permission(self, request, obj=None):
            return False

    # Add actions for class management
    actions = ['assign_class_teacher', 'remove_class_teacher']

    def assign_class_teacher(self, request, queryset):
        # Only allow assigning to one class at a time
        if queryset.count() > 1:
            self.message_user(request, "Please select only one class to assign a teacher to.", level='error')
            return

        class_obj = queryset.first()

        if class_obj.class_teacher:
            self.message_user(request, f"{class_obj.name} already has a class teacher: {class_obj.class_teacher.user.get_full_name()}", level='warning')
            return

        # Find available staff (not assigned to any class)
        available_staff = Staff.objects.filter(class_teacher__isnull=True).select_related('user')

        if not available_staff:
            self.message_user(request, "No available staff members. All staff are already assigned to classes.", level='warning')
            return

        # For now, assign the first available staff
        # In a real application, you'd want a form to select which staff member
        assigned_staff = available_staff.first()
        class_obj.class_teacher = assigned_staff
        class_obj.save()

        self.message_user(request, f"Assigned {assigned_staff.user.get_full_name()} as class teacher for {class_obj.name}")

    assign_class_teacher.short_description = "Assign a teacher to selected class(es)"

    def remove_class_teacher(self, request, queryset):
        updated = 0
        for class_obj in queryset:
            if class_obj.class_teacher:
                class_obj.class_teacher = None
                class_obj.save()
                updated += 1

        self.message_user(request, f"Removed class teachers from {updated} classes.")
    remove_class_teacher.short_description = "Remove class teacher from selected classes"

    inlines = [StudentInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'description')
    search_fields = ('name', 'code')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'current_class', 'admission_date', 'get_class_grade', 'get_section')
    list_filter = ('current_class__grade', 'current_class__academic_year', 'admission_date', 'current_class__section')
    search_fields = ('user__first_name', 'user__last_name', 'student_id', 'user__username')
    raw_id_fields = ('user',)
    autocomplete_fields = ('current_class',)

    def get_class_grade(self, obj):
        return obj.current_class.grade if obj.current_class else None
    get_class_grade.short_description = 'Grade'
    get_class_grade.admin_order_field = 'current_class__grade'

    def get_section(self, obj):
        return obj.current_class.section if obj.current_class else None
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'current_class__section'

    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Academic Information', {
            'fields': ('student_id', 'current_class', 'admission_date'),
            'description': 'Assign the student to a class. Classes are filtered by grade and academic year.'
        }),
        ('Additional Information', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone', 'medical_info'),
            'classes': ('collapse',)
        }),
    )

    # Custom formfield to make class selection more user-friendly
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "current_class":
            kwargs["queryset"] = Class.objects.select_related('academic_year').order_by('grade', 'section')
            kwargs["empty_label"] = "Select Class"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Add actions for bulk operations
    actions = ['assign_to_class', 'remove_from_class']

    def assign_to_class(self, request, queryset):
        # For now, just show a message with instructions
        students_without_class = queryset.filter(current_class__isnull=True).count()
        students_with_class = queryset.filter(current_class__isnull=False).count()

        message = f"Selected {queryset.count()} students. "
        if students_without_class > 0:
            message += f"{students_without_class} have no class assigned. "
        if students_with_class > 0:
            message += f"{students_with_class} already have classes assigned."

        message += " Use the 'current_class' field in each student's form to assign them individually."
        self.message_user(request, message)
    assign_to_class.short_description = "Check class assignments for selected students"

    def remove_from_class(self, request, queryset):
        updated = queryset.update(current_class=None)
        self.message_user(request, f"Removed {updated} students from their classes.")
    remove_from_class.short_description = "Remove selected students from their classes"


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'staff_id', 'designation', 'joining_date', 'get_assigned_classes_count', 'get_subjects_count', 'get_class_assignment_status')
    list_filter = ('designation', 'joining_date', 'qualification', 'subjects')
    search_fields = ('user__first_name', 'user__last_name', 'staff_id', 'user__username')
    raw_id_fields = ('user',)
    filter_horizontal = ('subjects',)
    autocomplete_fields = ('subjects',)

    def get_class_assignment_status(self, obj):
        if obj.class_teacher:
            return f'✓ {obj.class_teacher.name}'
        return '⚠ Available'
    get_class_assignment_status.short_description = 'Class Assignment'

    def get_assigned_classes_count(self, obj):
        return 1 if obj.class_teacher else 0
    get_assigned_classes_count.short_description = 'Classes Assigned'

    def get_subjects_count(self, obj):
        return obj.subjects.count()
    get_subjects_count.short_description = 'Subjects'

    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Employment Details', {
            'fields': ('staff_id', 'designation', 'joining_date', 'qualification', 'experience_years')
        }),
        ('Academic Assignments', {
            'fields': ('subjects',),
            'description': 'Select subjects this staff member teaches. Use Ctrl+Click to select multiple subjects.'
        }),
    )

    # Custom formfield for subjects to show more info
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "subjects":
            kwargs["queryset"] = Subject.objects.order_by('name')
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    # Note: Removed ClassTeacherInline because OneToOne relationships don't work well with inlines
    # The class assignment is handled through the Class model's class_teacher field

    # Add actions for bulk operations
    actions = ['assign_to_class', 'assign_subjects', 'remove_from_classes']

    def assign_to_class(self, request, queryset):
        # Only allow assigning one staff member at a time to avoid conflicts
        if queryset.count() > 1:
            self.message_user(request, "Please select only one staff member to assign to a class.", level='error')
            return

        staff = queryset.first()

        # Find classes that don't have a class teacher
        available_classes = Class.objects.filter(class_teacher__isnull=True).order_by('grade', 'section')

        if not available_classes:
            self.message_user(request, "No classes available for assignment. All classes already have teachers.", level='warning')
            return

        # For now, assign to the first available class
        # In a real application, you'd want a form to select which class
        assigned_class = available_classes.first()
        assigned_class.class_teacher = staff
        assigned_class.save()

        self.message_user(request, f"Assigned {staff.user.get_full_name()} as class teacher for {assigned_class.name}")

    assign_to_class.short_description = "Assign selected staff to an available class"

    def assign_subjects(self, request, queryset):
        # This would typically open a form to select subjects
        self.message_user(request, f"Selected {queryset.count()} staff members for subject assignment.")
    assign_subjects.short_description = "Assign subjects to selected staff"

    def remove_from_classes(self, request, queryset):
        # Remove staff from their assigned classes
        updated = 0
        for staff in queryset:
            if staff.class_teacher:
                staff.class_teacher.class_teacher = None
                staff.class_teacher.save()
                updated += 1

        self.message_user(request, f"Removed {updated} staff members from their class assignments.")
    remove_from_classes.short_description = "Remove selected staff from their assigned classes"


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'parent_id', 'get_children_count', 'get_children_names')
    search_fields = ('user__first_name', 'user__last_name', 'parent_id', 'children__user__first_name', 'children__user__last_name')
    raw_id_fields = ('user',)
    filter_horizontal = ('children',)
    autocomplete_fields = ('children',)

    def get_children_count(self, obj):
        return obj.children.count()
    get_children_count.short_description = 'Children'

    def get_children_names(self, obj):
        return ", ".join([f"{child.user.get_full_name()} ({child.current_class.name if child.current_class else 'No Class'})"
                         for child in obj.children.all()])
    get_children_names.short_description = 'Children Details'

    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Parent Details', {
            'fields': ('parent_id',)
        }),
        ('Family Information', {
            'fields': ('children',),
            'description': 'Select the children associated with this parent'
        }),
    )

    # Add an inline for children details
    class ChildInline(admin.TabularInline):
        model = Parent.children.through  # Through model for ManyToMany
        verbose_name = "Child"
        verbose_name_plural = "Children"
        fields = ('student_details',)
        readonly_fields = ('student_details',)
        can_delete = True
        max_num = 0
        extra = 0

        def student_details(self, obj):
            student = obj.student
            return f"{student.user.get_full_name()} - {student.student_id} - Class: {student.current_class.name if student.current_class else 'Not Assigned'}"
        student_details.short_description = 'Student Details'

    # Note: Django doesn't support inlines for ManyToMany through models easily,
    # so we'll stick with filter_horizontal for now


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'recorded_class', 'academic_year', 'term', 'ca_total', 'exam_score', 'marks_obtained', 'grade', 'uploaded_by', 'upload_date')
    list_filter = ('academic_year', 'term', 'subject', 'grade', 'uploaded_by', 'recorded_class')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'subject__name')
    raw_id_fields = ('student', 'subject', 'academic_year', 'uploaded_by', 'recorded_class')

    fieldsets = (
        ('Student & Subject Information', {
            'fields': ('student', 'subject', 'recorded_class', 'academic_year', 'term'),
            'description': 'Select the class the student was in when this result was recorded. This should match the class they were assigned to during this academic year.'
        }),
        ('Continuous Assessment Scores (10 marks each)', {
            'fields': ('ca1_score', 'ca2_score', 'ca3_score', 'ca4_score'),
            'description': 'Enter scores for each Continuous Assessment test (maximum 10 marks each)'
        }),
        ('Final Examination', {
            'fields': ('exam_score',),
            'description': 'Enter the final examination score (maximum 60 marks)'
        }),
        ('Calculated Results', {
            'fields': ('marks_obtained', 'grade', 'remarks'),
            'description': 'These fields are automatically calculated based on CA and exam scores',
            'classes': ('collapse',)
        }),
        ('Administrative Information', {
            'fields': ('uploaded_by', 'upload_date'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('marks_obtained', 'grade', 'upload_date')

    # Custom form validation
    def clean_ca_score(self, score, field_name):
        """Validate CA scores are between 0 and 10"""
        if score < 0 or score > 10:
            raise ValidationError(f"{field_name} must be between 0 and 10 marks")
        return score

    def clean_exam_score(self, score):
        """Validate exam score is between 0 and 60"""
        if score < 0 or score > 60:
            raise ValidationError("Exam score must be between 0 and 60 marks")
        return score

    # Add form validation
    def save_model(self, request, obj, form, change):
        # Validate scores before saving
        if obj.ca1_score < 0 or obj.ca1_score > 10:
            self.message_user(request, "CA1 score must be between 0 and 10", level='error')
            return
        if obj.ca2_score < 0 or obj.ca2_score > 10:
            self.message_user(request, "CA2 score must be between 0 and 10", level='error')
            return
        if obj.ca3_score < 0 or obj.ca3_score > 10:
            self.message_user(request, "CA3 score must be between 0 and 10", level='error')
            return
        if obj.ca4_score < 0 or obj.ca4_score > 10:
            self.message_user(request, "CA4 score must be between 0 and 10", level='error')
            return
        if obj.exam_score < 0 or obj.exam_score > 60:
            self.message_user(request, "Exam score must be between 0 and 60", level='error')
            return

        super().save_model(request, obj, form, change)


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'grade', 'fee_type', 'amount', 'description')
    list_filter = ('academic_year', 'grade', 'fee_type')
    search_fields = ('description',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Get unique grades from existing classes and create choices
        grades = Class.objects.values_list('grade', flat=True).distinct().order_by('grade')
        grade_choices = [(grade, f'Grade {grade}') for grade in grades]

        # Replace the grade field with a choice field
        form.base_fields['grade'].widget = forms.Select(choices=grade_choices)
        return form

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'grade':
            # Get unique grades from Class model
            grades = Class.objects.values_list('grade', flat=True).distinct().order_by('grade')
            choices = [(grade, f'Grade {grade}') for grade in grades]
            kwargs['choices'] = choices
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make grade field a choice field with available grades
        grades = Class.objects.values_list('grade', flat=True).distinct().order_by('grade')
        grade_choices = [(grade, f'Grade {grade}') for grade in grades]
        form.base_fields['grade'] = forms.ChoiceField(choices=grade_choices)
        return form


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_structure', 'amount_paid', 'total_amount', 'status', 'payment_date', 'due_date')
    list_filter = ('status', 'payment_date', 'due_date', 'fee_structure__fee_type')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'transaction_id')
    raw_id_fields = ('student', 'fee_structure')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'created_by', 'created_at', 'is_active')
    list_filter = ('priority', 'is_active', 'created_at', 'for_students', 'for_parents', 'for_staff', 'for_management')
    search_fields = ('title', 'content')
    raw_id_fields = ('created_by',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'class_period')
    list_filter = ('status', 'date', 'class_period')
    search_fields = ('student__user__first_name', 'student__user__last_name')
    raw_id_fields = ('student', 'class_period', 'marked_by')
