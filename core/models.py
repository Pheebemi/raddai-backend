import secrets

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone


def get_today():
    """Return today's date"""
    return timezone.now().date()


class ClassLevel(models.IntegerChoices):
    """
    Every level the school admits into, Pre-Nursery through SS 3.

    The integers match the `grade` values used by Class/FeeStructure so an
    application can be lined up against a real class later. Levels only —
    an applicant picks "JSS 1", never "JSS 1A"; sections are assigned on
    enrolment. Keep in sync with CLASS_LEVELS in the frontend.
    """
    PRE_NURSERY = -3, 'Pre-Nursery'
    NURSERY_1 = -2, 'Nursery 1'
    NURSERY_2 = -1, 'Nursery 2'
    PRIMARY_1 = 1, 'Primary 1'
    PRIMARY_2 = 2, 'Primary 2'
    PRIMARY_3 = 3, 'Primary 3'
    PRIMARY_4 = 4, 'Primary 4'
    PRIMARY_5 = 5, 'Primary 5'
    PRIMARY_6 = 6, 'Primary 6'
    JSS_1 = 7, 'JSS 1'
    JSS_2 = 8, 'JSS 2'
    JSS_3 = 9, 'JSS 3'
    SS_1 = 10, 'SS 1'
    SS_2 = 11, 'SS 2'
    SS_3 = 12, 'SS 3'


class StudentType(models.TextChoices):
    """
    New intake vs continuing. Drives which FeeStructure row applies —
    a returning student without a specific returning fee row falls back
    to the new-student rate for the same grade/gender/department.
    """
    NEW = 'new', 'New'
    RETURNING = 'returning', 'Returning'


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
    results_visible = models.BooleanField(default=False)
    first_term_visible = models.BooleanField(default=False)
    second_term_visible = models.BooleanField(default=False)
    third_term_visible = models.BooleanField(default=False)

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
    code = models.CharField(max_length=20, unique=True, blank=True, null=True, default=None)
    description = models.TextField(blank=True)
    grades = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class Student(models.Model):
    """Student profile model"""
    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    class Department(models.TextChoices):
        SCIENCE = 'science', 'Science'
        ARTS = 'arts', 'Arts'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    admission_date = models.DateField(default=get_today)
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='students')
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default='')
    department = models.CharField(max_length=10, choices=Department.choices, blank=True, default='')
    student_type = models.CharField(
        max_length=10, choices=StudentType.choices, default=StudentType.NEW
    )
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

    # CA Scores (Continuous Assessment) - 3 tests, each worth 10 marks = 30 total
    ca1_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="CA Test 1 (max 10 marks)")
    ca2_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="CA Test 2 (max 10 marks)")
    ca3_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="CA Test 3 (max 10 marks)")
    ca4_score = models.DecimalField(max_digits=4, decimal_places=2, default=0, help_text="Unused (kept for legacy)")

    # Final Exam Score - worth 70 marks
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Final Exam (max 70 marks)")

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
        # CA scores total (30 marks max — 3 tests × 10)
        ca_total = (self.ca1_score + self.ca2_score + self.ca3_score)
        # Exam score (70 marks max)
        self.marks_obtained = ca_total + self.exam_score
        self.total_marks = 100  # Always 100 (30 CA + 70 Exam)

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
        return self.ca1_score + self.ca2_score + self.ca3_score

    @property
    def percentage(self):
        """Calculate percentage"""
        if self.total_marks > 0:
            return (self.marks_obtained / self.total_marks) * 100
        return 0


class FeeStructure(models.Model):
    """Fee structure for different classes"""

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    class Department(models.TextChoices):
        SCIENCE = 'science', 'Science'
        ARTS = 'arts', 'Arts'

    class FeeType(models.TextChoices):
        TUITION = 'tuition', 'Tuition Fee'
        EXAMINATION = 'examination', 'Examination Fee'
        TRANSPORT = 'transport', 'Transport Fee'
        HOSTEL = 'hostel', 'Hostel Fee'
        OTHER = 'other', 'Other'

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    grade = models.IntegerField()  # Applicable grade
    section = models.CharField(
        max_length=10, blank=True, default='',
        help_text="Leave blank to apply to every section of this grade (A, B, C…); "
                   "set to override just one section, e.g. 'A'.",
    )
    fee_type = models.CharField(max_length=20, choices=FeeType.choices)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default='')
    department = models.CharField(max_length=10, choices=Department.choices, blank=True, default='')
    student_type = models.CharField(
        max_length=10, choices=StudentType.choices, default=StudentType.NEW
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [
            'academic_year', 'grade', 'section', 'fee_type', 'gender', 'department', 'student_type'
        ]

    def __str__(self):
        section_label = f" {self.section}" if self.section else ""
        return f"Grade {self.grade}{section_label} - {self.fee_type} - {self.student_type} ({self.academic_year})"


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


class StaffSalary(models.Model):
    """Salary record for staff per academic year and month"""

    class Month(models.IntegerChoices):
        JANUARY = 1, 'January'
        FEBRUARY = 2, 'February'
        MARCH = 3, 'March'
        APRIL = 4, 'April'
        MAY = 5, 'May'
        JUNE = 6, 'June'
        JULY = 7, 'July'
        AUGUST = 8, 'August'
        SEPTEMBER = 9, 'September'
        OCTOBER = 10, 'October'
        NOVEMBER = 11, 'November'
        DECEMBER = 12, 'December'

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='salaries')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='staff_salaries')
    month = models.PositiveSmallIntegerField(choices=Month.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_date = models.DateField(default=get_today)
    voucher_number = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['staff', 'academic_year', 'month']
        ordering = ['-paid_date', 'staff__user__last_name']

    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.get_month_display()} {self.academic_year}: {self.amount}"


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


class AdmissionSetting(models.Model):
    """Admission window for one academic year — management opens and closes it."""
    academic_year = models.OneToOneField(
        AcademicYear, on_delete=models.CASCADE, related_name='admission_setting'
    )
    is_open = models.BooleanField(default=False)
    closes_on = models.DateField(null=True, blank=True)
    instructions = models.TextField(
        blank=True, help_text="Shown to applicants on the public admissions page"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Admissions {self.academic_year.name} ({'open' if self.is_open else 'closed'})"

    @property
    def accepting_applications(self):
        """Open, and not past the closing date if one is set."""
        if not self.is_open:
            return False
        if self.closes_on and get_today() > self.closes_on:
            return False
        return True


class AdmissionFee(models.Model):
    """Application fee for one level. Levels without a row cannot be applied to."""
    setting = models.ForeignKey(AdmissionSetting, on_delete=models.CASCADE, related_name='fees')
    level = models.IntegerField(choices=ClassLevel.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ['setting', 'level']
        ordering = ['level']

    def __str__(self):
        return f"{self.get_level_display()} - {self.amount}"


def generate_application_reference():
    """
    Unguessable public reference, e.g. LAZ-2026-K7M3XQ.

    Ambiguous characters (O/0, I/1, S/5) are left out so it survives being
    read off a printed form over the phone. Hyphens rather than slashes so it
    drops straight into a URL without encoding.
    """
    alphabet = 'ABCDEFGHJKLMNPQRTUVWXYZ23456789'
    year = get_today().year
    while True:
        suffix = ''.join(secrets.choice(alphabet) for _ in range(6))
        reference = f'LAZ-{year}-{suffix}'
        if not Application.objects.filter(reference=reference).exists():
            return reference


class Application(models.Model):
    """
    An admission application. Deliberately has no User attached — an applicant
    never gets an account. If the child actually turns up, management creates
    the Student the normal way; applications that go nowhere stay inert rows.
    """

    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'Awaiting Payment'
        PAID = 'paid', 'Paid — Form Incomplete'
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        ADMITTED = 'admitted', 'Admitted'
        WAITLISTED = 'waitlisted', 'Waitlisted'
        REJECTED = 'rejected', 'Not Offered'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    reference = models.CharField(max_length=30, unique=True, editable=False)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='applications'
    )
    level = models.IntegerField(choices=ClassLevel.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)

    # --- Step 1: captured before payment, and all that lookup needs ---
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=15)

    # --- Payment ---
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    tx_ref = models.CharField(max_length=100, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # --- Step 2: the full form, filled after payment ---
    middle_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default='Nigerian')
    state_of_origin = models.CharField(max_length=100, blank=True)
    lga = models.CharField(max_length=100, blank=True)
    religion = models.CharField(max_length=50, blank=True)
    home_address = models.TextField(blank=True)
    blood_group = models.CharField(max_length=10, blank=True)
    genotype = models.CharField(max_length=10, blank=True)
    medical_info = models.TextField(blank=True)

    previous_school = models.CharField(max_length=200, blank=True)
    previous_class = models.CharField(max_length=100, blank=True)
    reason_for_leaving = models.TextField(blank=True)

    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_relationship = models.CharField(max_length=50, blank=True)
    guardian_phone = models.CharField(max_length=15, blank=True)
    guardian_email = models.EmailField(blank=True)
    guardian_occupation = models.CharField(max_length=200, blank=True)
    guardian_address = models.TextField(blank=True)
    father_phone = models.CharField(max_length=15, blank=True)
    mother_phone = models.CharField(max_length=15, blank=True)

    # --- Undertaking, required before submission — mirrors the signed paper form ---
    agrees_to_school_authority = models.BooleanField(
        default=False,
        help_text=(
            "Parent/guardian agrees to raise concerns with the school authority "
            "rather than confronting staff directly or involving outside parties."
        ),
    )
    confirms_rules_read = models.BooleanField(
        default=False,
        help_text="Parent/guardian confirms having read and understood the school's rules.",
    )

    passport_photo = models.ImageField(upload_to='admissions/photos/', blank=True, null=True)

    # --- Timestamps / decision ---
    created_at = models.DateTimeField(auto_now_add=True)
    last_saved_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admission_decisions'
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contact_phone', 'date_of_birth']),
            models.Index(fields=['contact_email', 'date_of_birth']),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_application_reference()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.full_name} ({self.get_level_display()})"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)

    @property
    def is_paid(self):
        return self.paid_at is not None

    # Fields an applicant must fill before the form counts as complete.
    REQUIRED_FORM_FIELDS = [
        'gender', 'state_of_origin', 'lga', 'home_address',
        'guardian_name', 'guardian_relationship', 'guardian_phone', 'guardian_address',
        'agrees_to_school_authority', 'confirms_rules_read',
    ]

    def missing_fields(self):
        """Which required fields are still blank — drives the 'form not completed' message."""
        return [f for f in self.REQUIRED_FORM_FIELDS if not getattr(self, f)]
