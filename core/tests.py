from datetime import date

from rest_framework.test import APITestCase

from .models import (
    AcademicYear, AdmissionSetting, AdmissionFee, Application, Staff, StaffSalary, User,
)
from .views import _mark_application_paid


class StaffSalaryTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='salary-manager', password='pw12345!', role='management'
        )
        self.staff_user = User.objects.create_user(
            username='salary-staff', password='pw12345!', first_name='Ada', last_name='Staff', role='staff'
        )
        self.staff = Staff.objects.create(
            user=self.staff_user,
            staff_id='ST-001',
            bank_name='Access Bank',
            account_number='0123456789',
        )
        self.year = AcademicYear.objects.create(
            name='2026-2027', start_date=date(2026, 9, 1), end_date=date(2027, 7, 31)
        )
        StaffSalary.objects.create(
            staff=self.staff,
            academic_year=self.year,
            month=8,
            amount=150000,
            paid_date=date(2026, 8, 25),
            voucher_number='AUG-001',
            account_name='Ada Staff',
            account_number='0123456789',
            bank_name='Access Bank',
        )
        self.client.force_authenticate(user=self.manager)

    def test_carry_forward_copies_salary_and_exposes_bank_details(self):
        response = self.client.post(
            '/api/staff-salaries/carry-forward/',
            {'academic_year': self.year.id, 'month': 8},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['created'], 1)
        copied = StaffSalary.objects.get(staff=self.staff, academic_year=self.year, month=9)
        self.assertEqual(copied.amount, 150000)
        self.assertEqual(copied.voucher_number, 'AUG-001')
        self.assertEqual(copied.account_name, 'Ada Staff')
        self.assertEqual(copied.account_number, '0123456789')
        self.assertEqual(copied.bank_name, 'Access Bank')

        staff_response = self.client.get(f'/api/staff/{self.staff.id}/')
        self.assertEqual(staff_response.status_code, 200)
        self.assertEqual(staff_response.json()['bank_name'], 'Access Bank')
        self.assertEqual(staff_response.json()['account_number'], '0123456789')


class AdmissionFlowTests(APITestCase):
    """
    Covers the applicant journey end to end. Applicants have no account, so
    every public call below is unauthenticated on purpose.
    """

    def setUp(self):
        self.year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_active=True,
        )
        self.setting = AdmissionSetting.objects.create(
            academic_year=self.year, is_open=True
        )
        AdmissionFee.objects.create(setting=self.setting, level=7, amount=15000)
        AdmissionFee.objects.create(setting=self.setting, level=-3, amount=5000)

    def start_application(self, **overrides):
        payload = {
            'first_name': 'Amina',
            'last_name': 'Bello',
            'date_of_birth': '2014-03-12',
            'contact_email': 'parent@example.com',
            'contact_phone': '08030000001',
            'level': 7,
        }
        payload.update(overrides)
        return self.client.post(
            '/api/admissions/start/', payload, content_type='application/json'
        )

    def complete_form(self, reference):
        return self.client.patch(
            f'/api/admissions/{reference}/save/',
            {
                'gender': 'female',
                'state_of_origin': 'Taraba',
                'lga': 'Jalingo',
                'home_address': '12 Hammaruwa Way',
                'guardian_name': 'Musa Bello',
                'guardian_relationship': 'Father',
                'guardian_phone': '08030000001',
                'guardian_address': '12 Hammaruwa Way',
            },
            content_type='application/json',
        )

    # --- public info ---

    def test_info_lists_only_levels_with_a_fee(self):
        response = self.client.get('/api/admissions/info/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['is_open'])
        labels = [level['label'] for level in body['levels']]
        self.assertEqual(labels, ['Pre-Nursery', 'JSS 1'])
        self.assertEqual(body['levels'][1]['fee'], 15000.0)

    def test_info_reports_closed_when_window_shut(self):
        self.setting.is_open = False
        self.setting.save()
        response = self.client.get('/api/admissions/info/')
        self.assertFalse(response.json()['is_open'])

    def test_closed_window_blocks_new_applications(self):
        self.setting.is_open = False
        self.setting.save()
        self.assertEqual(self.start_application().status_code, 400)

    def test_past_closing_date_blocks_new_applications(self):
        self.setting.closes_on = date(2020, 1, 1)
        self.setting.save()
        self.assertEqual(self.start_application().status_code, 400)

    # --- step 1 ---

    def test_start_creates_pending_application_with_reference(self):
        response = self.start_application()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['status'], 'pending_payment')
        self.assertEqual(body['fee_amount'], 15000.0)
        self.assertTrue(body['reference'].startswith('LAZ-'))
        self.assertNotIn('/', body['reference'])

    def test_start_rejects_level_without_a_fee(self):
        response = self.start_application(level=12)
        self.assertEqual(response.status_code, 400)

    def test_start_rejects_future_date_of_birth(self):
        response = self.start_application(date_of_birth='2999-01-01')
        self.assertEqual(response.status_code, 400)

    def test_references_are_unique(self):
        first = self.start_application().json()['reference']
        second = self.start_application(contact_phone='08030000002').json()['reference']
        self.assertNotEqual(first, second)

    # --- payment gating ---

    def test_form_cannot_be_saved_before_payment(self):
        reference = self.start_application().json()['reference']
        response = self.complete_form(reference)
        self.assertEqual(response.status_code, 402)

    def test_submit_blocked_before_payment(self):
        reference = self.start_application().json()['reference']
        response = self.client.post(f'/api/admissions/{reference}/submit/')
        self.assertEqual(response.status_code, 402)

    def test_marking_paid_is_idempotent(self):
        reference = self.start_application().json()['reference']
        application = Application.objects.get(reference=reference)

        _mark_application_paid(application, 'TX-1', 15000.0, reference)
        first_paid_at = application.paid_at

        _mark_application_paid(application, 'TX-2', 99999.0, reference)
        application.refresh_from_db()

        self.assertEqual(application.paid_at, first_paid_at)
        self.assertEqual(application.transaction_id, 'TX-1')
        self.assertEqual(float(application.amount_paid), 15000.0)

    # --- lookup ---

    def test_lookup_by_phone_and_dob(self):
        self.start_application()
        response = self.client.post(
            '/api/admissions/lookup/',
            {'identifier': '08030000001', 'date_of_birth': '2014-03-12'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        found = response.json()['applications'][0]
        self.assertFalse(found['is_paid'])
        self.assertFalse(found['can_print'])
        self.assertEqual(found['status_display'], 'Awaiting Payment')

    def test_lookup_by_email_and_dob(self):
        self.start_application()
        response = self.client.post(
            '/api/admissions/lookup/',
            {'identifier': 'parent@example.com', 'date_of_birth': '2014-03-12'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_lookup_requires_matching_date_of_birth(self):
        self.start_application()
        response = self.client.post(
            '/api/admissions/lookup/',
            {'identifier': '08030000001', 'date_of_birth': '2000-01-01'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_lookup_requires_both_fields(self):
        self.start_application()
        response = self.client.post(
            '/api/admissions/lookup/',
            {'identifier': '08030000001'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_siblings_sharing_a_phone_are_told_apart_by_dob(self):
        self.start_application(first_name='Amina', date_of_birth='2014-03-12')
        self.start_application(first_name='Yusuf', date_of_birth='2016-08-04')

        response = self.client.post(
            '/api/admissions/lookup/',
            {'identifier': '08030000001', 'date_of_birth': '2016-08-04'},
            content_type='application/json',
        )
        applications = response.json()['applications']
        self.assertEqual(len(applications), 1)
        self.assertEqual(applications[0]['full_name'], 'Yusuf Bello')

    # --- form completion and submission ---

    def test_submit_rejected_while_required_fields_missing(self):
        reference = self.start_application().json()['reference']
        application = Application.objects.get(reference=reference)
        _mark_application_paid(application, 'TX-1', 15000.0, reference)

        response = self.client.post(f'/api/admissions/{reference}/submit/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('guardian_name', response.json()['missing_fields'])

    def test_full_journey_from_payment_to_printable(self):
        reference = self.start_application().json()['reference']
        application = Application.objects.get(reference=reference)
        _mark_application_paid(application, 'TX-1', 15000.0, reference)
        application.refresh_from_db()
        self.assertEqual(application.status, 'paid')

        saved = self.complete_form(reference)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['missing_fields'], [])

        submitted = self.client.post(f'/api/admissions/{reference}/submit/')
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()['status'], 'submitted')

        lookup = self.client.post(
            '/api/admissions/lookup/',
            {'identifier': '08030000001', 'date_of_birth': '2014-03-12'},
            content_type='application/json',
        )
        self.assertTrue(lookup.json()['applications'][0]['can_print'])

    def test_submitted_form_cannot_be_edited(self):
        reference = self.start_application().json()['reference']
        application = Application.objects.get(reference=reference)
        _mark_application_paid(application, 'TX-1', 15000.0, reference)
        self.complete_form(reference)
        self.client.post(f'/api/admissions/{reference}/submit/')

        response = self.client.patch(
            f'/api/admissions/{reference}/save/',
            {'gender': 'male'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 409)

    def test_resubmitting_is_a_no_op(self):
        reference = self.start_application().json()['reference']
        application = Application.objects.get(reference=reference)
        _mark_application_paid(application, 'TX-1', 15000.0, reference)
        self.complete_form(reference)

        first = self.client.post(f'/api/admissions/{reference}/submit/')
        second = self.client.post(f'/api/admissions/{reference}/submit/')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['submitted_at'], second.json()['submitted_at'])

    def test_passport_photo_comes_back_as_an_absolute_url(self):
        """
        Without the request in serializer context DRF returns a bare
        /media/... path, which the frontend resolves against its own origin
        and fails to load. Also checks the file is genuinely served.
        """
        import io
        import shutil
        import tempfile
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        media_root = tempfile.mkdtemp()
        # Windows keeps the handle open behind FileResponse, so ignore_errors.
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        with override_settings(MEDIA_ROOT=media_root):
            self._assert_photo_round_trip()

    def _assert_photo_round_trip(self):
        import io
        from urllib.parse import urlparse
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        reference = self.start_application().json()['reference']
        application = Application.objects.get(reference=reference)
        _mark_application_paid(application, 'TX-1', 15000.0, reference)

        buffer = io.BytesIO()
        Image.new('RGB', (10, 10), 'blue').save(buffer, format='JPEG')
        buffer.seek(0)
        photo = SimpleUploadedFile('passport.jpg', buffer.read(), content_type='image/jpeg')

        upload = self.client.patch(
            f'/api/admissions/{reference}/save/',
            {'passport_photo': photo},
            format='multipart',
        )
        self.assertEqual(upload.status_code, 200, upload.content)

        detail = self.client.get(f'/api/admissions/{reference}/')
        url = detail.json()['passport_photo']
        self.assertTrue(url.startswith('http'), f'expected absolute URL, got {url!r}')
        self.assertIn('/media/admissions/photos/', url)

        # And the file is actually reachable at that URL, not just referenced.
        served = self.client.get(urlparse(url).path)
        self.assertEqual(served.status_code, 200)
        served.close()

    def test_fee_webhook_routes_admission_payments(self):
        """
        Flutterwave allows one webhook URL per account and the fee endpoint is
        the one registered, so admission payments must be handled there too.
        """
        from unittest.mock import patch

        reference = self.start_application().json()['reference']

        payload = {
            'event': 'charge.completed',
            'data': {
                'id': 55501,
                'tx_ref': reference,
                'status': 'successful',
                'currency': 'NGN',
                'amount': 15000,
            },
        }

        with patch(
            'core.views._verify_with_flutterwave',
            return_value={'amount': 15000, 'status': 'successful', 'currency': 'NGN'},
        ):
            response = self.client.post(
                '/api/payments/webhook/', payload, content_type='application/json',
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'recorded')

        application = Application.objects.get(reference=reference)
        self.assertIsNotNone(application.paid_at)
        self.assertEqual(application.status, 'paid')
        self.assertEqual(application.transaction_id, '55501')

    def test_fee_webhook_replay_does_not_double_record(self):
        from unittest.mock import patch

        reference = self.start_application().json()['reference']
        payload = {
            'event': 'charge.completed',
            'data': {
                'id': 55502, 'tx_ref': reference, 'status': 'successful',
                'currency': 'NGN', 'amount': 15000,
            },
        }

        with patch(
            'core.views._verify_with_flutterwave',
            return_value={'amount': 15000, 'status': 'successful', 'currency': 'NGN'},
        ):
            first = self.client.post(
                '/api/payments/webhook/', payload, content_type='application/json',
            )
            second = self.client.post(
                '/api/payments/webhook/', payload, content_type='application/json',
            )

        self.assertEqual(first.json()['status'], 'recorded')
        self.assertEqual(second.json()['status'], 'already_recorded')

    def test_unknown_reference_is_404(self):
        response = self.client.get('/api/admissions/LAZ-2026-NOPE99/')
        self.assertEqual(response.status_code, 404)


class AdmissionManagementTests(APITestCase):
    """Management review side — everything here requires authentication."""

    def setUp(self):
        self.year = AcademicYear.objects.create(
            name='2026-2027',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_active=True,
        )
        self.setting = AdmissionSetting.objects.create(
            academic_year=self.year, is_open=True
        )
        AdmissionFee.objects.create(setting=self.setting, level=7, amount=15000)

        self.manager = User.objects.create_user(
            username='manager', password='pw12345!', role='management'
        )
        self.parent = User.objects.create_user(
            username='someparent', password='pw12345!', role='parent'
        )

    def make_submitted_application(self):
        application = Application.objects.create(
            academic_year=self.year, level=7, fee_amount=15000,
            first_name='Amina', last_name='Bello',
            date_of_birth=date(2014, 3, 12),
            contact_phone='08030000001',
            gender='female', state_of_origin='Taraba', lga='Jalingo',
            home_address='12 Hammaruwa Way', guardian_name='Musa Bello',
            guardian_relationship='Father', guardian_phone='08030000001',
            guardian_address='12 Hammaruwa Way',
        )
        _mark_application_paid(application, 'TX-1', 15000.0, application.reference)
        self.client.post(f'/api/admissions/{application.reference}/submit/')
        application.refresh_from_db()
        return application

    def test_application_list_requires_authentication(self):
        response = self.client.get('/api/applications/')
        self.assertIn(response.status_code, (401, 403))

    def test_parents_cannot_read_applications(self):
        self.client.force_authenticate(user=self.parent)
        response = self.client.get('/api/applications/')
        self.assertEqual(response.status_code, 403)

    def test_management_can_list_applications(self):
        self.make_submitted_application()
        self.client.force_authenticate(user=self.manager)
        response = self.client.get('/api/applications/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        rows = body['results'] if isinstance(body, dict) else body
        self.assertEqual(len(rows), 1)

    def test_management_can_admit(self):
        application = self.make_submitted_application()
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f'/api/applications/{application.id}/decision/',
            {'decision': 'admitted', 'note': 'Strong entrance result'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        application.refresh_from_db()
        self.assertEqual(application.status, 'admitted')
        self.assertEqual(application.decided_by, self.manager)
        self.assertIsNotNone(application.decided_at)

    def test_decision_rejected_for_unsubmitted_application(self):
        application = Application.objects.create(
            academic_year=self.year, level=7, fee_amount=15000,
            first_name='Not', last_name='Done',
            date_of_birth=date(2014, 1, 1), contact_phone='08030000005',
        )
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            f'/api/applications/{application.id}/decision/',
            {'decision': 'admitted'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_decision_value_rejected(self):
        application = self.make_submitted_application()
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            f'/api/applications/{application.id}/decision/',
            {'decision': 'expelled'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_admitting_does_not_create_a_user_account(self):
        """The whole point of the design — an applicant never becomes a User."""
        application = self.make_submitted_application()
        before = User.objects.count()

        self.client.force_authenticate(user=self.manager)
        self.client.post(
            f'/api/applications/{application.id}/decision/',
            {'decision': 'admitted'},
            content_type='application/json',
        )

        self.assertEqual(User.objects.count(), before)

    def test_stats_counts_by_status(self):
        self.make_submitted_application()
        self.client.force_authenticate(user=self.manager)
        response = self.client.get('/api/applications/stats/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['by_status']['submitted'], 1)
        self.assertEqual(body['total_collected'], 15000.0)

    def test_search_filters_by_reference(self):
        application = self.make_submitted_application()
        self.client.force_authenticate(user=self.manager)
        response = self.client.get('/api/applications/', {'search': application.reference})
        body = response.json()
        rows = body['results'] if isinstance(body, dict) else body
        self.assertEqual(len(rows), 1)

        response = self.client.get('/api/applications/', {'search': 'LAZ-0000-ZZZZZZ'})
        body = response.json()
        rows = body['results'] if isinstance(body, dict) else body
        self.assertEqual(len(rows), 0)

    def test_fee_table_replacement(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.put(
            f'/api/admission-settings/{self.setting.id}/fees/',
            {'fees': [{'level': -3, 'amount': 6000}, {'level': 10, 'amount': 20000}]},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        levels = sorted(self.setting.fees.values_list('level', flat=True))
        self.assertEqual(levels, [-3, 10])

    def test_admin_pages_render(self):
        """Admin config passes system checks; make sure the pages actually load."""
        application = self.make_submitted_application()
        admin_user = User.objects.create_superuser(
            username='root', password='pw12345!', email='root@example.com',
        )
        self.client.force_login(admin_user)

        for url in (
            '/admin/core/application/',
            f'/admin/core/application/{application.id}/change/',
            '/admin/core/admissionsetting/',
            f'/admin/core/admissionsetting/{self.setting.id}/change/',
            '/admin/core/admissionfee/',
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_bulk_admit_skips_unsubmitted(self):
        from django.contrib.admin.sites import site
        from django.contrib.messages.storage.fallback import FallbackStorage

        submitted = self.make_submitted_application()
        draft = Application.objects.create(
            academic_year=self.year, level=7, fee_amount=15000,
            first_name='Not', last_name='Done',
            date_of_birth=date(2014, 1, 1), contact_phone='08030000007',
        )

        admin_user = User.objects.create_superuser(
            username='root2', password='pw12345!', email='root2@example.com',
        )
        request = self.client.request().wsgi_request
        request.user = admin_user
        request.session = self.client.session
        request._messages = FallbackStorage(request)

        model_admin = site._registry[Application]
        model_admin.mark_admitted(request, Application.objects.all())

        submitted.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(submitted.status, 'admitted')
        self.assertEqual(draft.status, 'pending_payment')
        self.assertEqual(submitted.decided_by, admin_user)

    def test_fee_table_rejects_unknown_level(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.put(
            f'/api/admission-settings/{self.setting.id}/fees/',
            {'fees': [{'level': 99, 'amount': 1000}]},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.setting.fees.exists(), 'existing fees should survive a bad request')
