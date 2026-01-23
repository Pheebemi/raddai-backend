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
                return StudentSerializer(profile).data
            elif obj.role == 'staff':
                return StaffSerializer(profile).data
            elif obj.role == 'parent':
                return ParentSerializer(profile).data
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
        return ClassSerializer(obj.class_teacher.all(), many=True).data


class ParentSerializer(serializers.ModelSerializer):
    """Serializer for Parent model"""
    user_details = UserSerializer(source='user', read_only=True)
    children_details = StudentSerializer(source='children', many=True, read_only=True)

    class Meta:
        model = Parent
        fields = '__all__'


class ResultSerializer(serializers.ModelSerializer):
    """Serializer for Result model"""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = '__all__'

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.user.get_full_name()
        return None


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