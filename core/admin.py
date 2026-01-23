from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
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
    list_display = ('name', 'grade', 'section', 'academic_year', 'class_teacher')
    list_filter = ('grade', 'academic_year', 'class_teacher')
    search_fields = ('name', 'class_teacher__user__first_name', 'class_teacher__user__last_name')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'description')
    search_fields = ('name', 'code')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'current_class', 'admission_date')
    list_filter = ('current_class', 'admission_date')
    search_fields = ('user__first_name', 'user__last_name', 'student_id')
    raw_id_fields = ('user', 'current_class')


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'staff_id', 'designation', 'joining_date')
    list_filter = ('designation', 'joining_date', 'qualification')
    search_fields = ('user__first_name', 'user__last_name', 'staff_id')
    raw_id_fields = ('user',)
    filter_horizontal = ('subjects',)


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'parent_id')
    search_fields = ('user__first_name', 'user__last_name', 'parent_id')
    raw_id_fields = ('user',)
    filter_horizontal = ('children',)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'academic_year', 'term', 'marks_obtained', 'total_marks', 'grade', 'uploaded_by')
    list_filter = ('academic_year', 'term', 'subject', 'uploaded_by')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'subject__name')
    raw_id_fields = ('student', 'subject', 'academic_year', 'uploaded_by')


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'grade', 'fee_type', 'amount', 'description')
    list_filter = ('academic_year', 'grade', 'fee_type')
    search_fields = ('description',)


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
