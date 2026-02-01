from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Count, Sum
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


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

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
        return [permissions.IsAuthenticated(), permissions.IsAdminOrReadOnly()]


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
        stats = {
            'total_students': Student.objects.count(),
            'total_staff': Staff.objects.count(),
            'total_parents': Parent.objects.count(),
            'total_classes': Class.objects.count(),
            'total_subjects': Subject.objects.count(),
            'pending_fee_payments': FeePayment.objects.filter(status='pending').count(),
            'recent_announcements': Announcement.objects.filter(
                is_active=True, for_management=True
            ).order_by('-created_at')[:5].count()
        }

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
            stats = {
                'current_class': student_profile.current_class.name if student_profile.current_class else None,
                'total_results': Result.objects.filter(student=student_profile).count(),
                'pending_fees': FeePayment.objects.filter(
                    student=student_profile, status='pending'
                ).count(),
                'attendance_percentage': 0,  # Would need calculation
                'recent_announcements': Announcement.objects.filter(
                    is_active=True, for_students=True
                ).order_by('-created_at')[:5].count()
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