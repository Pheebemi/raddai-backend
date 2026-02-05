from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone


def get_today():
    """Return today's date"""
    return timezone.now().date()


class User(AbstractUser):
    """Custom user model with role-based authentication"""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        MANAGEMENT = 'management', 'Management'
        STAFF = 'staff', 'Staff'
        STUDENT = 'student', 'Student'
        PARENT = 'parent', 'Parent'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    # Additional fields
    phone_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$')],
        blank=True,
        null=True
    )
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    # profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)  # Temporarily disabled

    # Role-specific relationships will be accessed via reverse relations from profile models

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def get_profile(self):
        """Get the appropriate profile based on user role"""
        try:
            if self.role == self.Role.STUDENT:
                return self.student_profile
            elif self.role == self.Role.STAFF:
                return self.staff_profile
            elif self.role == self.Role.PARENT:
                return self.parent_profile
        except:
            return None
        return None


class AcademicYear(models.Model):
    """Academic year model"""
    name = models.CharField(max_length=50, unique=True)  # e.g., "2023-2024"
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class Class(models.Model):
    """School class/grade model"""
    name = models.CharField(max_length=50)  # e.g., "Grade 10", "Class A"
    grade = models.IntegerField()  # Numeric grade level (1-12)
    section = models.CharField(max_length=10, blank=True)  # e.g., "A", "B", "C"
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    class_teacher = models.OneToOneField(
        'Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='class_teacher'
    )

    class Meta:
        unique_together = ['grade', 'section', 'academic_year']
        ordering = ['grade', 'section']

    def __str__(self):
        return f"Grade {self.grade} {self.section} - {self.academic_year.name}"


class Subject(models.Model):
    """Academic subject model"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Student(models.Model):
    """Student profile model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    admission_date = models.DateField(default=get_today)
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='students')
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    medical_info = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} (ID: {self.student_id})"


class Staff(models.Model):
    """Staff/Teacher profile model"""

    class Designation(models.TextChoices):
        TEACHER = 'teacher', 'Teacher'
        PRINCIPAL = 'principal', 'Principal'
        VICE_PRINCIPAL = 'vice_principal', 'Vice Principal'
        ADMINISTRATOR = 'administrator', 'Administrator'
        LIBRARIAN = 'librarian', 'Librarian'
        COUNSELOR = 'counselor', 'Counselor'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    staff_id = models.CharField(max_length=20, unique=True)
    designation = models.CharField(max_length=20, choices=Designation.choices, default=Designation.TEACHER)
    joining_date = models.DateField(default=timezone.now)
    qualification = models.CharField(max_length=200, blank=True)
    experience_years = models.PositiveIntegerField(default=0)

    # Subjects taught by this staff member
    subjects = models.ManyToManyField(Subject, related_name='teachers', blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.designation} (ID: {self.staff_id})"


class Parent(models.Model):
    """Parent profile model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    parent_id = models.CharField(max_length=20, unique=True)

    # Relationship to children
    children = models.ManyToManyField(Student, related_name='parents', blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} (ID: {self.parent_id})"


class Result(models.Model):
    """Academic result model"""

    class Term(models.TextChoices):
        FIRST = 'first', 'First Term'
        SECOND = 'second', 'Second Term'
        THIRD = 'third', 'Third Term'
        FINAL = 'final', 'Final Exam'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.CharField(max_length=10, choices=Term.choices)
    recorded_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='recorded_results')

    # CA Scores (Continuous Assessment) - each worth 10 marks
    ca1_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="CA Test 1 (max 10 marks)")
    ca2_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="CA Test 2 (max 10 marks)")
    ca3_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="CA Test 3 (max 10 marks)")
    ca4_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="CA Test 4 (max 10 marks)")

    # Final Exam Score - worth 60 marks
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Final Exam (max 60 marks)")

    # Calculated fields
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, editable=False)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=100, editable=False)
    grade = models.CharField(max_length=5, blank=True)  # e.g., "A+", "B", "C"
    remarks = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'subject', 'academic_year', 'term']

    def save(self, *args, **kwargs):
        """Calculate total marks obtained before saving"""
        # CA scores total (40 marks max)
        ca_total = (self.ca1_score + self.ca2_score + self.ca3_score + self.ca4_score)
        # Exam score (60 marks max)
        # Total marks obtained = CA total + Exam score
        self.marks_obtained = ca_total + self.exam_score
        self.total_marks = 100  # Always 100 (40 CA + 60 Exam)

        # Calculate grade based on percentage
        percentage = self.percentage
        if percentage >= 90:
            self.grade = 'A+'
        elif percentage >= 80:
            self.grade = 'A'
        elif percentage >= 70:
            self.grade = 'B+'
        elif percentage >= 60:
            self.grade = 'B'
        elif percentage >= 50:
            self.grade = 'C+'
        elif percentage >= 40:
            self.grade = 'C'
        elif percentage >= 30:
            self.grade = 'D'
        else:
            self.grade = 'F'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.term} {self.academic_year})"

    @property
    def ca_total(self):
        """Calculate total CA marks"""
        return self.ca1_score + self.ca2_score + self.ca3_score + self.ca4_score

    @property
    def percentage(self):
        """Calculate percentage"""
        if self.total_marks > 0:
            return (self.marks_obtained / self.total_marks) * 100
        return 0


class FeeStructure(models.Model):
    """Fee structure for different classes"""

    class FeeType(models.TextChoices):
        TUITION = 'tuition', 'Tuition Fee'
        EXAMINATION = 'examination', 'Examination Fee'
        TRANSPORT = 'transport', 'Transport Fee'
        HOSTEL = 'hostel', 'Hostel Fee'
        OTHER = 'other', 'Other'

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    grade = models.IntegerField()  # Applicable grade
    fee_type = models.CharField(max_length=20, choices=FeeType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ['academic_year', 'grade', 'fee_type']

    def __str__(self):
        return f"Grade {self.grade} - {self.fee_type} ({self.academic_year})"


class FeePayment(models.Model):
    """Fee payment records"""

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        PARTIAL = 'partial', 'Partial'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_payments')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, null=True, blank=True)

    class Term(models.TextChoices):
        FIRST = 'first', 'First Term'
        SECOND = 'second', 'Second Term'
        THIRD = 'third', 'Third Term'

    term = models.CharField(max_length=10, choices=Term.choices, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_method = models.CharField(max_length=50, blank=True)  # e.g., "Online", "Cash", "Bank Transfer"
    transaction_id = models.CharField(max_length=100, blank=True, unique=True)
    remarks = models.TextField(blank=True)

    class Meta:
        unique_together = ['student', 'academic_year', 'term']  # Prevent duplicate payments for same term

    def __str__(self):
        return f"{self.student} - {self.fee_structure.fee_type} ({self.status})"


class Announcement(models.Model):
    """School announcements"""

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Target audience
    for_students = models.BooleanField(default=True)
    for_parents = models.BooleanField(default=True)
    for_staff = models.BooleanField(default=True)
    for_management = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Attendance(models.Model):
    """Student attendance records"""

    class AttendanceStatus(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LATE = 'late', 'Late'
        EXCUSED = 'excused', 'Excused'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    class_period = models.ForeignKey(Class, on_delete=models.CASCADE)
    marked_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    remarks = models.TextField(blank=True)

    class Meta:
        unique_together = ['student', 'date', 'class_period']

    def __str__(self):
        return f"{self.student} - {self.date} ({self.status})"
