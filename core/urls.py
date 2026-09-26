from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
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
router.register(r'staff-salaries', views.StaffSalaryViewSet)
router.register(r'announcements', views.AnnouncementViewSet)
router.register(r'attendance', views.AttendanceViewSet)
router.register(r'admission-settings', views.AdmissionSettingViewSet)
router.register(r'applications', views.ApplicationViewSet)

# URL patterns
urlpatterns = [
    # Custom endpoints BEFORE router (prevents router from swallowing them as pk lookups)
    path('academic-years/toggle-results/', views.toggle_results_visibility, name='toggle_results'),

    # Include router URLs
    path('', include(router.urls)),

    # Authentication endpoints
    path('auth/login/', views.login_view, name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Dashboard endpoints
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),

    # Rankings endpoints
    path('rankings/class/', views.get_class_rankings, name='class_rankings'),

    # Promotion endpoint
    path('promote-students/', views.promote_students, name='promote_students'),

    # Secure Flutterwave payment verification
    path('payments/verify/', views.verify_flutterwave_payment, name='verify_payment'),

    # Flutterwave webhook — called by Flutterwave server when payment completes
    path('payments/webhook/', views.flutterwave_webhook, name='flutterwave_webhook'),

    # Management/admin recording an offline (cash, bank transfer, etc.) payment
    path('payments/record-manual/', views.record_manual_payment, name='record_manual_payment'),

    # Get per-term fee for current student
    path('fees/student-term-fee/', views.get_student_term_fee, name='student_term_fee'),

    # Admissions — public, no authentication. Applicants never get an account.
    path('admissions/info/', views.admission_info, name='admission_info'),
    path('admissions/start/', views.start_application, name='start_application'),
    path('admissions/verify-payment/', views.verify_application_payment, name='verify_application_payment'),
    path('admissions/webhook/', views.application_payment_webhook, name='application_webhook'),
    path('admissions/lookup/', views.lookup_application, name='lookup_application'),
    path('admissions/<str:reference>/save/', views.save_application_form, name='save_application'),
    path('admissions/<str:reference>/submit/', views.submit_application, name='submit_application'),
    path('admissions/<str:reference>/', views.application_detail, name='application_detail'),

]