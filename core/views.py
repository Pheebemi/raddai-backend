from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Sum
from django.utils import timezone
from .models import (
    User, AcademicYear, Class, Subject, Student, Staff, Parent,
    Result, FeeStructure, FeePayment, StaffSalary, Announcement, Attendance
)
from .serializers import (
    UserSerializer, LoginSerializer, AcademicYearSerializer,
    ClassSerializer, SubjectSerializer, StudentSerializer,
    StaffSerializer, ParentSerializer, ResultSerializer,
    FeeStructureSerializer, FeePaymentSerializer, StaffSalarySerializer,
    AnnouncementSerializer, AttendanceSerializer
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

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return Attendance.objects.all()
        elif user.role == 'staff':
            try:
                staff_profile = user.staff_profile
                return Attendance.objects.filter(class_period__class_teacher=staff_profile)
            except Exception:
                return Attendance.objects.none()
        elif user.role == 'student':
            try:
                student_profile = user.student_profile
                return Attendance.objects.filter(student=student_profile)
            except Exception:
                return Attendance.objects.none()
        elif user.role == 'parent':
            try:
                parent_profile = user.parent_profile
                return Attendance.objects.filter(student__in=parent_profile.children.all())
            except Exception:
                return Attendance.objects.none()
        return Attendance.objects.none()


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

    if tx_data.get('status') != 'successful':
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

        results = Result.objects.filter(
            student__current_class_id=class_id_int,
            term=term,
            academic_year=academic_year_obj
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
def dashboard_stats(request):
    user = request.user
    stats = {}

    if user.role == 'management':
        revenue_agg = FeePayment.objects.filter(status='paid').aggregate(total=Sum('amount_paid'))
        total_revenue = float(revenue_agg['total'] or 0)

        pending_agg = FeePayment.objects.filter(status__in=['pending', 'overdue']).aggregate(total=Sum('total_amount'))
        pending_fees = float(pending_agg['total'] or 0)

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
