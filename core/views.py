from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Count, Sum, Exists, OuterRef
from django.utils import timezone
from .models import (
    User, AcademicYear, Class, Subject, Student, Staff, Parent,
    Result, FeeStructure, FeePayment, Announcement, Attendance
)
from .serializers import (
    UserSerializer, LoginSerializer, AcademicYearSerializer,
    ClassSerializer, SubjectSerializer, StudentSerializer,
    StaffSerializer, ParentSerializer, ResultSerializer,
    FeeStructureSerializer, FeePaymentSerializer,
    AnnouncementSerializer, AttendanceSerializer
)


class IsOwnerOrAdmin(permissions.BasePermission):
    """Custom permission to only allow owners of an object or admins to access it"""

    def has_permission(self, request, view):
        """Check if user has permission to access the view"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin' or request.user.role == 'management':
            return True

        # Students can access their own data
        if request.user.role == 'student' and hasattr(obj, 'user'):
            return obj.user == request.user

        # Staff can access their own data and students they teach
        if request.user.role == 'staff':
            if hasattr(obj, 'user') and obj.user == request.user:
                return True
            if hasattr(obj, 'student'):
                # Check if staff teaches this student's class/subject
                try:
                    staff_profile = request.user.staff_profile
                    return (obj.student.current_class and
                           obj.student.current_class.class_teacher == staff_profile)
                except:
                    return False

        # Parents can access their children's data
        if request.user.role == 'parent':
            try:
                parent_profile = request.user.parent_profile
                if hasattr(obj, 'student') and obj.student in parent_profile.children.all():
                    return True
                if hasattr(obj, 'user') and obj.user == request.user:
                    return True
            except:
                return False

        return False


class IsStaffOrAdmin(permissions.BasePermission):
    """Custom permission to only allow staff or admins to create/update results"""

    def has_permission(self, request, view):
        """Check if user is staff or admin"""
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['staff', 'admin', 'management']


class IsManagementOrAdmin(permissions.BasePermission):
    """Custom permission to only allow management or admins to create announcements"""

    def has_permission(self, request, view):
        """Check if user is management or admin"""
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['management', 'admin']


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_permissions(self):
        """Allow management and admin to create users, others can only access their own data"""
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return User.objects.all()
        elif user.role == 'staff':
            # Staff can see students in their classes
            try:
                staff_profile = user.staff_profile
                student_ids = []
                if staff_profile.class_teacher.exists():
                    for class_obj in staff_profile.class_teacher.all():
                        student_ids.extend(class_obj.students.values_list('user_id', flat=True))
                return User.objects.filter(Q(id=user.id) | Q(id__in=student_ids))
            except:
                return User.objects.filter(id=user.id)
        elif user.role == 'parent':
            # Parents can see themselves and their children
            try:
                parent_profile = user.parent_profile
                children_ids = parent_profile.children.values_list('user_id', flat=True)
                return User.objects.filter(Q(id=user.id) | Q(id__in=children_ids))
            except:
                return User.objects.filter(id=user.id)
        else:
            # Students can only see themselves
            return User.objects.filter(id=user.id)

    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update current user's profile"""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AcademicYearViewSet(viewsets.ModelViewSet):
    """ViewSet for AcademicYear model"""
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), permissions.IsAdminOrReadOnly()]


class ClassViewSet(viewsets.ModelViewSet):
    """ViewSet for Class model"""
    queryset = Class.objects.all()
    serializer_class = ClassSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), permissions.IsAdminOrReadOnly()]


class SubjectViewSet(viewsets.ModelViewSet):
    """ViewSet for Subject model"""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), permissions.IsAdminOrReadOnly()]


class StudentViewSet(viewsets.ModelViewSet):
    """ViewSet for Student model"""
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_permissions(self):
        """Allow management and admin to create students"""
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return Student.objects.all()
        elif user.role == 'staff':
            # Staff can see students in their classes
            try:
                staff_profile = user.staff_profile
                return Student.objects.filter(current_class__class_teacher=staff_profile)
            except:
                return Student.objects.none()
        elif user.role == 'parent':
            # Parents can see their children
            try:
                parent_profile = user.parent_user
                return parent_profile.children.all()
            except:
                return Student.objects.none()
        else:
            # Students can only see themselves
            try:
                return Student.objects.filter(user=user)
            except:
                return Student.objects.none()


class StaffViewSet(viewsets.ModelViewSet):
    """ViewSet for Staff model"""
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_permissions(self):
        """Allow management and admin to create staff"""
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'management']:
            return Staff.objects.all()
        else:
            # Others can only see their own staff profile
            try:
                return Staff.objects.filter(user=user)
            except:
                return Staff.objects.none()

    @action(detail=True, methods=['post'], url_path='assign-class')
    def assign_class(self, request, pk=None):
        """
        Assign or unassign this staff member as class teacher for a class.

        Expects:
        - class_id: ID of the class to assign as class teacher
          If null/empty, unassigns the staff from any class.
        """
        staff = self.get_object()
        class_id = request.data.get('class_id')

        # Unassign from all classes if no class_id provided
        if not class_id:
            Class.objects.filter(class_teacher=staff).update(class_teacher=None)
            serializer = self.get_serializer(staff)
            return Response(serializer.data)

        try:
            target_class = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            return Response({'detail': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure this staff is class teacher for at most one class:
        # clear previous assignments on other classes
        Class.objects.filter(class_teacher=staff).exclude(pk=target_class.pk).update(class_teacher=None)

        target_class.class_teacher = staff
        target_class.save()

        serializer = self.get_serializer(staff)
        return Response(serializer.data)


class ParentViewSet(viewsets.ModelViewSet):
    """ViewSet for Parent model"""
    queryset = Parent.objects.all()
    serializer_class = ParentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'management']:
            return Parent.objects.all()
        else:
            # Others can only see their own parent profile
            try:
                return Parent.objects.filter(user=user)
            except:
                return Parent.objects.none()


class ResultViewSet(viewsets.ModelViewSet):
    """ViewSet for Result model"""
    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def perform_create(self, serializer):
        """Set the uploaded_by field to the current staff user when creating results"""
        if self.request.user.role == 'staff':
            serializer.save(uploaded_by=self.request.user.staff_profile)
        else:
            serializer.save()

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return Result.objects.all()
        elif user.role == 'staff':
            # Staff can see results they uploaded or for students they teach
            try:
                staff_profile = user.staff_profile
                return Result.objects.filter(
                    Q(uploaded_by=staff_profile) |
                    Q(student__current_class__class_teacher=staff_profile)
                )
            except:
                return Result.objects.none()
        elif user.role == 'student':
            # Students can see their own results
            try:
                student_profile = user.student_profile
                return Result.objects.filter(student=student_profile)
            except:
                return Result.objects.none()
        elif user.role == 'parent':
            # Parents can see their children's results
            try:
                parent_profile = user.parent_profile
                return Result.objects.filter(student__in=parent_profile.children.all())
            except:
                return Result.objects.none()
        return Result.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        # Only staff can create/update results
        elif self.action in ['create', 'update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsStaffOrAdmin()]
        return [permissions.IsAuthenticated(), permissions.IsAdminOrReadOnly()]


class FeeStructureViewSet(viewsets.ModelViewSet):
    """ViewSet for FeeStructure model"""
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), permissions.IsAdminOrReadOnly()]


class FeePaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for FeePayment model"""
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return FeePayment.objects.all()
        elif user.role == 'student':
            # Students can see their own fee payments
            try:
                student_profile = user.student_profile
                return FeePayment.objects.filter(student=student_profile)
            except:
                return FeePayment.objects.none()
        elif user.role == 'parent':
            # Parents can see their children's fee payments
            try:
                parent_profile = user.parent_profile
                return FeePayment.objects.filter(student__in=parent_profile.children.all())
            except:
                return FeePayment.objects.none()
        return FeePayment.objects.none()

    def create(self, request, *args, **kwargs):
        """
        Support part payments per term.

        For each (student, academic_year, term) we keep a single FeePayment row and
        accumulate `amount_paid` on it. `total_amount` represents the full fee for
        that term. Status rules:
        - amount_paid == 0            -> pending
        - 0 < amount_paid < total     -> partial
        - amount_paid >= total        -> paid
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = data.get('student')
        academic_year = data.get('academic_year')
        term = data.get('term')
        fee_structure = data.get('fee_structure')
        incoming_amount = data.get('amount_paid') or 0

        print(f"📥 Payment request data: student={student}, academic_year={academic_year}, term={term}, fee_structure={fee_structure}, incoming_amount={incoming_amount}")

        # Always determine the full term fee from the student's actual class grade
        # and academic year, so each class uses its own configured fee even if an
        # old/wrong fee_structure was saved previously.
        from .models import FeeStructure as FSModel

        full_amount = None
        resolved_fee_structure = fee_structure

        try:
            if student and hasattr(student, 'current_class') and student.current_class and academic_year:
                grade = student.current_class.grade
                fs_qs = FSModel.objects.filter(
                    academic_year=academic_year,
                    grade=grade,
                    fee_type=FSModel.FeeType.TUITION,
                )
                resolved_fee_structure = fs_qs.first() or fee_structure
                if resolved_fee_structure and getattr(resolved_fee_structure, 'amount', None) is not None:
                    full_amount = resolved_fee_structure.amount
                    print(f"📋 Using grade-based fee_structure.amount: {full_amount} for grade={grade}, academic_year={academic_year.id}, fee_structure_id={resolved_fee_structure.id}")

        except Exception as e:
            print(f"⚠️ Failed to resolve grade-based fee_structure: {e}")

        # Fallbacks if we still don't have a full_amount
        if full_amount is None:
            if resolved_fee_structure and hasattr(resolved_fee_structure, 'amount') and resolved_fee_structure.amount is not None:
                full_amount = resolved_fee_structure.amount
                print(f"📋 Fallback to resolved_fee_structure.amount: {full_amount} for fee_structure {resolved_fee_structure.id}")
            else:
                full_amount = data.get('total_amount') or incoming_amount
                print(f"📋 Fallback to payload total_amount or incoming_amount: {full_amount}")

        # Always work with the resolved fee_structure (grade-correct if found)
        fee_structure = resolved_fee_structure

        print(f"💰 Payment processing: student={getattr(student, 'id', None)}, term={term}, academic_year={getattr(academic_year, 'id', None)}, incoming_amount={incoming_amount}, full_amount={full_amount}, fee_structure_id={getattr(fee_structure, 'id', None)}")

        existing = FeePayment.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).first()

        if existing:
            # Accumulate amount_paid on the existing record
            new_amount_paid = (existing.amount_paid or 0) + incoming_amount
            # Cap at full_amount to avoid over-payment in records
            if full_amount:
                new_amount_paid = min(new_amount_paid, full_amount)

            existing.amount_paid = new_amount_paid
            # Keep or set total_amount as the full required amount
            if full_amount:
                existing.total_amount = full_amount

            # Update helpful audit fields from the latest payment
            existing.payment_method = data.get('payment_method') or existing.payment_method
            existing.transaction_id = data.get('transaction_id') or existing.transaction_id
            existing.remarks = data.get('remarks') or existing.remarks
            existing.due_date = data.get('due_date') or existing.due_date

            # Compute status
            print(f"📊 Status calculation: full_amount={full_amount}, new_amount_paid={new_amount_paid}, condition={full_amount and new_amount_paid >= full_amount}")
            if full_amount and new_amount_paid >= full_amount:
                existing.status = FeePayment.PaymentStatus.PAID
                print(f"✅ Status set to PAID")
            elif new_amount_paid > 0:
                existing.status = FeePayment.PaymentStatus.PARTIAL
                print(f"⚠️ Status set to PARTIAL")
            else:
                existing.status = FeePayment.PaymentStatus.PENDING
                print(f"⏳ Status set to PENDING")

            existing.save()
            print(f"💾 Payment saved with status: {existing.status}")
            output_serializer = self.get_serializer(existing)
            return Response(output_serializer.data, status=status.HTTP_200_OK)

        # No existing record -> create a new one and set status based on first payment
        total_amount = full_amount or incoming_amount
        amount_paid = min(incoming_amount, total_amount)

        print(f"🆕 Creating new payment: total_amount={total_amount}, amount_paid={amount_paid}, condition={total_amount and amount_paid >= total_amount}")
        if total_amount and amount_paid >= total_amount:
            status_value = FeePayment.PaymentStatus.PAID
            print(f"✅ New payment status: PAID")
        elif amount_paid > 0:
            status_value = FeePayment.PaymentStatus.PARTIAL
            print(f"⚠️ New payment status: PARTIAL")
        else:
            status_value = FeePayment.PaymentStatus.PENDING
            print(f"⏳ New payment status: PENDING")

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


class AnnouncementViewSet(viewsets.ModelViewSet):
    """ViewSet for Announcement model"""
    queryset = Announcement.objects.filter(is_active=True)
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Announcement.objects.filter(is_active=True)

        # Filter announcements based on target audience
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
        """Set the created_by field to the current user when creating announcements"""
        serializer.save(created_by=self.request.user)


class AttendanceViewSet(viewsets.ModelViewSet):
    """ViewSet for Attendance model"""
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'management':
            return Attendance.objects.all()
        elif user.role == 'staff':
            # Staff can see attendance for classes they teach
            try:
                staff_profile = user.staff_profile
                return Attendance.objects.filter(class_period__class_teacher=staff_profile)
            except:
                return Attendance.objects.none()
        elif user.role == 'student':
            # Students can see their own attendance
            try:
                student_profile = user.student_profile
                return Attendance.objects.filter(student=student_profile)
            except:
                return Attendance.objects.none()
        elif user.role == 'parent':
            # Parents can see their children's attendance
            try:
                parent_profile = user.parent_profile
                return Attendance.objects.filter(student__in=parent_profile.children.all())
            except:
                return Attendance.objects.none()
        return Attendance.objects.none()


# Authentication views
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    """Handle user login and return JWT tokens"""
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


# Dashboard views for different user roles
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_class_rankings(request):
    """Get student rankings for a specific class, term, and academic year"""
    class_id = request.GET.get('class_id')
    term = request.GET.get('term')
    academic_year = request.GET.get('academic_year')

    print(f"Rankings request: class_id={class_id}, term={term}, academic_year={academic_year}")

    if not all([class_id, term, academic_year]):
        return Response(
            {'error': 'class_id, term, and academic_year are required parameters'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Validate inputs
        try:
            class_id_int = int(class_id)
            academic_year_int = int(academic_year)
        except ValueError:
            return Response(
                {'error': 'class_id and academic_year must be valid integers'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate term
        if term not in ['first', 'second', 'third']:
            return Response(
                {'error': 'term must be one of: first, second, third'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if class exists
        if not Class.objects.filter(id=class_id_int).exists():
            return Response(
                {'error': f'Class with id {class_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if academic year exists
        if not AcademicYear.objects.filter(id=academic_year_int).exists():
            return Response(
                {'error': f'Academic year with id {academic_year} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all results for this class, term, and academic year
        results = Result.objects.filter(
            student__current_class_id=class_id_int,
            term=term,
            academic_year_id=academic_year_int
        ).select_related('student', 'subject', 'academic_year')

        print(f"Found {len(results)} results for class_id={class_id_int}, term={term}, academic_year={academic_year_int}")

        # Debug: Check if there are any students in this class
        class_students = Student.objects.filter(current_class_id=class_id_int)
        print(f"Class has {len(class_students)} students total")

        # Debug: Check if there are any results for this class at all
        all_class_results = Result.objects.filter(student__current_class_id=class_id_int)
        print(f"Class has {len(all_class_results)} results total across all terms/years")

        if not results:
            return Response({
                'rankings': [],
                'message': 'No results found for the specified criteria',
                'total_students': 0,
                'class_info': {
                    'class_id': class_id,
                    'term': term,
                    'academic_year': academic_year
                }
            })

        # Group results by student and calculate cumulative average
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

            # Add subject result
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

        print(f"Processed {len(student_averages)} students")

        # Calculate average percentage for each student
        rankings_list = []
        for student_data in student_averages.values():
            if student_data['total_max_score'] > 0:
                average_percentage = (student_data['total_weighted_score'] / student_data['total_max_score']) * 100
                student_data['average_percentage'] = round(average_percentage, 2)
                rankings_list.append(student_data)
            else:
                student_data['average_percentage'] = 0.0
                rankings_list.append(student_data)

        # Sort by average percentage descending
        rankings_list.sort(key=lambda x: x['average_percentage'], reverse=True)

        print(f"Generated rankings for {len(rankings_list)} students")

        # Assign positions, handling ties
        current_position = 1
        previous_percentage = None

        for i, student in enumerate(rankings_list):
            if previous_percentage is not None and student['average_percentage'] < previous_percentage:
                current_position = i + 1

            student['position'] = current_position
            previous_percentage = student['average_percentage']

        print("Rankings calculation completed successfully")

        return Response({
            'rankings': rankings_list,
            'total_students': len(rankings_list),
            'class_info': {
                'class_id': class_id,
                'term': term,
                'academic_year': academic_year
            }
        })

    except Exception as e:
        import traceback
        print(f"Error in get_class_rankings: {str(e)}")
        print(traceback.format_exc())
        return Response(
            {'error': f'Failed to calculate rankings: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    """Get dashboard statistics based on user role"""
    user = request.user
    stats = {}

    if user.role == 'management':
        # School-wide statistics
        # Calculate revenue from paid fee payments (use amount_paid for actual collected amount)
        revenue_agg = FeePayment.objects.filter(status='paid').aggregate(
            total=Sum('amount_paid')
        )
        total_revenue = revenue_agg['total']
        if total_revenue is None:
            total_revenue = 0
        else:
            total_revenue = float(total_revenue)

        print(f"Total revenue calculation: {total_revenue}")
        print(f"Revenue aggregate result: {revenue_agg}")
        print(f"Paid payments count: {FeePayment.objects.filter(status='paid').count()}")

        # Calculate pending fees
        pending_agg = FeePayment.objects.filter(status__in=['pending', 'overdue']).aggregate(
            total=Sum('total_amount')
        )
        pending_fees = pending_agg['total']
        if pending_fees is None:
            pending_fees = 0
        else:
            pending_fees = float(pending_fees)

        print(f"Pending fees calculation: {pending_fees}")
        print(f"Pending aggregate result: {pending_agg}")
        print(f"Pending payments count: {FeePayment.objects.filter(status__in=['pending', 'overdue']).count()}")

        # Get top performers (students with highest average grades)
        top_performers = []
        # This would require complex aggregation - for now, get recent high-grade results
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

        # Get recent results
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

        # Calculate average attendance (placeholder for now)
        average_attendance = 85  # This would need Attendance model data

        print(f"Final stats before return: total_revenue={total_revenue}, pending_fees={pending_fees}")

        stats = {
            'total_students': Student.objects.count(),
            'total_staff': Staff.objects.count(),
            'total_parents': Parent.objects.count(),
            'total_classes': Class.objects.count(),
            'total_subjects': Subject.objects.count(),
            'total_revenue': float(total_revenue) if total_revenue else 0.0,
            'pending_fees': float(pending_fees) if pending_fees else 0.0,
            'average_attendance': average_attendance,
            'top_performers': top_performers,
            'recent_results': recent_results_data,
            'pending_fee_payments': FeePayment.objects.filter(status='pending').count(),
            'recent_announcements': Announcement.objects.filter(
                is_active=True, for_management=True
            ).order_by('-created_at')[:5].count()
        }

        print(f"Stats dict: {stats}")

    elif user.role == 'staff':
        try:
            staff_profile = user.staff_user
            stats = {
                'assigned_classes': staff_profile.class_teacher.count(),
                'assigned_subjects': staff_profile.subjects.count(),
                'pending_results': 0,  # Would need more complex logic
                'students_count': sum(
                    class_obj.students.count()
                    for class_obj in staff_profile.class_teacher.all()
                ),
                'recent_announcements': Announcement.objects.filter(
                    is_active=True, for_staff=True
                ).order_by('-created_at')[:5].count()
            }
        except:
            stats = {'error': 'Staff profile not found'}

    elif user.role == 'student':
        try:
            student_profile = user.student_profile

            # Current class name
            current_class_name = (
                student_profile.current_class.name if student_profile.current_class else None
            )

            # Determine the relevant academic year (active or latest)
            academic_year = (
                AcademicYear.objects.filter(is_active=True).first()
                or AcademicYear.objects.order_by('-start_date').first()
            )

            session_pending_fees = 0

            if academic_year and student_profile.current_class:
                # We treat the tuition fee defined in FeeStructure for this grade + year
                # as the per-term fee, then multiply by 3 terms for the session total.
                grade = student_profile.current_class.grade

                tuition_qs = FeeStructure.objects.filter(
                    academic_year=academic_year,
                    grade=grade,
                    fee_type=FeeStructure.FeeType.TUITION,
                )

                per_term_fee = tuition_qs.aggregate(total=Sum('amount'))['total'] or 0

                # Total expected for the whole academic session (3 terms)
                session_total_fee = per_term_fee * 3

                # Total actually paid by this student for this academic year (all terms)
                paid_agg = FeePayment.objects.filter(
                    student=student_profile,
                    academic_year=academic_year,
                ).aggregate(total=Sum('amount_paid'))

                total_paid = paid_agg['total'] or 0

                # Pending amount = expected session fee minus all payments made (never negative)
                raw_pending = session_total_fee - total_paid
                if raw_pending < 0:
                    raw_pending = 0

                session_pending_fees = float(raw_pending)

            stats = {
                'current_class': current_class_name,
                'total_results': Result.objects.filter(student=student_profile).count(),
                # Monetary pending fees for the current/active academic session
                'pending_fees': session_pending_fees,
                'attendance_percentage': 0,  # Would need calculation
                'recent_announcements': Announcement.objects.filter(
                    is_active=True, for_students=True
                ).order_by('-created_at')[:5].count(),
            }
        except:
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
        except:
            stats = {'error': 'Parent profile not found'}

    return Response(stats)