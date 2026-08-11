from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Sum, Count
from django.utils import timezone
from .models import (
    User, AcademicYear, Class, Subject, Student, Staff, Parent,
    Result, FeeStructure, FeePayment, StaffSalary, Announcement, Attendance,
    AdmissionSetting, AdmissionFee, Application, ClassLevel
)
from .serializers import (
    UserSerializer, LoginSerializer, AcademicYearSerializer,
    ClassSerializer, SubjectSerializer, StudentSerializer,
    StaffSerializer, ParentSerializer, ResultSerializer,
    FeeStructureSerializer, FeePaymentSerializer, StaffSalarySerializer,
    AnnouncementSerializer, AttendanceSerializer,
    AdmissionSettingSerializer, AdmissionFeeSerializer,
    ApplicationSerializer, ApplicationListSerializer,
    ApplicationStartSerializer, ApplicationFormSerializer
)


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin' or request.user.role == 'management':
            return True

        if request.user.role == 'student' and hasattr(obj, 'user'):
            return obj.user == request.user

        if request.user.role == 'staff':
            if hasattr(obj, 'user') and obj.user == request.user:
                return True
            if hasattr(obj, 'student'):
                try:
                    staff_profile = request.user.staff_profile
                    return (obj.student.current_class and
                           obj.student.current_class.class_teacher == staff_profile)
                except Exception:
                    return False

        if request.user.role == 'parent':
            try:
                parent_profile = request.user.parent_profile
                if hasattr(obj, 'student') and obj.student in parent_profile.children.all():
                    return True
                if hasattr(obj, 'user') and obj.user == request.user:
                    return True
            except Exception:
                return False

        return False


class IsStaffOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['staff', 'admin', 'management']


class IsManagementOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['management', 'admin']


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return User.objects.all()
        elif user.role == 'staff':
            try:
                staff_profile = user.staff_profile
                student_ids = []
                try:
                    class_obj = staff_profile.class_teacher
                    student_ids.extend(class_obj.students.values_list('user_id', flat=True))
                except Exception:
                    pass
                return User.objects.filter(Q(id=user.id) | Q(id__in=student_ids))
            except Exception:
                return User.objects.filter(id=user.id)
        elif user.role == 'parent':
            try:
                parent_profile = user.parent_profile
                children_ids = parent_profile.children.values_list('user_id', flat=True)
                return User.objects.filter(Q(id=user.id) | Q(id__in=children_ids))
            except Exception:
                return User.objects.filter(id=user.id)
        else:
            return User.objects.filter(id=user.id)

    @action(detail=False, methods=['get'])
    def profile(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='change_password')
    def change_password(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response({'error': 'Both current and new password are required'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            return Response({'error': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password changed successfully'})

    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AcademicYearViewSet(viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsManagementOrAdmin()]

    def perform_update(self, serializer):
        instance = serializer.save()
        # If setting this year as active, deactivate all others
        if instance.is_active:
            AcademicYear.objects.exclude(pk=instance.pk).update(is_active=False)


class ClassViewSet(viewsets.ModelViewSet):
    queryset = Class.objects.all()
    serializer_class = ClassSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsManagementOrAdmin()]


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsManagementOrAdmin()]

    def get_queryset(self):
        qs = Subject.objects.all()
        grade = self.request.query_params.get('grade')
        if grade:
            try:
                grade_int = int(grade)
                # Return subjects assigned to this grade OR subjects with no grade restriction
                qs = qs.filter(grades__contains=grade_int) | qs.filter(grades=[])
            except ValueError:
                pass
        return qs




class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return Student.objects.all()
        elif user.role == 'staff':
            try:
                staff_profile = user.staff_profile
                return Student.objects.filter(current_class__class_teacher=staff_profile)
            except Exception:
                return Student.objects.none()
        elif user.role == 'parent':
            try:
                parent_profile = user.parent_profile
                return parent_profile.children.all()
            except Exception:
                return Student.objects.none()
        else:
            try:
                return Student.objects.filter(user=user)
            except Exception:
                return Student.objects.none()


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'management']:
            return Staff.objects.all()
        else:
            try:
                return Staff.objects.filter(user=user)
            except Exception:
                return Staff.objects.none()

    @action(detail=True, methods=['post'], url_path='assign-class')
    def assign_class(self, request, pk=None):
        staff = self.get_object()
        class_id = request.data.get('class_id')

        if not class_id:
            Class.objects.filter(class_teacher=staff).update(class_teacher=None)
            serializer = self.get_serializer(staff)
            return Response(serializer.data)

        try:
            target_class = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            return Response({'detail': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)

        Class.objects.filter(class_teacher=staff).exclude(pk=target_class.pk).update(class_teacher=None)
        target_class.class_teacher = staff
        target_class.save()

        serializer = self.get_serializer(staff)
        return Response(serializer.data)


class ParentViewSet(viewsets.ModelViewSet):
    queryset = Parent.objects.all()
    serializer_class = ParentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'management']:
            return Parent.objects.all()
        else:
            try:
                return Parent.objects.filter(user=user)
            except Exception:
                return Parent.objects.none()

    def perform_create(self, serializer):
        # Auto-generate parent_id if not provided
        if not serializer.validated_data.get('parent_id'):
            last = Parent.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            parent_id = f'PAR{next_num:04d}'
            serializer.save(parent_id=parent_id)
        else:
            serializer.save()


class ResultViewSet(viewsets.ModelViewSet):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def perform_create(self, serializer):
        if self.request.user.role == 'staff':
            serializer.save(uploaded_by=self.request.user.staff_profile)
        else:
            serializer.save()

    def get_queryset(self):
        user = self.request.user

        if user.role == 'admin' or user.role == 'management':
            return Result.objects.all()
        elif user.role == 'staff':
            try:
                staff_profile = user.staff_profile
                return Result.objects.filter(
                    Q(uploaded_by=staff_profile) |
                    Q(student__current_class__class_teacher=staff_profile)
                )
            except Exception:
                return Result.objects.none()
        elif user.role == 'student':
            try:
                student_profile = user.student_profile
                return Result.objects.filter(student=student_profile)
            except Exception:
                return Result.objects.none()
        elif user.role == 'parent':
            try:
                parent_profile = user.parent_profile
                return Result.objects.filter(student__in=parent_profile.children.all())
            except Exception:
                return Result.objects.none()
        return Result.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        elif self.action in ['create', 'update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsStaffOrAdmin()]
        elif self.action == 'export_results':
            return [permissions.IsAuthenticated(), IsStaffOrAdmin()]
        return [permissions.IsAuthenticated(), permissions.IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='export')
    def export_results(self, request):
        user = request.user
        if user.role not in ['staff', 'admin', 'management']:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        queryset = self.get_queryset()

        class_id = request.query_params.get('class_id')
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        if class_id:
            queryset = queryset.filter(student__current_class=class_id)
        if term:
            queryset = queryset.filter(term=term)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        queryset = queryset.order_by(
            'student__user__first_name',
            'student__user__last_name',
            'student__student_id',
            'subject__name',
        )

        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="results_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Student ID', 'Student Name', 'Class', 'Subject', 'Term', 'Academic Year',
            'CA1 Score', 'CA2 Score', 'CA3 Score', 'CA4 Score', 'CA Total',
            'Exam Score', 'Total Marks', 'Percentage', 'Grade', 'Remarks', 'Uploaded By'
        ])

        for result in queryset.select_related('student__user', 'subject', 'academic_year', 'uploaded_by__user'):
            writer.writerow([
                result.student.student_id,
                result.student.user.get_full_name(),
                result.student.current_class.name if result.student.current_class else '',
                result.subject.name,
                result.term,
                result.academic_year.name,
                result.ca1_score,
                result.ca2_score,
                result.ca3_score,
                result.ca4_score,
                result.ca_total,
                result.exam_score,
                result.marks_obtained,
                result.percentage,
                result.grade,
                result.remarks or '',
                result.uploaded_by.user.get_full_name() if result.uploaded_by else ''
            ])

        return response


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsManagementOrAdmin()]


class FeePaymentViewSet(viewsets.ModelViewSet):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return FeePayment.objects.all()
        elif user.role == 'student':
            try:
                student_profile = user.student_profile
                return FeePayment.objects.filter(student=student_profile)
            except Exception:
                return FeePayment.objects.none()
        elif user.role == 'parent':
            try:
                parent_profile = user.parent_profile
                return FeePayment.objects.filter(student__in=parent_profile.children.all())
            except Exception:
                return FeePayment.objects.none()
        return FeePayment.objects.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = data.get('student')
        academic_year = data.get('academic_year')
        term = data.get('term')
        fee_structure = data.get('fee_structure')
        incoming_amount = data.get('amount_paid') or 0

        full_amount = None
        resolved_fee_structure = fee_structure

        try:
            if student and hasattr(student, 'current_class') and student.current_class and academic_year:
                grade = student.current_class.grade
                fs_qs = FeeStructure.objects.filter(
                    academic_year=academic_year,
                    grade=grade,
                    fee_type=FeeStructure.FeeType.TUITION,
                )
                resolved_fee_structure = fs_qs.first() or fee_structure
                if resolved_fee_structure and getattr(resolved_fee_structure, 'amount', None) is not None:
                    full_amount = resolved_fee_structure.amount
        except Exception:
            pass

        if full_amount is None:
            if resolved_fee_structure and hasattr(resolved_fee_structure, 'amount') and resolved_fee_structure.amount is not None:
                full_amount = resolved_fee_structure.amount
            else:
                full_amount = data.get('total_amount') or incoming_amount

        fee_structure = resolved_fee_structure

        existing = FeePayment.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).first()

        if existing:
            new_amount_paid = (existing.amount_paid or 0) + incoming_amount
            if full_amount:
                new_amount_paid = min(new_amount_paid, full_amount)

            existing.amount_paid = new_amount_paid
            if full_amount:
                existing.total_amount = full_amount

            existing.payment_method = data.get('payment_method') or existing.payment_method
            existing.transaction_id = data.get('transaction_id') or existing.transaction_id
            existing.remarks = data.get('remarks') or existing.remarks
            existing.due_date = data.get('due_date') or existing.due_date

            if full_amount and new_amount_paid >= full_amount:
                existing.status = FeePayment.PaymentStatus.PAID
            elif new_amount_paid > 0:
                existing.status = FeePayment.PaymentStatus.PARTIAL
            else:
                existing.status = FeePayment.PaymentStatus.PENDING

            existing.save()
            output_serializer = self.get_serializer(existing)
            return Response(output_serializer.data, status=status.HTTP_200_OK)

        total_amount = full_amount or incoming_amount
        amount_paid = min(incoming_amount, total_amount)

        if total_amount and amount_paid >= total_amount:
            status_value = FeePayment.PaymentStatus.PAID
        elif amount_paid > 0:
            status_value = FeePayment.PaymentStatus.PARTIAL
        else:
            status_value = FeePayment.PaymentStatus.PENDING

        fee_payment = FeePayment.objects.create(
            student=student,
            fee_structure=fee_structure,
            academic_year=academic_year,
            term=term,
            amount_paid=amount_paid,
            total_amount=total_amount,
            due_date=data.get('due_date'),
            status=status_value,
            payment_method=data.get('payment_method', ''),
            transaction_id=data.get('transaction_id', ''),
            remarks=data.get('remarks', ''),
        )

        output_serializer = self.get_serializer(fee_payment)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class StaffSalaryViewSet(viewsets.ModelViewSet):
    queryset = StaffSalary.objects.select_related('staff__user', 'academic_year').all()
    serializer_class = StaffSalarySerializer
    permission_classes = [IsManagementOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        academic_year = self.request.query_params.get('academic_year')
        month = self.request.query_params.get('month')
        staff_id = self.request.query_params.get('staff')

        if academic_year:
            qs = qs.filter(academic_year_id=academic_year)
        if month:
            qs = qs.filter(month=month)
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        return qs


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.filter(is_active=True)
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Announcement.objects.filter(is_active=True)

        if user.role == 'student':
            queryset = queryset.filter(for_students=True)
        elif user.role == 'staff':
            queryset = queryset.filter(for_staff=True)
        elif user.role == 'parent':
            queryset = queryset.filter(for_parents=True)
        elif user.role == 'management':
            queryset = queryset.filter(for_management=True)

        return queryset.order_by('-created_at')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsManagementOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = None

    def get_queryset(self):
        date = self.request.query_params.get('date')
        user = self.request.user

        if user.role == 'admin' or user.role == 'management':
            qs = Attendance.objects.all()
        elif user.role == 'staff':
            try:
                staff_profile = user.staff_profile
                qs = Attendance.objects.filter(class_period__class_teacher=staff_profile)
            except Exception:
                qs = Attendance.objects.none()
        elif user.role == 'student':
            try:
                student_profile = user.student_profile
                qs = Attendance.objects.filter(student=student_profile)
            except Exception:
                qs = Attendance.objects.none()
        elif user.role == 'parent':
            try:
                parent_profile = user.parent_profile
                qs = Attendance.objects.filter(student__in=parent_profile.children.all())
            except Exception:
                qs = Attendance.objects.none()
        else:
            qs = Attendance.objects.none()

        if date:
            qs = qs.filter(date=date)

        return qs


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_results_visibility(request):
    if request.user.role not in ['management', 'admin']:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    academic_year_id = request.data.get('academic_year_id')
    visible = request.data.get('visible')
    term = request.data.get('term')  # optional: 'first', 'second', 'third'

    if academic_year_id is None or visible is None:
        return Response({'error': 'academic_year_id and visible are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        academic_year = AcademicYear.objects.get(id=academic_year_id)
    except AcademicYear.DoesNotExist:
        return Response({'error': 'Academic year not found'}, status=status.HTTP_404_NOT_FOUND)

    if term == 'first':
        academic_year.first_term_visible = bool(visible)
    elif term == 'second':
        academic_year.second_term_visible = bool(visible)
    elif term == 'third':
        academic_year.third_term_visible = bool(visible)
    else:
        # Toggle all terms together
        academic_year.results_visible = bool(visible)
        academic_year.first_term_visible = bool(visible)
        academic_year.second_term_visible = bool(visible)
        academic_year.third_term_visible = bool(visible)

    academic_year.save()

    return Response({
        'id': academic_year.id,
        'name': academic_year.name,
        'results_visible': academic_year.results_visible,
        'first_term_visible': academic_year.first_term_visible,
        'second_term_visible': academic_year.second_term_visible,
        'third_term_visible': academic_year.third_term_visible,
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def flutterwave_webhook(request):
    """
    Flutterwave calls this endpoint directly when a payment completes.
    Runs server-to-server — independent of the user's browser.
    """
    import requests as http_requests
    from django.conf import settings as django_settings
    import calendar
    from datetime import date

    # Verify the webhook signature
    webhook_hash = getattr(django_settings, 'FLUTTERWAVE_WEBHOOK_HASH', '')
    if webhook_hash:
        received_hash = request.headers.get('verif-hash', '')
        if received_hash != webhook_hash:
            return Response({'error': 'Invalid webhook signature'}, status=status.HTTP_401_UNAUTHORIZED)

    data = request.data
    event = data.get('event', '')

    # Only handle successful charge events
    if event != 'charge.completed':
        return Response({'status': 'ignored'})

    tx_data = data.get('data', {})

    if tx_data.get('status') not in ['successful', 'completed']:
        return Response({'status': 'ignored'})

    if tx_data.get('currency') != 'NGN':
        return Response({'status': 'ignored'})

    transaction_id = tx_data.get('id')
    tx_ref = tx_data.get('tx_ref', '')
    verified_amount = float(tx_data.get('amount', 0))

    if not transaction_id:
        return Response({'error': 'No transaction ID'}, status=status.HTTP_400_BAD_REQUEST)

    # Admission fees arrive here too. Flutterwave allows only one webhook URL
    # per account, and this is the one already registered — so route anything
    # whose tx_ref is an application reference to the admissions handler
    # instead of letting it fall through the school-fee logic below.
    application = Application.objects.filter(reference=tx_ref).first()
    if application:
        if application.paid_at:
            return Response({'status': 'already_recorded'})

        verified = _verify_with_flutterwave(transaction_id)
        if not verified:
            return Response({'status': 'verification_failed'})

        _mark_application_paid(
            application, transaction_id, float(verified.get('amount', 0)), tx_ref
        )
        return Response({'status': 'recorded'})

    # Idempotency — already recorded
    if FeePayment.objects.filter(transaction_id=str(transaction_id)).exists():
        return Response({'status': 'already_recorded'})

    # Verify with Flutterwave API
    secret_key = getattr(django_settings, 'FLUTTERWAVE_SECRET_KEY', '')
    try:
        flw_response = http_requests.get(
            f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
            headers={'Authorization': f'Bearer {secret_key}'},
            timeout=30,
        )
        flw_data = flw_response.json()
        if flw_data.get('status') != 'success' or flw_data.get('data', {}).get('status') != 'successful':
            return Response({'status': 'verification_failed'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Extract student info from tx_ref (format: school_fee_{user_id}_{timestamp})
    # We need to find the student from the meta or tx_ref
    meta = tx_data.get('meta', {})
    student_id = meta.get('student_id') if meta else None

    # Try to parse student_id from tx_ref: school_fee_{user_id}_{timestamp}
    if not student_id and tx_ref.startswith('school_fee_'):
        try:
            user_id = int(tx_ref.split('_')[2])
            student = Student.objects.filter(user_id=user_id).first()
            if student:
                student_id = student.id
        except (IndexError, ValueError):
            pass

    if not student_id:
        return Response({'error': 'Could not identify student'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get active academic year
    academic_year = AcademicYear.objects.filter(is_active=True).first()
    if not academic_year:
        return Response({'error': 'No active academic year'}, status=status.HTTP_400_BAD_REQUEST)

    # Find fee structure
    fee_structure = None
    if student.current_class:
        fee_structure = FeeStructure.objects.filter(
            grade=student.current_class.grade,
            fee_type='tuition',
            academic_year=academic_year,
        ).first()

    total_amount = float(fee_structure.amount) if fee_structure else verified_amount

    # Term from meta or default to first available unpaid term
    term = meta.get('term') if meta else None
    if not term:
        for t in ['first', 'second', 'third']:
            if not FeePayment.objects.filter(student=student, academic_year=academic_year, term=t, status='paid').exists():
                term = t
                break
    if not term:
        term = 'first'

    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    due_date = date(today.year, today.month, last_day)

    existing = FeePayment.objects.filter(student=student, academic_year=academic_year, term=term).first()
    if existing:
        new_paid = min(float(existing.amount_paid or 0) + verified_amount, total_amount)
        existing.amount_paid = new_paid
        existing.total_amount = total_amount
        existing.status = FeePayment.PaymentStatus.PAID if new_paid >= total_amount else FeePayment.PaymentStatus.PARTIAL
        existing.transaction_id = str(transaction_id)
        existing.payment_method = 'flutterwave'
        existing.save()
    else:
        payment_status = FeePayment.PaymentStatus.PAID if verified_amount >= total_amount else FeePayment.PaymentStatus.PARTIAL
        FeePayment.objects.create(
            student=student,
            fee_structure=fee_structure,
            academic_year=academic_year,
            term=term,
            amount_paid=verified_amount,
            total_amount=total_amount,
            status=payment_status,
            payment_method='flutterwave',
            transaction_id=str(transaction_id),
            due_date=due_date,
        )

    return Response({'status': 'recorded'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verify_flutterwave_payment(request):
    import requests as http_requests
    from django.conf import settings as django_settings
    import calendar
    from datetime import date

    transaction_id = request.data.get('transaction_id')
    student_id = request.data.get('student_id')
    term = request.data.get('term')
    academic_year_id = request.data.get('academic_year')
    expected_amount = request.data.get('expected_amount')
    remarks = request.data.get('remarks', '')

    if not transaction_id:
        return Response({'error': 'transaction_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    # Idempotency — already recorded for this transaction
    existing_payment = FeePayment.objects.filter(transaction_id=str(transaction_id)).first()
    if existing_payment:
        from .serializers import FeePaymentSerializer
        return Response(FeePaymentSerializer(existing_payment).data, status=status.HTTP_200_OK)

    # Verify with Flutterwave
    secret_key = getattr(django_settings, 'FLUTTERWAVE_SECRET_KEY', '')
    if not secret_key:
        return Response({'error': 'Payment verification not configured on server'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        flw_response = http_requests.get(
            f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
            headers={'Authorization': f'Bearer {secret_key}'},
            timeout=30,
        )
    except Exception as e:
        return Response({'error': f'Verification request failed: {str(e)}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if flw_response.status_code != 200:
        return Response({'error': 'Flutterwave verification failed'}, status=status.HTTP_400_BAD_REQUEST)

    flw_data = flw_response.json()

    if flw_data.get('status') != 'success':
        return Response({'error': 'Transaction could not be verified'}, status=status.HTTP_400_BAD_REQUEST)

    tx_data = flw_data.get('data', {})

    if tx_data.get('status') not in ['successful', 'completed']:
        return Response({'error': f'Transaction status: {tx_data.get("status")}'}, status=status.HTTP_400_BAD_REQUEST)

    if tx_data.get('currency') != 'NGN':
        return Response({'error': 'Invalid currency'}, status=status.HTTP_400_BAD_REQUEST)

    verified_amount = float(tx_data.get('amount', 0))

    if expected_amount and abs(verified_amount - float(expected_amount)) > 1:
        return Response({
            'error': f'Amount mismatch: expected ₦{expected_amount}, verified ₦{verified_amount}'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get student
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get academic year
    try:
        academic_year_obj = AcademicYear.objects.get(id=academic_year_id)
    except AcademicYear.DoesNotExist:
        return Response({'error': 'Academic year not found'}, status=status.HTTP_404_NOT_FOUND)

    # Find fee structure
    fee_structure = None
    if student.current_class:
        fee_structure = FeeStructure.objects.filter(
            grade=student.current_class.grade,
            fee_type='tuition',
            academic_year=academic_year_obj,
        ).first()

    total_amount = float(fee_structure.amount) if fee_structure else verified_amount

    # Due date = end of current month
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    due_date = date(today.year, today.month, last_day)

    # Partial payment — add to existing record
    existing = FeePayment.objects.filter(
        student=student,
        academic_year=academic_year_obj,
        term=term,
    ).first()

    if existing:
        new_amount_paid = float(existing.amount_paid or 0) + verified_amount
        new_amount_paid = min(new_amount_paid, total_amount)
        existing.amount_paid = new_amount_paid
        existing.total_amount = total_amount
        existing.status = FeePayment.PaymentStatus.PAID if new_amount_paid >= total_amount else FeePayment.PaymentStatus.PARTIAL
        existing.transaction_id = str(transaction_id)
        existing.payment_method = 'flutterwave'
        existing.remarks = remarks or existing.remarks
        existing.save()
        from .serializers import FeePaymentSerializer
        return Response(FeePaymentSerializer(existing).data, status=status.HTTP_200_OK)

    # New payment
    payment_status = FeePayment.PaymentStatus.PAID if verified_amount >= total_amount else FeePayment.PaymentStatus.PARTIAL

    payment = FeePayment.objects.create(
        student=student,
        fee_structure=fee_structure,
        academic_year=academic_year_obj,
        term=term,
        amount_paid=verified_amount,
        total_amount=total_amount,
        status=payment_status,
        payment_method='flutterwave',
        transaction_id=str(transaction_id),
        remarks=remarks,
        due_date=due_date,
    )

    from .serializers import FeePaymentSerializer
    return Response(FeePaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user_data,
            'role': user.role
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_class_rankings(request):
    class_id = request.GET.get('class_id')
    term = request.GET.get('term')
    academic_year = request.GET.get('academic_year')

    if not all([class_id, term, academic_year]):
        return Response(
            {'error': 'class_id, term, and academic_year are required parameters'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        try:
            class_id_int = int(class_id)
        except ValueError:
            return Response(
                {'error': 'class_id must be a valid integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        academic_year_obj = None
        try:
            academic_year_obj = AcademicYear.objects.get(id=int(academic_year))
        except (ValueError, AcademicYear.DoesNotExist):
            try:
                academic_year_obj = AcademicYear.objects.get(name=academic_year)
            except AcademicYear.DoesNotExist:
                return Response(
                    {'error': 'academic_year must be a valid ID or name'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if term not in ['first', 'second', 'third', 'final']:
            return Response(
                {'error': 'term must be one of: first, second, third, final'},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = Class.objects.filter(id=class_id_int)
        if not qs.exists():
            return Response(
                {'error': f'Class with id {class_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        user = request.user
        if user.role == 'staff':
            try:
                staff_profile = user.staff_profile
            except Exception:
                return Response(
                    {'error': 'Staff profile not found for current user'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if not qs.filter(class_teacher=staff_profile).exists():
                return Response(
                    {'error': 'You are not the class teacher for this class'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Use recorded_class when set; fall back to current_class only when recorded_class is NULL
        results = Result.objects.filter(
            term=term,
            academic_year=academic_year_obj,
        ).filter(
            Q(recorded_class_id=class_id_int) |
            Q(recorded_class__isnull=True, student__current_class_id=class_id_int)
        ).select_related('student', 'subject', 'academic_year')

        if not results:
            return Response({
                'rankings': [],
                'message': 'No results found for the specified criteria',
                'total_students': 0,
                'class_info': {
                    'class_id': class_id,
                    'term': term,
                    'academic_year': academic_year_obj.name
                }
            })

        student_averages = {}

        for result in results:
            student_id = result.student.id
            student_name = result.student.user.get_full_name()

            if student_id not in student_averages:
                student_averages[student_id] = {
                    'student_id': student_id,
                    'student_name': student_name,
                    'total_weighted_score': 0,
                    'total_max_score': 0,
                    'subject_count': 0,
                    'subjects': []
                }

            subject_data = {
                'subject_name': result.subject.name,
                'ca_total': result.ca_total,
                'exam_score': result.exam_score,
                'marks_obtained': result.marks_obtained,
                'total_marks': result.total_marks,
                'percentage': result.percentage,
                'grade': result.grade
            }

            student_averages[student_id]['subjects'].append(subject_data)
            student_averages[student_id]['total_weighted_score'] += result.marks_obtained
            student_averages[student_id]['total_max_score'] += result.total_marks
            student_averages[student_id]['subject_count'] += 1

        rankings_list = []
        for student_data in student_averages.values():
            if student_data['total_max_score'] > 0:
                average_percentage = (student_data['total_weighted_score'] / student_data['total_max_score']) * 100
                student_data['average_percentage'] = round(average_percentage, 2)
            else:
                student_data['average_percentage'] = 0.0
            rankings_list.append(student_data)

        rankings_list.sort(key=lambda x: x['average_percentage'], reverse=True)

        current_position = 1
        previous_percentage = None

        for i, student in enumerate(rankings_list):
            if previous_percentage is not None and student['average_percentage'] < previous_percentage:
                current_position = i + 1
            student['position'] = current_position
            previous_percentage = student['average_percentage']

        return Response({
            'rankings': rankings_list,
            'total_students': len(rankings_list),
            'class_info': {
                'class_id': class_id,
                'term': term,
                'academic_year': academic_year_obj.name
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(
            {'error': f'Failed to calculate rankings: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsManagementOrAdmin])
def promote_students(request):
    """
    GET  — preview which class each student would move to.
    POST — execute the promotion.

    GET params : from_academic_year (id), to_academic_year (id)
    POST body  : from_academic_year, to_academic_year,
                 repeated_student_ids (list), graduated_student_ids (list)
    """
    from_year_id = request.data.get('from_academic_year') if request.method == 'POST' else request.GET.get('from_academic_year')
    to_year_id   = request.data.get('to_academic_year')   if request.method == 'POST' else request.GET.get('to_academic_year')

    if not from_year_id or not to_year_id:
        return Response(
            {'error': 'from_academic_year and to_academic_year are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        from_year = AcademicYear.objects.get(id=from_year_id)
        to_year   = AcademicYear.objects.get(id=to_year_id)
    except AcademicYear.DoesNotExist:
        return Response({'error': 'Academic year not found'}, status=status.HTTP_404_NOT_FOUND)

    students = Student.objects.filter(
        current_class__academic_year=from_year
    ).select_related('user', 'current_class')

    if request.method == 'GET':
        preview = []
        for student in students:
            current_grade = student.current_class.grade if student.current_class else None
            next_grade    = current_grade + 1 if current_grade is not None else None
            next_class    = None
            if next_grade is not None:
                next_class = Class.objects.filter(academic_year=to_year, grade=next_grade).first()

            preview.append({
                'student_id':     student.id,
                'student_name':   student.user.get_full_name(),
                'student_number': student.student_id,
                'current_class':  student.current_class.name if student.current_class else None,
                'current_grade':  current_grade,
                'next_class':     next_class.name if next_class else None,
                'next_class_id':  next_class.id   if next_class else None,
                'can_promote':    next_class is not None,
            })

        return Response({
            'students':  preview,
            'from_year': from_year.name,
            'to_year':   to_year.name,
            'total':     len(preview),
        })

    # POST — execute
    repeated_ids   = set(request.data.get('repeated_student_ids',  []))
    graduated_ids  = set(request.data.get('graduated_student_ids', []))

    promoted         = 0
    repeated         = 0
    graduated        = 0
    no_class_found   = []

    for student in students:
        current_grade = student.current_class.grade if student.current_class else None

        if student.id in graduated_ids:
            student.current_class = None
            student.save()
            graduated += 1

        elif student.id in repeated_ids:
            same_class = Class.objects.filter(academic_year=to_year, grade=current_grade).first()
            if same_class:
                student.current_class = same_class
                student.save()
                repeated += 1
            else:
                no_class_found.append(
                    f"{student.user.get_full_name()} (Grade {current_grade} repeat — no class in {to_year.name})"
                )

        else:
            next_grade = current_grade + 1 if current_grade is not None else None
            if next_grade is not None:
                next_class = Class.objects.filter(academic_year=to_year, grade=next_grade).first()
                if next_class:
                    student.current_class = next_class
                    student.save()
                    promoted += 1
                else:
                    no_class_found.append(
                        f"{student.user.get_full_name()} (Grade {next_grade} — no class found in {to_year.name})"
                    )
            else:
                no_class_found.append(f"{student.user.get_full_name()} (no current grade)")

    return Response({
        'promoted':       promoted,
        'repeated':       repeated,
        'graduated':      graduated,
        'no_class_found': no_class_found,
        'message':        f'Done: {promoted} promoted, {repeated} repeated, {graduated} graduated.',
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_student_term_fee(request):
    """Returns the tuition fee amount for the student's current class and a given academic year."""
    academic_year_id = request.query_params.get('academic_year')
    student_id = request.query_params.get('student_id')  # for parent paying for a child

    try:
        if student_id:
            student = Student.objects.get(id=student_id)
        elif request.user.role == 'student':
            student = request.user.student_profile
        else:
            return Response({'error': 'student_id required'}, status=status.HTTP_400_BAD_REQUEST)

        if not student.current_class:
            return Response({'fee': None, 'reason': 'no_class'})

        grade = student.current_class.grade

        if academic_year_id:
            academic_year = AcademicYear.objects.filter(id=academic_year_id).first()
        else:
            academic_year = AcademicYear.objects.filter(is_active=True).first()

        if not academic_year:
            return Response({'fee': None, 'reason': 'no_academic_year'})

        fee_structure = FeeStructure.objects.filter(
            academic_year=academic_year,
            grade=grade,
            fee_type=FeeStructure.FeeType.TUITION,
        ).first()

        if not fee_structure:
            return Response({'fee': None, 'reason': 'no_fee_structure'})

        return Response({
            'fee': float(fee_structure.amount),
            'grade': grade,
            'academic_year': academic_year.name,
            'academic_year_id': academic_year.id,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    user = request.user
    stats = {}

    if user.role == 'management':
        # Auto-mark payments from previous (inactive) years as overdue if still pending/partial
        active_year = AcademicYear.objects.filter(is_active=True).first()
        if active_year:
            FeePayment.objects.filter(
                status__in=['pending', 'partial'],
            ).exclude(
                academic_year=active_year
            ).update(status=FeePayment.PaymentStatus.OVERDUE)

        academic_year_id = request.query_params.get('academic_year')
        payment_qs = FeePayment.objects.all()
        if academic_year_id and academic_year_id != 'all':
            payment_qs = payment_qs.filter(academic_year_id=academic_year_id)

        # Total revenue = all paid amounts
        revenue_agg = payment_qs.filter(status='paid').aggregate(total=Sum('amount_paid'))
        total_revenue = float(revenue_agg['total'] or 0)

        # Pending & expected: based on selected year (or active year if "all")
        from django.db.models import Count as DbCount
        calc_year = None
        if academic_year_id and academic_year_id != 'all':
            calc_year = AcademicYear.objects.filter(id=academic_year_id).first()
        else:
            calc_year = active_year  # default to active year for expected calc

        total_expected = 0.0
        if calc_year:
            fee_map = {
                fs.grade: float(fs.amount)
                for fs in FeeStructure.objects.filter(
                    academic_year=calc_year,
                    fee_type=FeeStructure.FeeType.TUITION,
                )
            }

            if calc_year == active_year:
                # Active year: use current_class (accurate for current enrolment)
                students_by_grade = (
                    Student.objects
                    .filter(current_class__academic_year=calc_year, current_class__isnull=False)
                    .values('current_class__grade')
                    .annotate(count=DbCount('id'))
                )
                for row in students_by_grade:
                    grade = row['current_class__grade']
                    fee = fee_map.get(grade, 0)
                    total_expected += fee * 3 * row['count']
            else:
                # Old year: use recorded_class from results (historical enrolment)
                from django.db.models import Count as RCount
                historical = (
                    Result.objects
                    .filter(academic_year=calc_year, recorded_class__isnull=False)
                    .values('student', 'recorded_class__grade')
                    .distinct()
                )
                # Count distinct students per grade
                grade_counts: dict = {}
                for row in historical:
                    grade = row['recorded_class__grade']
                    if grade not in grade_counts:
                        grade_counts[grade] = set()
                    grade_counts[grade].add(row['student'])
                for grade, students_set in grade_counts.items():
                    fee = fee_map.get(grade, 0)
                    total_expected += fee * 3 * len(students_set)

        paid_in_year = float(
            payment_qs.filter(status='paid').aggregate(total=Sum('amount_paid'))['total'] or 0
        )

        outstanding = max(total_expected - paid_in_year, 0)

        # Determine if the selected year is the active year
        is_active_year = (
            calc_year and active_year and calc_year.id == active_year.id
        ) or (not academic_year_id or academic_year_id == 'all')

        if is_active_year:
            # Current year: outstanding = pending (not overdue yet)
            pending_fees = outstanding
            overdue_amount = float(
                payment_qs.filter(status='overdue').aggregate(total=Sum('total_amount'))['total'] or 0
            )
        else:
            # Old year: everything outstanding is overdue (year has ended)
            pending_fees = 0
            overdue_amount = outstanding

        top_performers = []
        recent_high_results = Result.objects.filter(
            grade__in=['A+', 'A', 'A-']
        ).select_related('student__user').order_by('-upload_date')[:3]

        for result in recent_high_results:
            top_performers.append({
                'id': result.student.id,
                'name': result.student.user.get_full_name(),
                'class': result.student.current_class.name if result.student.current_class else 'N/A',
                'grade': result.grade
            })

        recent_results = Result.objects.select_related(
            'student__user', 'uploaded_by__user', 'subject'
        ).order_by('-upload_date')[:5]

        recent_results_data = []
        for result in recent_results:
            recent_results_data.append({
                'id': result.id,
                'student_name': result.student.user.get_full_name(),
                'subject_name': result.subject.name,
                'grade': result.grade,
                'marks_obtained': result.marks_obtained,
                'total_marks': result.total_marks,
                'term': result.term,
                'academic_year': result.academic_year.name,
                'uploaded_by': result.uploaded_by.user.get_full_name() if result.uploaded_by else 'System'
            })

        stats = {
            'total_students': Student.objects.count(),
            'total_staff': Staff.objects.count(),
            'total_parents': Parent.objects.count(),
            'total_classes': Class.objects.count(),
            'total_subjects': Subject.objects.count(),
            'total_revenue': total_revenue,
            'pending_fees': pending_fees,
            'overdue_amount': overdue_amount,
            'total_expected': total_expected,
            'average_attendance': 85,
            'top_performers': top_performers,
            'recent_results': recent_results_data,
            'pending_fee_payments': FeePayment.objects.filter(status='pending').count(),
            'recent_announcements': Announcement.objects.filter(
                is_active=True, for_management=True
            ).order_by('-created_at')[:5].count()
        }

    elif user.role == 'staff':
        try:
            staff_profile = user.staff_profile
            try:
                assigned_class = staff_profile.class_teacher
                assigned_classes_count = 1
                students_count = assigned_class.students.count()
            except Exception:
                assigned_classes_count = 0
                students_count = 0

            stats = {
                'assigned_classes': assigned_classes_count,
                'assigned_subjects': staff_profile.subjects.count(),
                'pending_results': 0,
                'students_count': students_count,
                'recent_announcements': Announcement.objects.filter(
                    is_active=True, for_staff=True
                ).order_by('-created_at')[:5].count()
            }
        except Exception:
            stats = {'error': 'Staff profile not found'}

    elif user.role == 'student':
        try:
            student_profile = user.student_profile
            current_class_name = (
                student_profile.current_class.name if student_profile.current_class else None
            )

            academic_year = (
                AcademicYear.objects.filter(is_active=True).first()
                or AcademicYear.objects.order_by('-start_date').first()
            )

            session_pending_fees = 0

            if academic_year and student_profile.current_class:
                grade = student_profile.current_class.grade
                tuition_qs = FeeStructure.objects.filter(
                    academic_year=academic_year,
                    grade=grade,
                    fee_type=FeeStructure.FeeType.TUITION,
                )
                per_term_fee = tuition_qs.aggregate(total=Sum('amount'))['total'] or 0
                session_total_fee = per_term_fee * 3

                paid_agg = FeePayment.objects.filter(
                    student=student_profile,
                    academic_year=academic_year,
                ).aggregate(total=Sum('amount_paid'))
                total_paid = paid_agg['total'] or 0

                raw_pending = session_total_fee - total_paid
                session_pending_fees = float(max(raw_pending, 0))

            stats = {
                'current_class': current_class_name,
                'total_results': Result.objects.filter(student=student_profile).count(),
                'pending_fees': session_pending_fees,
                'per_term_fee': float(per_term_fee) if academic_year and student_profile.current_class else 0,
                'academic_year_id': academic_year.id if academic_year else None,
                'attendance_percentage': 0,
                'recent_announcements': Announcement.objects.filter(
                    is_active=True, for_students=True
                ).order_by('-created_at')[:5].count(),
            }
        except Exception:
            stats = {'error': 'Student profile not found'}

    elif user.role == 'parent':
        try:
            parent_profile = user.parent_profile
            children_count = parent_profile.children.count()
            total_pending_fees = FeePayment.objects.filter(
                student__in=parent_profile.children.all(), status='pending'
            ).count()

            stats = {
                'children_count': children_count,
                'total_pending_fees': total_pending_fees,
                'recent_announcements': Announcement.objects.filter(
                    is_active=True, for_parents=True
                ).order_by('-created_at')[:5].count()
            }
        except Exception:
            stats = {'error': 'Parent profile not found'}

    return Response(stats)


# ==========================================================================
# Admissions — public endpoints
#
# Applicants have no account, so everything below is AllowAny. Access to a
# specific application is gated on knowing the reference, or on matching
# email/phone together with the child's date of birth.
# ==========================================================================


def _open_admission_setting():
    """The admission window for the active academic year, if there is one."""
    return AdmissionSetting.objects.filter(
        academic_year__is_active=True
    ).select_related('academic_year').first()


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def admission_info(request):
    """Public: is admission open, and what does each level cost?"""
    setting = _open_admission_setting()

    if not setting:
        return Response({'is_open': False, 'instructions': '', 'levels': []})

    fees = {fee.level: fee.amount for fee in setting.fees.all()}
    levels = [
        {'value': value, 'label': label, 'fee': float(fees[value])}
        for value, label in ClassLevel.choices
        if value in fees
    ]

    return Response({
        'is_open': setting.accepting_applications,
        'academic_year': setting.academic_year.name,
        'closes_on': setting.closes_on,
        'instructions': setting.instructions,
        'levels': levels,
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def start_application(request):
    """
    Step 1. Creates the application in `pending_payment` and hands back the
    reference plus the amount to charge. The reference exists before payment
    so a dropped connection mid-checkout is always recoverable.
    """
    serializer = ApplicationStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    setting = data.pop('_setting')
    fee = data.pop('_fee')

    application = Application.objects.create(
        academic_year=setting.academic_year,
        fee_amount=fee.amount,
        **data
    )

    return Response({
        'reference': application.reference,
        'status': application.status,
        'fee_amount': float(application.fee_amount),
        'full_name': application.full_name,
        'level_display': application.get_level_display(),
        'contact_email': application.contact_email,
        'contact_phone': application.contact_phone,
    }, status=status.HTTP_201_CREATED)


def _mark_application_paid(application, transaction_id, amount, tx_ref=''):
    """Shared by the browser-side verify and the webhook. Idempotent."""
    if application.paid_at:
        return application

    application.transaction_id = str(transaction_id)
    application.tx_ref = tx_ref or application.tx_ref
    application.amount_paid = amount
    application.paid_at = timezone.now()
    if application.status == Application.Status.PENDING_PAYMENT:
        application.status = Application.Status.PAID
    application.save()
    return application


def _verify_with_flutterwave(transaction_id):
    """Ask Flutterwave whether a transaction really succeeded. Returns tx data or None."""
    import requests as http_requests
    from django.conf import settings as django_settings

    secret_key = getattr(django_settings, 'FLUTTERWAVE_SECRET_KEY', '')
    if not secret_key:
        return None

    try:
        response = http_requests.get(
            f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
            headers={'Authorization': f'Bearer {secret_key}'},
            timeout=30,
        )
    except Exception:
        return None

    if response.status_code != 200:
        return None

    payload = response.json()
    if payload.get('status') != 'success':
        return None

    tx_data = payload.get('data', {})
    if tx_data.get('status') not in ['successful', 'completed']:
        return None
    if tx_data.get('currency') != 'NGN':
        return None

    return tx_data


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_application_payment(request):
    """
    Called by the applicant's browser after Flutterwave checkout closes.
    The webhook below is the authoritative path — this one just makes the
    happy case feel instant.
    """
    transaction_id = request.data.get('transaction_id')
    reference = request.data.get('reference')

    if not transaction_id or not reference:
        return Response(
            {'error': 'transaction_id and reference are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    application = Application.objects.filter(reference=reference).first()
    if not application:
        return Response({'error': 'Application not found'}, status=status.HTTP_404_NOT_FOUND)

    # Already settled, most likely by the webhook getting there first.
    if application.paid_at:
        return Response(ApplicationSerializer(application, context={'request': request}).data)

    tx_data = _verify_with_flutterwave(transaction_id)
    if not tx_data:
        return Response(
            {'error': 'Transaction could not be verified'},
            status=status.HTTP_400_BAD_REQUEST
        )

    verified_amount = float(tx_data.get('amount', 0))
    if abs(verified_amount - float(application.fee_amount)) > 1:
        return Response(
            {'error': 'Amount paid does not match the application fee'},
            status=status.HTTP_400_BAD_REQUEST
        )

    _mark_application_paid(
        application, transaction_id, verified_amount, tx_data.get('tx_ref', '')
    )
    return Response(ApplicationSerializer(application, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def application_payment_webhook(request):
    """
    Flutterwave calls this server-to-server. This is what makes a lost
    connection survivable: the payment lands here regardless of whether the
    applicant's browser ever made it back to the site.
    """
    from django.conf import settings as django_settings

    webhook_hash = getattr(django_settings, 'FLUTTERWAVE_WEBHOOK_HASH', '')
    if webhook_hash and request.headers.get('verif-hash', '') != webhook_hash:
        return Response({'error': 'Invalid webhook signature'}, status=status.HTTP_401_UNAUTHORIZED)

    data = request.data
    if data.get('event') != 'charge.completed':
        return Response({'status': 'ignored'})

    tx_data = data.get('data', {})
    if tx_data.get('status') not in ['successful', 'completed']:
        return Response({'status': 'ignored'})
    if tx_data.get('currency') != 'NGN':
        return Response({'status': 'ignored'})

    transaction_id = tx_data.get('id')
    tx_ref = tx_data.get('tx_ref', '')

    if not transaction_id:
        return Response({'error': 'No transaction ID'}, status=status.HTTP_400_BAD_REQUEST)

    if Application.objects.filter(transaction_id=str(transaction_id)).exists():
        return Response({'status': 'already_recorded'})

    # The frontend sets tx_ref to the application reference at checkout.
    application = Application.objects.filter(reference=tx_ref).first()
    if not application:
        # Not an admission payment — the fee-payment webhook handles those.
        return Response({'status': 'ignored'})

    verified = _verify_with_flutterwave(transaction_id)
    if not verified:
        return Response({'status': 'verification_failed'})

    _mark_application_paid(
        application, transaction_id, float(verified.get('amount', 0)), tx_ref
    )
    return Response({'status': 'recorded'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def lookup_application(request):
    """
    Return to a form later. Email or phone, plus the child's date of birth —
    the DOB keeps someone who merely knows a phone number from pulling up
    another family's details. Siblings share contacts but differ by DOB.
    """
    identifier = (request.data.get('identifier') or '').strip()
    date_of_birth = request.data.get('date_of_birth')

    if not identifier or not date_of_birth:
        return Response(
            {'error': "Enter the email or phone number used to apply, along with the date of birth."},
            status=status.HTTP_400_BAD_REQUEST
        )

    applications = Application.objects.filter(
        Q(contact_email__iexact=identifier) | Q(contact_phone=identifier),
        date_of_birth=date_of_birth,
    ).order_by('-created_at')

    if not applications.exists():
        return Response(
            {'error': 'No application found for those details. Check the email or phone number and try again.'},
            status=status.HTTP_404_NOT_FOUND
        )

    results = [{
        'reference': app.reference,
        'full_name': app.full_name,
        'level_display': app.get_level_display(),
        'status': app.status,
        'status_display': app.get_status_display(),
        'is_paid': app.is_paid,
        'fee_amount': float(app.fee_amount),
        'missing_fields': app.missing_fields(),
        'can_print': bool(app.submitted_at),
    } for app in applications]

    return Response({'applications': results})


def _get_application_or_error(reference):
    application = Application.objects.filter(reference=reference).first()
    if not application:
        return None, Response(
            {'error': 'Application not found'}, status=status.HTTP_404_NOT_FOUND
        )
    return application, None


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def application_detail(request, reference):
    """Fetch one application by reference — used by the form and the printable page."""
    application, error = _get_application_or_error(reference)
    if error:
        return error
    return Response(ApplicationSerializer(application, context={'request': request}).data)


@api_view(['PATCH'])
@permission_classes([permissions.AllowAny])
def save_application_form(request, reference):
    """
    Autosave. Only works once the fee is paid, and locks after submission so a
    printed form cannot be edited out from under management.
    """
    application, error = _get_application_or_error(reference)
    if error:
        return error

    if not application.is_paid:
        return Response(
            {'error': 'The application fee has not been paid yet.'},
            status=status.HTTP_402_PAYMENT_REQUIRED
        )

    if application.submitted_at:
        return Response(
            {'error': 'This application has already been submitted and can no longer be edited.'},
            status=status.HTTP_409_CONFLICT
        )

    serializer = ApplicationFormSerializer(application, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    application.refresh_from_db()
    return Response({
        'saved_at': application.last_saved_at,
        'missing_fields': application.missing_fields(),
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def submit_application(request, reference):
    """Final submit — refuses while any required field is still blank."""
    application, error = _get_application_or_error(reference)
    if error:
        return error

    if not application.is_paid:
        return Response(
            {'error': 'The application fee has not been paid yet.'},
            status=status.HTTP_402_PAYMENT_REQUIRED
        )

    if application.submitted_at:
        return Response(ApplicationSerializer(application, context={'request': request}).data)

    missing = application.missing_fields()
    if missing:
        return Response(
            {'error': 'Some required fields are still empty.', 'missing_fields': missing},
            status=status.HTTP_400_BAD_REQUEST
        )

    application.status = Application.Status.SUBMITTED
    application.submitted_at = timezone.now()
    application.save()

    return Response(ApplicationSerializer(application, context={'request': request}).data)


# ==========================================================================
# Admissions — management endpoints
# ==========================================================================


class AdmissionSettingViewSet(viewsets.ModelViewSet):
    """Open/close the admission window and set the fee for each level."""
    queryset = AdmissionSetting.objects.select_related('academic_year').prefetch_related('fees')
    serializer_class = AdmissionSettingSerializer
    permission_classes = [IsManagementOrAdmin]

    @action(detail=True, methods=['put'])
    def fees(self, request, pk=None):
        """
        Replace the whole fee table in one call. Body: {"fees": [{"level": 7,
        "amount": "15000"}, ...]}. Levels left out become unavailable to apply to.
        """
        setting = self.get_object()
        rows = request.data.get('fees', [])

        if not isinstance(rows, list):
            return Response(
                {'error': 'fees must be a list'}, status=status.HTTP_400_BAD_REQUEST
            )

        valid_levels = {value for value, _ in ClassLevel.choices}
        cleaned = []
        for row in rows:
            level = row.get('level')
            amount = row.get('amount')
            if level not in valid_levels:
                return Response(
                    {'error': f'Unknown class level: {level}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return Response(
                    {'error': f'Invalid amount for level {level}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if amount < 0:
                return Response(
                    {'error': f'Amount for level {level} cannot be negative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cleaned.append({'level': level, 'amount': amount})

        setting.fees.all().delete()
        AdmissionFee.objects.bulk_create([
            AdmissionFee(setting=setting, level=row['level'], amount=row['amount'])
            for row in cleaned
        ])

        setting.refresh_from_db()
        return Response(AdmissionSettingSerializer(setting).data)


class ApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Management review of admission applications. Read-only plus a decision
    action — nobody edits an applicant's answers on their behalf.
    """
    queryset = Application.objects.select_related('academic_year', 'decided_by')
    permission_classes = [IsManagementOrAdmin]

    def get_serializer_class(self):
        if self.action == 'list':
            return ApplicationListSerializer
        return ApplicationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        status_filter = params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        level = params.get('level')
        if level:
            queryset = queryset.filter(level=level)

        academic_year = params.get('academic_year')
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(reference__icontains=search)
                | Q(contact_phone__icontains=search)
                | Q(contact_email__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def decision(self, request, pk=None):
        """Record an admit / waitlist / reject decision, or send it back to review."""
        application = self.get_object()
        decision = request.data.get('decision')

        allowed = [
            Application.Status.UNDER_REVIEW,
            Application.Status.ADMITTED,
            Application.Status.WAITLISTED,
            Application.Status.REJECTED,
        ]
        if decision not in allowed:
            return Response(
                {'error': f'decision must be one of: {", ".join(allowed)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not application.submitted_at:
            return Response(
                {'error': 'This application has not been submitted yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        application.status = decision
        application.decision_note = request.data.get('note', '')
        application.decided_by = request.user
        application.decided_at = timezone.now()
        application.save()

        return Response(ApplicationSerializer(application, context={'request': request}).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Counts per status for the dashboard cards."""
        queryset = self.get_queryset()
        counts = {
            row['status']: row['total']
            for row in queryset.values('status').annotate(total=Count('id'))
        }

        return Response({
            'total': queryset.count(),
            'by_status': {
                value: counts.get(value, 0) for value, _ in Application.Status.choices
            },
            'total_collected': float(
                queryset.aggregate(total=Sum('amount_paid'))['total'] or 0
            ),
        })
