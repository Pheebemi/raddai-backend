from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    User, AcademicYear, Class, Subject, Student, Staff, Parent,
    Result, FeeStructure, FeePayment, Announcement, Attendance
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    full_name = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'phone_number', 'date_of_birth', 'address', 'profile'
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_profile(self, obj):
        profile = obj.get_profile()
        if profile:
            if obj.role == 'student':
                return {
                    'id': profile.id,
                    'student_id': profile.student_id,
                    'current_class': profile.current_class.name if profile.current_class else None,
                    'admission_date': profile.admission_date,
                }
            elif obj.role == 'staff':
                return {
                    'id': profile.id,
                    'staff_id': profile.staff_id,
                    'designation': profile.designation,
                    'joining_date': profile.joining_date,
                }
            elif obj.role == 'parent':
                return {
                    'id': profile.id,
                    'parent_id': profile.parent_id,
                    'children_count': profile.children.count(),
                }
        return None

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
            return attrs
        raise serializers.ValidationError('Must include username and password')


class AcademicYearSerializer(serializers.ModelSerializer):
    """Serializer for AcademicYear model"""

    class Meta:
        model = AcademicYear
        fields = '__all__'


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Subject model"""

    class Meta:
        model = Subject
        fields = '__all__'


class ClassSerializer(serializers.ModelSerializer):
    """Serializer for Class model"""
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    class_teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = '__all__'

    def get_class_teacher_name(self, obj):
        if obj.class_teacher:
            return obj.class_teacher.user.get_full_name()
        return None


class StudentSerializer(serializers.ModelSerializer):
    """Serializer for Student model"""
    user_details = UserSerializer(source='user', read_only=True)
    current_class_name = serializers.CharField(source='current_class.name', read_only=True)
    parents_count = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = '__all__'

    def get_parents_count(self, obj):
        return obj.parents.count()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove user_details to avoid circular reference when used in nested serialization
        if hasattr(self, 'parent') and isinstance(self.parent, serializers.Serializer):
            self.fields.pop('user_details', None)


class StaffSerializer(serializers.ModelSerializer):
    """Serializer for Staff model"""
    user_details = UserSerializer(source='user', read_only=True)
    subjects_count = serializers.SerializerMethodField()
    assigned_classes = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = '__all__'

    def get_subjects_count(self, obj):
        return obj.subjects.count()

    def get_assigned_classes(self, obj):
        # Since class_teacher is OneToOne, return array with single class or empty array
        if obj.class_teacher:
            return [ClassSerializer(obj.class_teacher).data]
        return []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove user_details to avoid circular reference when used in nested serialization
        if hasattr(self, 'parent') and isinstance(self.parent, serializers.Serializer):
            self.fields.pop('user_details', None)


class ParentSerializer(serializers.ModelSerializer):
    """Serializer for Parent model"""
    user_details = UserSerializer(source='user', read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = '__all__'

    def get_children_count(self, obj):
        return obj.children.count()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove user_details to avoid circular reference when used in nested serialization
        if hasattr(self, 'parent') and isinstance(self.parent, serializers.Serializer):
            self.fields.pop('user_details', None)


class ResultSerializer(serializers.ModelSerializer):
    """Serializer for Result model"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    ca_total = serializers.ReadOnlyField()
    percentage = serializers.ReadOnlyField()

    class Meta:
        model = Result
        fields = [
            'id', 'student', 'student_name', 'subject', 'subject_name',
            'academic_year', 'academic_year_name', 'term',
            'ca1_score', 'ca2_score', 'ca3_score', 'ca4_score', 'ca_total',
            'exam_score', 'marks_obtained', 'total_marks', 'percentage',
            'grade', 'remarks', 'uploaded_by', 'uploaded_by_name', 'upload_date'
        ]
        read_only_fields = ['marks_obtained', 'total_marks', 'grade', 'ca_total', 'percentage']

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.user.get_full_name()
        return None

    def validate_ca1_score(self, value):
        if value < 0 or value > 10:
            raise serializers.ValidationError("CA1 score must be between 0 and 10")
        return value

    def validate_ca2_score(self, value):
        if value < 0 or value > 10:
            raise serializers.ValidationError("CA2 score must be between 0 and 10")
        return value

    def validate_ca3_score(self, value):
        if value < 0 or value > 10:
            raise serializers.ValidationError("CA3 score must be between 0 and 10")
        return value

    def validate_ca4_score(self, value):
        if value < 0 or value > 10:
            raise serializers.ValidationError("CA4 score must be between 0 and 10")
        return value

    def validate_exam_score(self, value):
        if value < 0 or value > 60:
            raise serializers.ValidationError("Exam score must be between 0 and 60")
        return value


class FeeStructureSerializer(serializers.ModelSerializer):
    """Serializer for FeeStructure model"""
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)

    class Meta:
        model = FeeStructure
        fields = '__all__'


class FeePaymentSerializer(serializers.ModelSerializer):
    """Serializer for FeePayment model"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    fee_type_name = serializers.CharField(source='fee_structure.fee_type', read_only=True)
    academic_year = serializers.CharField(source='fee_structure.academic_year.name', read_only=True)

    class Meta:
        model = FeePayment
        fields = '__all__'


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Announcement
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for Attendance model"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    class_name = serializers.CharField(source='class_period.name', read_only=True)
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = '__all__'

    def get_marked_by_name(self, obj):
        if obj.marked_by:
            return obj.marked_by.user.get_full_name()
        return None