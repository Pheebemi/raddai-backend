from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register viewsets
router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'academic-years', views.AcademicYearViewSet)
router.register(r'classes', views.ClassViewSet)
router.register(r'subjects', views.SubjectViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'staff', views.StaffViewSet)
router.register(r'parents', views.ParentViewSet)
router.register(r'results', views.ResultViewSet)
router.register(r'fee-structures', views.FeeStructureViewSet)
router.register(r'fee-payments', views.FeePaymentViewSet)
router.register(r'announcements', views.AnnouncementViewSet)
router.register(r'attendance', views.AttendanceViewSet)

# URL patterns
urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),

    # Authentication endpoints
    path('auth/login/', views.login_view, name='login'),

    # Dashboard endpoints
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
]