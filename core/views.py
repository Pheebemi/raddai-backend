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
            return [permissions.IsAuthenticated(), permissions.BasePermission]  # Custom permission needed
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