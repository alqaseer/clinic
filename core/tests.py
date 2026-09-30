from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Speciality


class ConsultantSelectionSettingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="settings-test", password="test-only")
        self.speciality = Speciality.objects.create(name="Surgery")
        self.other = Speciality.objects.create(name="Cardiology")
        self.url = reverse("manage_specialities")

    def update(self, value):
        return self.client.post(self.url, {
            "update_consultant_selection": "true",
            "speciality_id": self.speciality.pk,
            "allow_consultant_selection": value,
        })

    def test_default_and_persisted_toggle_are_independent_per_speciality(self):
        self.assertFalse(self.speciality.allow_consultant_selection)
        self.client.force_login(self.user)
        for value, expected in [("true", True), ("true", True), ("false", False)]:
            self.assertRedirects(self.update(value), self.url)
            self.speciality.refresh_from_db()
            self.other.refresh_from_db()
            self.assertEqual(self.speciality.allow_consultant_selection, expected)
            self.assertFalse(self.other.allow_consultant_selection)
            response = self.client.get(self.url)
            self.assertContains(response, 'role="switch"')
            self.assertContains(response, 'aria-checked="%s"' % str(expected).lower())

    def test_anonymous_request_cannot_change_setting(self):
        self.assertEqual(self.update("true").status_code, 302)
        self.speciality.refresh_from_db()
        self.assertFalse(self.speciality.allow_consultant_selection)

    def test_invalid_setting_does_not_change_value(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.update("invalid"), self.url)
        self.speciality.refresh_from_db()
        self.assertFalse(self.speciality.allow_consultant_selection)


class ReferralBookingTests(TestCase):
    def setUp(self):
        from .models import Doctor, Workspace
        self.doctor = Doctor.objects.create(username="referrer", full_name="Referrer")
        self.speciality = Speciality.objects.create(name="Surgery", allow_consultant_selection=True)
        owner = get_user_model().objects.create_user(username="consultant-owner")
        self.workspace = Workspace.objects.create(name="Consultant clinic", owner_name="Dr Consultant", admin=owner,
            session_config={"Thursday": {"sessions": {"AM": {"max_total": 1, "max_new_referrals": 1}, "PM": {"max_total": 1, "max_new_referrals": 1}}}})
        self.speciality.workspaces.add(self.workspace)
        other_owner = get_user_model().objects.create_user(username="other-owner")
        self.other = Workspace.objects.create(name="Other clinic", admin=other_owner)
        session = self.client.session
        session['doctor_id'] = self.doctor.pk
        session.save()
        self.payload = {'patient_name': 'Test Patient', 'civil_id': '123456789012', 'phone_number': '12345678',
                        'diagnosis': 'Test diagnosis', 'speciality': self.speciality.pk, 'consultant': self.workspace.pk}

    def book(self, **updates):
        return self.client.post(reverse('book_appointment'), {**self.payload, **updates}, content_type='application/json')

    def test_consultant_is_required_and_must_belong_to_speciality(self):
        from .models import ClinicAppointment
        for value in [None, '', self.other.pk]:
            response = self.book(consultant=value)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json()['success'])
        self.assertFalse(ClinicAppointment.objects.exists())

    def test_normal_booking_is_restricted_to_selected_consultant(self):
        from unittest.mock import patch
        from datetime import date, time
        with patch('core.views.find_available_appointment', return_value=(self.workspace, date(2026, 10, 1), time(8))) as finder:
            response = self.book()
        self.assertTrue(response.json()['success'])
        self.assertEqual(finder.call_args.kwargs['selected_workspace'], self.workspace)
        self.assertEqual(response.json()['workspace_id'], self.workspace.pk)
        self.assertFalse(response.json()['is_urgent'])

    def test_disabled_selection_ignores_supplied_consultant(self):
        from unittest.mock import patch
        from datetime import date, time
        self.speciality.allow_consultant_selection = False
        self.speciality.save()
        with patch('core.views.find_available_appointment', return_value=(self.workspace, date(2026, 10, 1), time(8))) as finder:
            response = self.book(consultant=self.other.pk)
        self.assertTrue(response.json()['success'])
        self.assertIsNone(finder.call_args.kwargs['selected_workspace'])

    def test_urgent_books_full_session_and_persists_urgency(self):
        from unittest.mock import patch
        from datetime import datetime, date, time, timezone as tz
        from .models import ClinicAppointment
        for minutes in range(0, 271, 15):
            ClinicAppointment.objects.create(workspace=self.workspace, patient_name='Existing', civil_id='111111111111',
                phone_number='11111111', date=date(2026, 10, 1), time=time(8 + minutes // 60, minutes % 60),
                session='AM', appointment_type='New', system_referral=True)
        with patch('core.views.timezone.localtime', return_value=datetime(2026, 9, 30, 7, tzinfo=tz.utc)):
            response = self.book(is_urgent=True)
        self.assertTrue(response.json()['success'])
        appointment = ClinicAppointment.objects.get(pk=response.json()['appointment_id'])
        self.assertTrue(appointment.is_urgent)
        self.assertEqual(appointment.date, date(2026, 10, 1))
        self.assertEqual(appointment.time, time(8))
        self.assertEqual(appointment.workspace, self.workspace)

    def test_urgent_skips_locked_morning_and_never_books_afternoon(self):
        from unittest.mock import patch
        from datetime import datetime, date, timezone as tz
        from .models import ClinicAppointment, Lock
        Lock.objects.create(workspace=self.workspace, date=date(2026, 10, 1), pm=False)
        with patch('core.views.timezone.localtime', return_value=datetime(2026, 9, 30, 7, tzinfo=tz.utc)):
            response = self.book(is_urgent=True, am_only=True)
        appointment = ClinicAppointment.objects.get(pk=response.json()['appointment_id'])
        self.assertEqual(appointment.date, date(2026, 10, 8))
        self.assertEqual(appointment.session, 'AM')

    def test_urgent_can_book_today_but_never_a_past_slot(self):
        from unittest.mock import patch
        from datetime import datetime, date, time, timezone as tz
        from .models import ClinicAppointment
        self.workspace.session_config = {'Wednesday': {'sessions': {'AM': {'max_total': 0, 'max_new_referrals': 0}}}}
        self.workspace.save()
        with patch('core.views.timezone.localtime', return_value=datetime(2026, 9, 30, 10, 3, tzinfo=tz.utc)):
            response = self.book(is_urgent=True)
        appointment = ClinicAppointment.objects.get(pk=response.json()['appointment_id'])
        self.assertEqual(appointment.date, date(2026, 9, 30))
        self.assertEqual(appointment.time, time(10, 15))

    def test_urgent_returns_no_slot_for_unconfigured_clinic(self):
        from unittest.mock import patch
        from datetime import datetime, timezone as tz
        self.workspace.session_config = {}
        self.workspace.save()
        with patch('core.views.timezone.localtime', return_value=datetime(2026, 9, 30, 7, tzinfo=tz.utc)):
            response = self.book(is_urgent=True)
        self.assertFalse(response.json()['success'])

    def test_dashboard_includes_consultant_options(self):
        response = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Refer to Consultant')
        self.assertContains(response, 'Dr Consultant')
        self.assertContains(response, 'Urgent case: Next clinic immediately')

    def test_urgent_rejects_afternoon_only_clinic(self):
        from unittest.mock import patch
        from datetime import datetime, timezone as tz
        self.workspace.session_config = {'Thursday': {'sessions': {'PM': {'max_total': 20, 'max_new_referrals': 10}}}}
        self.workspace.save()
        with patch('core.views.timezone.localtime', return_value=datetime(2026, 9, 30, 7, tzinfo=tz.utc)):
            response = self.book(is_urgent=True, am_only=True)
        self.assertFalse(response.json()['success'])

    def test_urgent_allows_afternoon_when_am_preference_is_off(self):
        from unittest.mock import patch
        from datetime import datetime, date, timezone as tz
        from .models import ClinicAppointment, Lock
        Lock.objects.create(workspace=self.workspace, date=date(2026, 10, 1), pm=False)
        with patch('core.views.timezone.localtime', return_value=datetime(2026, 9, 30, 7, tzinfo=tz.utc)):
            response = self.book(is_urgent=True, am_only=False)
        appointment = ClinicAppointment.objects.get(pk=response.json()['appointment_id'])
        self.assertEqual(appointment.date, date(2026, 10, 1))
        self.assertEqual(appointment.session, 'PM')
