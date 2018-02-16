import simplejson, datetime
from freezegun import freeze_time
from decimal import Decimal
import mock, pytz

from django.test import TestCase, Client
from django.utils import timezone
from django.conf import settings

from django.db import transaction
from .models import Experiment, Checkin, User, JawboneMeasurement

import passwords

@mock.patch("app.jawbone.get_user_id", lambda x: "7890")
class ExperimentTestCase(TestCase):

    email = "bob@bob.johnson"

    def setUp(self):
        self.client = Client(HTTP_X_APPKEY=passwords.APP_KEY)
        token = simplejson.loads(self.client.post("/obtain_token/", {"email": self.email, "UUID": "1234"}).content)['token']
        self.client = Client(HTTP_X_APPKEY=passwords.APP_KEY, HTTP_AUTHORIZATION='Token ' + token)
        self.user = User.objects.get(email=self.email)

        self.freezer = freeze_time("2012-01-14 9:00:00")
        self.frozen_time = self.freezer.start()

    def tearDown(self):
        self.freezer.stop()

    def tick(self, days=1):
        self.frozen_time.tick(datetime.timedelta(days=days))

    def post(self, url, data={}, **kwargs):
        response = self.client.post(url, data, **kwargs)
        self.assertEqual(response.status_code, 200)
        return simplejson.loads(response.content)

    def get(self, url, data={}, **kwargs):
        response = self.client.get(url, data, **kwargs)
        self.assertEqual(response.status_code, 200)
        return simplejson.loads(response.content)

    def _create_experiment(self, **kwargs):
        post = dict(type="leisurehappiness",
                    self_efficacy=3,
                    app_efficacy=5,
                    experiment_efficacy=8)
        post.update(kwargs)
        response = self.post('/start_experiment/', post)
        self.assertEqual(response['success'], True)
        self.experiment_key = response["key"]

    def _get_experiment(self):
        return Experiment.objects.get(key=self.experiment_key)

    def _checkin(self, **kwargs):
        post = dict(experiment_key=self.experiment_key,
                    did_follow_instructions=3,
                    happy=4,
                    stress=5,
                    productivity=6,
                    leisure_time=120)
        post.update(kwargs)
        response = self.post('/experiment_checkin/', post)
        self.assertEqual(response['success'], True)
        return response['result']

    def _make_jawbone_sleep_event(self, start_offset=-8, end_offset=-2, awake_time=60):
        now = timezone.now()
        measurement = JawboneMeasurement(user=self.user,
                                         type="sleeps",
                                         start_time=now + datetime.timedelta(hours=start_offset),
                                         end_time=now + datetime.timedelta(hours=end_offset),
                                         jawbone_id="34",
                                         duration=(end_offset-start_offset) * 60,
                                         awake_time=awake_time
                                         )
        measurement.save()

    def _make_jawbone_steps_event(self, start_offset=0, end_offset=2, steps=1000):
        now = timezone.now()
        measurement = JawboneMeasurement(user=self.user,
                                         type="moves",
                                         start_time=now + datetime.timedelta(hours=start_offset),
                                         end_time=now + datetime.timedelta(hours=end_offset),
                                         jawbone_id="34",
                                         steps=steps
                                         )
        measurement.save()

    def test_set_user_data(self):
        response = self.post('/set_user_data/', dict(jawbone_access="1234",
                                                    jawbone_reset="5678",
                                                    date_of_birth="1985-01-13",
                                                    race="white",
                                                    gender="m",
                                                    happy=4,
                                                    stress=3,
                                                    activity="three",
                                                    sleep_quality=6,
                                                    timezone="America/New York"))
        self.assertEqual(response['success'], True)
        user = User.objects.get(email=self.email)
        self.assertEqual(user.jawbone_access_token, "1234")
        self.assertEqual(user.jawbone_reset_token, "5678")
        self.assertEqual(user.date_of_birth.strftime("%Y-%m-%d"), "1985-01-13")
        self.assertEqual(user.race, "white")
        self.assertEqual(user.gender, "m")
        self.assertEqual(user.happy, 4)
        self.assertEqual(user.stress, 3)
        self.assertEqual(user.activity, "three")
        self.assertEqual(user.sleep_quality, 6)
        self.assertEqual(user.timezone, "America/New York")
        self.assertEqual(user.jawbone_user_id, "7890")

    def test_start_experiment(self):
        response = self.post('/start_experiment/', dict(type="leisurehappiness",
                                                        self_efficacy=3,
                                                        app_efficacy=5,
                                                        experiment_efficacy=8))
        self.assertEqual(response['success'], True)
        key = response["key"]
        experiment = Experiment.objects.get(key=key)
        self.assertEqual(experiment.experiment_type, "leisurehappiness")
        self.assertEqual(experiment.self_efficacy, 3)
        self.assertEqual(experiment.app_efficacy, 5)
        self.assertEqual(experiment.experiment_efficacy, 8)
        self.assertEqual(experiment.user.email, self.email)

    def test_checkin(self):
        self._create_experiment()

        self.tick()
        response = self._checkin(leisure_time=120)
        self.assertEqual(response['current_stage'], 0)
        self.assertEqual(response['stage_inputs'], [120])

        self.tick()
        response = self._checkin(leisure_time=60)
        self.assertEqual(response['stage_inputs'], [120, 60])

    def test_refresh_instructions(self):
        self._create_experiment()

        self.tick()
        response = self._checkin(leisure_time=120)
        self.assertEqual(response['current_stage'], 0)
        self.assertEqual(response['stage_inputs'], [120])

        refresh_response = self.get("/refresh_instructions/", dict(experiment_key=self.experiment_key))
        refresh_result = refresh_response['result']
        self.assertEqual(response['current_stage'], refresh_result["current_stage"])
        self.assertEqual(response['stage_inputs'], refresh_result["stage_inputs"])
        self.assertEqual(response['target'], refresh_result["target"])
        self.assertEqual(response['stage_outputs'], refresh_result["stage_outputs"])


    def test_complete_initial_stage(self):
        self._create_experiment()

        self.tick()
        self._checkin(leisure_time=120)

        self.tick()
        self._checkin(leisure_time=60)

        self.tick()
        response = self._checkin(leisure_time=220)
        self.assertEqual(response['stage_inputs'], [120, 60, 220])

        self.tick()
        self._checkin(leisure_time=50)

        self.tick()
        self._checkin(leisure_time=70)

        self.tick()
        response = self._checkin(leisure_time=70)
        self.assertEqual(response['stage_inputs'], [120, 60, 220, 50, 70, 70])
        self.assertEqual(response['current_stage'], 0)

        self.tick()
        response = self._checkin(leisure_time=40)
        self.assertEqual(response['stage_inputs'], [])
        self.assertEqual(response['current_stage'], 1)

        self.tick()
        response = self._checkin(leisure_time=47)
        self.assertEqual(response['stage_inputs'], [47])
        self.assertEqual(response['current_stage'], 1)

    def test_succeed_stage_early(self):
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=120)
        self.assertEqual(response['stage_inputs'], [])
        self.assertEqual(response['current_stage'], 1)
        self.assertEqual(response['target'], 90)

        self.tick()
        self._checkin(leisure_time=100)

        self.tick()
        self._checkin(leisure_time=80)

        self.tick()
        self._checkin(leisure_time=83)

        self.tick()
        self._checkin(leisure_time=95)

        self.tick()
        response = self._checkin(leisure_time=90)
        self.assertEqual(response['stage_inputs'], [])
        self.assertEqual(response['current_stage'], 2)


    def test_barely_succeed_stage(self):
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=120)
        self.assertEqual(response['stage_inputs'], [])
        self.assertEqual(response['current_stage'], 1)
        self.assertEqual(response['target'], 90)

        self.tick()
        self._checkin(leisure_time=100)

        self.tick()
        self._checkin(leisure_time=80)

        self.tick()
        self._checkin(leisure_time=130)

        self.tick()
        self._checkin(leisure_time=130)

        self.tick()

        self.tick()
        self._checkin(leisure_time=95)

        self.tick()
        response = self._checkin(leisure_time=90)
        self.assertEqual(response['stage_inputs'], [])
        self.assertEqual(response['current_stage'], 2)

    def test_complete_fail_stage(self):
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=120)
        self.assertEqual(response['stage_inputs'], [])
        self.assertEqual(response['current_stage'], 1)
        self.assertEqual(response['target'], 90)

        self.tick()
        self._checkin(leisure_time=100)

        self.tick()
        self._checkin(leisure_time=80)

        self.tick()
        self._checkin(leisure_time=130)

        self.tick()

        self.tick()

        self.tick()
        response = self._checkin(leisure_time=95)
        self.assertEqual(response['restarted_stage'], True)

    def test_leisure_experiment(self):
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=30)
        self.assertEqual(response['current_stage'], 1)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=90, happy=6)
        self.assertEqual(response['current_stage'], 2)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=30)
        self.assertEqual(response['current_stage'], 3)

        self.assertEqual(response.get('result_value'), None)
        self.assertEqual(response.get('is_complete'), None)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=60)
        self.assertEqual(response['current_stage'], 4)

        self.assertEqual(response['result_value'], 90)
        self.assertEqual(response['result_confidence'], .9)
        self.assertEqual(response['is_complete'], True)

    def test_confidence_levels(self):
        # test 80% overlap
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=30)
        self.assertEqual(response['current_stage'], 1)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=90, happy=6)
        self.assertEqual(response['current_stage'], 2)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=30, happy=min(4+i, 6))
        self.assertEqual(response['current_stage'], 3)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=60, happy=min(5+i, 6))
        self.assertEqual(response['current_stage'], 4)

        self.assertEqual(response['result_value'], 90)
        self.assertEqual(response['result_confidence'], .2)
        self.assertEqual(response['is_complete'], True)

        # repeat for a 60% overlap, to make sure multiple overlap values work
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=30)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=90, happy=6)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=30, happy=min(4+i, 6))

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=60, happy=min(2+i, 6))

        self.assertEqual(response['result_value'], 90)
        self.assertEqual(response['result_confidence'], .4)
        self.assertEqual(response['is_complete'], True)

        # full overlap!
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=30)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=90, happy=7)

        for i in xrange(5):
            self.tick()
            response = self._checkin(leisure_time=30, happy=7)

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=60, happy=3+i)

        self.assertEqual(response['result_value'], 90)
        self.assertEqual(response['result_confidence'], 0)
        self.assertEqual(response['is_complete'], True)

    def test_cancel_experiment(self):
        self._create_experiment()

        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=120)
        self.assertEqual(response['stage_inputs'], [])
        self.assertEqual(response['current_stage'], 1)
        self.assertEqual(response['target'], 90)

        reason = "NO MORE"

        response = self.post('/cancel_experiment/', dict(experiment_key=self.experiment_key, reason=reason))
        self.assertEqual(response['success'], True)
        self.assertEqual(response['experiments'][0]['is_cancelled'], True)
        self.assertEqual(response['experiments'][0]['key'], self.experiment_key)
        experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(experiment.end_time, timezone.now())
        self.assertEqual(experiment.is_cancelled, True)
        self.assertEqual(experiment.cancel_reason, reason)

    def test_stage_targets(self):

        # under -> under, N1, N3, N2
        self._create_experiment()
        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=10)
        self.assertEqual(response['target'], 30)
        experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(experiment.get_stage_targets(), [15, 30, 90, 60])

        # N1 -> N1, N3, N1, N2
        self._create_experiment()
        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=40)
        self.assertEqual(response['target'], 90)
        experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(experiment.get_stage_targets(), [30, 90, 30, 60])

        # N2 -> N2, N3, N1, N2
        self._create_experiment()
        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=50)
        self.assertEqual(response['target'], 90)
        experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(experiment.get_stage_targets(), [60, 90, 30, 60])

        # N3 -> N3, N1, N3, N2
        self._create_experiment()
        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=95)
        self.assertEqual(response['target'], 30)
        experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(experiment.get_stage_targets(), [90, 30, 90, 60])

        # over -> over, N3, N1, N2
        self._create_experiment()
        for i in xrange(7):
            self.tick()
            response = self._checkin(leisure_time=120)
        self.assertEqual(response['target'], 90)
        experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(experiment.get_stage_targets(), [105, 90, 30, 60])

    def test_get_experiments(self):
        self._create_experiment()
        response = self.get('/get_experiments/')
        self.assertEqual(len(response['experiments']), 1)
        self.assertEqual(response['experiments'][0]['key'], self.experiment_key)

        self._create_experiment()
        response = self.get('/get_experiments/')
        self.assertEqual(len(response['experiments']), 2)
        self.assertEqual(response['experiments'][1]['key'], self.experiment_key)

    def test_sleep_duration_experiment(self):
        self._create_experiment(type="sleepdurationproductivity")

        for i in xrange(7):
            self._make_jawbone_sleep_event()
            self.tick()
            response = self._checkin()
        self.assertEqual(response['current_stage'], 1)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-5, end_offset=2)
            self.tick()
            response = self._checkin(productivity=7)
        self.assertEqual(response['current_stage'], 2)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-7, end_offset=2)
            self.tick()
            response = self._checkin()
        self.assertEqual(response['current_stage'], 3)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-6, end_offset=2)
            self.tick()
            response = self._checkin()
        self.assertEqual(response['current_stage'], 4)

        self.assertEqual(response['result_value'], 6.5 * 60)
        self.assertEqual(response['result_confidence'], .9)
        self.assertEqual(response['is_complete'], True)

    def test_sleep_variability_experiment(self):
        self._create_experiment(type="sleepvariabilitystress")

        self.tick()
        for i in xrange(7):
            self._make_jawbone_sleep_event(start_offset=-15 + 30.0/60*(-1)**i)
            response = self._checkin()
            self.tick()
        self.assertEqual(response['current_stage'], 1)

        experiment = Experiment.objects.get(key=self.experiment_key)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-15 + 90.0/60*(-1)**i)
            self._make_jawbone_sleep_event(start_offset=-13 + 90.0/60*(-1)**i)
            response = self._checkin(productivity=7)
            self.tick()
        self.assertEqual(response['current_stage'], 2)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-15 + 30.0/60*(-1)**i)
            response = self._checkin(stress=0)
            self.tick()
        self.assertEqual(response['current_stage'], 3)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-15 + 60.0/60*(-1)**i)
            response = self._checkin()
            self.tick()
        self.assertEqual(response['current_stage'], 4)

        self.assertEqual(response['result_value'], 30)
        self.assertEqual(response['result_confidence'], .9)
        self.assertEqual(response['is_complete'], True)

    def test_sleep_variability_experiment_miss_day(self):
        self._create_experiment(type="sleepvariabilitystress")

        self.tick()
        for i in xrange(7):
            self._make_jawbone_sleep_event(start_offset=-15 + 30.0/60*(-1)**i)
            response = self._checkin()
            self.tick()
        self.assertEqual(response['current_stage'], 1)

        experiment = Experiment.objects.get(key=self.experiment_key)

        for i in xrange(6):
            if i != 3:
                self._make_jawbone_sleep_event(start_offset=-15 + 90.0/60*(-1)**i)
                self._make_jawbone_sleep_event(start_offset=-13 + 90.0/60*(-1)**i)
            response = self._checkin(productivity=7)
            self.tick()
        self.assertEqual(response['current_stage'], 2)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-15 + 30.0/60*(-1)**i)
            response = self._checkin(stress=0)
            self.tick()
        self.assertEqual(response['current_stage'], 3)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-15 + 60.0/60*(-1)**i)
            response = self._checkin()
            self.tick()
        self.assertEqual(response['current_stage'], 4)

        self.assertEqual(response['result_value'], 30)
        self.assertEqual(response['result_confidence'], .9)
        self.assertEqual(response['is_complete'], True)

    def test_sleep_variability_experiment_midnight(self):
        self._create_experiment(type="sleepvariabilitystress")

        for i in xrange(7):
            self._make_jawbone_sleep_event(start_offset=-5 + 30.0/60*(-1)**i)
            self.tick()
            response = self._checkin()
        self.assertEqual(response['current_stage'], 1)

        experiment = Experiment.objects.get(key=self.experiment_key)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-5 + 90.0/60*(-1)**i)
            self.tick()
            response = self._checkin(productivity=7)
        self.assertEqual(response['current_stage'], 2)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-5 + 30.0/60*(-1)**i)
            self.tick()
            response = self._checkin(stress=0)
        self.assertEqual(response['current_stage'], 3)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-5 + 60.0/60*(-1)**i)
            self.tick()
            response = self._checkin()
        self.assertEqual(response['current_stage'], 4)

        self.assertEqual(response['result_value'], 30)
        self.assertEqual(response['result_confidence'], .9)
        self.assertEqual(response['is_complete'], True)

    def test_sleep_variability_initial_averages(self):

        for hour_offset in range(0, 24):

            if hour_offset == 9:
                continue  # things get weird when you start at 6:30 and 7:30

            JawboneMeasurement.objects.all().delete()
            self.tick(days=-8)
            self._create_experiment(type="sleepvariabilitystress")

            minute_offset = 1 if hour_offset < 9 else -1

            for i in xrange(8):
                self._make_jawbone_sleep_event(start_offset=-1*hour_offset + 30.0/60*(-1)**i * minute_offset)
                response = self._checkin()
                self.tick()

            self.assertEqual(response['current_stage'], 1)
            experiment = Experiment.objects.get(key=self.experiment_key)

            self.assertEqual(experiment.initial_stage_average % (24 * 60), ((9 - 5 - hour_offset) % 24) * 60 + 30/7) # last bit is because there are 7 input days so the average will be a little different

    def test_steps_experiment(self):
        self._create_experiment(type="stepssleepefficiency")

        for i in xrange(7):
            self._make_jawbone_sleep_event(awake_time=100)
            self._make_jawbone_steps_event(steps=10000)
            self.tick()
            response = self._checkin()
            experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(response['current_stage'], 1)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-6, end_offset=-2, awake_time=60)
            self._make_jawbone_steps_event(steps=13000)
            self.tick()
            response = self._checkin(productivity=7)
            experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(response['current_stage'], 2)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-6, end_offset=-2, awake_time=120)
            self._make_jawbone_steps_event(steps=7500)
            self.tick()
            response = self._checkin()
            experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(response['current_stage'], 3)

        for i in xrange(5):
            self._make_jawbone_sleep_event(start_offset=-6, end_offset=-2, awake_time=1)
            self._make_jawbone_steps_event(steps=12000)
            self.tick()
            response = self._checkin()
            experiment = Experiment.objects.get(key=self.experiment_key)
        self.assertEqual(response['current_stage'], 4)

        self.assertEqual(response['result_value'], 11000)
        self.assertEqual(response['result_confidence'], .9)
        self.assertEqual(response['is_complete'], True)

    def test_jawbone_sleep_durations(self):
        # test if durations are what we expect
        self._create_experiment(type="sleepdurationproductivity")
        self._make_jawbone_sleep_event()
        now = timezone.now()
        experiment = Experiment.objects.get(key=self.experiment_key)

        start_date = (now - datetime.timedelta(days=1)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        durations = experiment.get_experiment_type()._get_jawbone_duration_event(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(durations, [0, 360])

        start_date = now.date()
        end_date = (now + datetime.timedelta(days=1)).date()
        durations = experiment.get_experiment_type()._get_jawbone_duration_event(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(durations, [360])

        start_date = (now - datetime.timedelta(days=1)).date()
        end_date = now.date()
        durations = experiment.get_experiment_type()._get_jawbone_duration_event(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(durations, [0])

        self._make_jawbone_sleep_event(start_offset=-36, end_offset=-24)
        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        durations = experiment.get_experiment_type()._get_jawbone_duration_event(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(durations, [0, 0, 180, 540, 360])

        self._make_jawbone_sleep_event(start_offset=-20, end_offset=-10) 
        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        durations = experiment.get_experiment_type()._get_jawbone_duration_event(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(durations, [0, 0, 180, 540+60*10, 360])

    def test_jawbone_sleep_efficiencies(self):
        self._create_experiment(type="stepssleepefficiency")
        self._make_jawbone_sleep_event(awake_time=1*60)  # 1 hr awake
        now = timezone.now()
        experiment = Experiment.objects.get(key=self.experiment_key)

        start_date = (now - datetime.timedelta(days=1)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        efficiencies = experiment.get_experiment_type()._get_jawbone_sleep_efficiencies(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(efficiencies, [None, 5.0/6])

        start_date = now.date()
        end_date = (now + datetime.timedelta(days=1)).date()
        efficiencies = experiment.get_experiment_type()._get_jawbone_sleep_efficiencies(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(efficiencies, [5.0/6])

        start_date = (now - datetime.timedelta(days=1)).date()
        end_date = now.date()
        efficiencies = experiment.get_experiment_type()._get_jawbone_sleep_efficiencies(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(efficiencies, [None])

        self._make_jawbone_sleep_event(start_offset=-36, end_offset=-24, awake_time=3*60)  #3 hrs awake, 12 hrs in bed
        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        efficiencies = experiment.get_experiment_type()._get_jawbone_sleep_efficiencies(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(efficiencies, [None, None, 9.0/12, None, 5.0/6.0])

        self._make_jawbone_sleep_event(start_offset=-20, end_offset=-10, awake_time=1*60)   #1 hrs awake, 10 hrs in bed
        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        efficiencies = experiment.get_experiment_type()._get_jawbone_sleep_efficiencies(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        self.assertEqual(efficiencies, [None, None, 9.0/12, 9.0/10, 5.0/6.0])

    def test_jawbone_sleep_start(self):
        self._create_experiment(type="sleepvariabilitystress")
        self._make_jawbone_sleep_event() # Start Time 1am
        now = timezone.now()
        experiment = Experiment.objects.get(key=self.experiment_key)

        start_date = (now - datetime.timedelta(days=1)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        sleep_times = experiment.get_experiment_type()._get_jawbone_activity_start(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        sleep_times = [s.hour * 60 + s.minute if s is not None else None for s in sleep_times ]
        self.assertEqual(sleep_times, [None, 60])

        self._make_jawbone_sleep_event(start_offset=-36, end_offset=-24) # Start time 9pm
        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        sleep_times = experiment.get_experiment_type()._get_jawbone_activity_start(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        sleep_times = [s.hour * 60 + s.minute if s is not None else None for s in sleep_times ]
        self.assertEqual(sleep_times, [None, None, 1260, None, 60])

        self._make_jawbone_sleep_event(start_offset=-20, end_offset=-10) # Start time 1 pm
        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        sleep_times = experiment.get_experiment_type()._get_jawbone_activity_start(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        sleep_times = [s.hour * 60 + s.minute if s is not None else None for s in sleep_times ]
        self.assertEqual(sleep_times, [None, None, 1260, 780, 60])
        

        self._make_jawbone_sleep_event(start_offset=-9.5, end_offset=-9) # (Nap) Start time 11:30 pm
        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        sleep_times = experiment.get_experiment_type()._get_jawbone_activity_start(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))
        sleep_times = [s.hour * 60 + s.minute if s is not None else None for s in sleep_times ]
        self.assertEqual(sleep_times, [None, None, 1260, 780, 60])

    def test_jawbone_activity_steps(self):
        self._create_experiment(type="stepssleepefficiency")
        now = timezone.now()
        experiment = Experiment.objects.get(key=self.experiment_key)
        
        self._make_jawbone_steps_event()

        start_date = (now - datetime.timedelta(days=1)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        steps = experiment.get_experiment_type()._get_jawbone_activity_steps(experiment, start_date, end_date)
        self.assertEqual(steps, [0, 1000])

        self._make_jawbone_steps_event(start_offset=-36,end_offset=-24,steps=20000)

        start_date = (now - datetime.timedelta(days=4)).date()
        end_date = (now + datetime.timedelta(days=1)).date()
        steps = experiment.get_experiment_type()._get_jawbone_activity_steps(experiment, start_date, end_date)
        self.assertEqual(steps, [0,0,20000,0, 1000])

    def test_realistic_experiment(self):
        self._create_experiment()
        experiment = Experiment.objects.get(key=self.experiment_key)

        happiness = [5,2,4,5,6,6,6, # avg: 4.86 
                        7,None,6,5,5,5,6, # 5.6 (best week, min 5)
                        5,4,5,6,None,5, # 5.0 (4/5 above min)
                        6,5,4,5,4] # 4.8 (3/5 above min)
        leisure = [10,50,0,10,40,20,10, # Stage 0
                    90,None,90,80,45,104,90, # Stage 1
                    20,20,40,20,None,20, # Stage 2
                    60,45,60,75,60] # Stage 3
        for i in xrange(6):
            self.tick()
            response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response['current_stage'], 0)

        self.tick()
        response = self._checkin(leisure_time=leisure[6],happy=happiness[6])
        self.assertEqual(response['current_stage'], 1)
        self.assertEqual(response['target'], 90)

        for i in xrange(7,14):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],2)

        for i in xrange(14,20):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],3)

        for i in xrange(20,25):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],4)

        self.assertEqual(response["is_complete"], True)
        self.assertEqual(response['result_value'],90)
        self.assertEqual(response['result_confidence'],.2)

    def todo_test_realistic_experiment_with_redo_stages(self):
        self._create_experiment()
        experiment = Experiment.objects.get(key=self.experiment_key)

        happiness = [5,2,4,5,6,6,6, # avg: 4.86
                        7,6,6,6, 
                        7,None,6,5,5,5,6, # 5.6 (best week, min 5)
                        5,4,5,6,None,5, # 5.0 (4/5 above min)
                        5,None,4,5,None,
                        6,5,4,5,4] # 4.8 (3/5 above min)
        leisure = [10,50,0,10,40,20,10, # Stage 0
                    300,120,240,120, # Attempted Stage 1
                    90,None,90,80,45,104,90, # Re-do Stage 1
                    20,20,40,20,None,20, # Stage 2
                    60,None,45,45,None, # Attempted Stage 3
                    60,45,60,75,60] # Re-do Stage 3
        
        # Stage 0
        for i in xrange(6):
            self.tick()
            response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response['current_stage'], 0)

        self.tick()
        response = self._checkin(leisure_time=leisure[6],happy=happiness[6])
        self.assertEqual(response['current_stage'], 1)
        self.assertEqual(response['target'], 90)

        # Attempt Stage 1
        for i in xrange(7,11):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],1)
        # TODO: Somehow restart the stage

        # Redo Stage 1
        for i in xrange(11,18):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],2)

        # Stage 2
        for i in xrange(18,24):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],3)

        # Attempt Stage 3
        for i in xrange(24,29):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],3)
        # TODO: Somehow restart the stage

        # Redo Stage 3
        for i in xrange(29,34):
            self.tick()
            if leisure[i] is not None:
                response = self._checkin(leisure_time=leisure[i],happy=happiness[i])
        self.assertEqual(response["current_stage"],4)

        self.assertEqual(response["is_complete"], True)
        self.assertEqual(response['result_value'],90)
        self.assertEqual(response['result_confidence'],.2) 

    def todo_test_realistic_experiment_sleepduration_productivity(self):
        self._create_experiment(type="sleepdurationproductivity")
        experiment = Experiment.objects.get(key=self.experiment_key)

        productivity = [5,3,2,4,3,5,6, # Stage 0 (7.4 hrs sleep) --> N2,N3,N1,N2
                            4,4,4,4,None,3,5, # Stage 1 
                            5,6,4,5,4,
                            5,3,3,None,3,4,None,5,5,None,6,3,4] 
        
        steps = [9658,621,2852,6692,4375,4998,14973,9320,4965,18741,4380,1546,4906,8625,8327,8286,7338,7303,8083,10538,8124,3536,3152,5218,5174,7072,5577,6742,12471,4007,4469,4246]
        
        bedtime = [5720,2070,-6089,-4426,1423,-5400,-3920,
                    -5435,-4037,-6043,-7200,-11875,None,-3000,
                    -9045,624,-4001,-10679,-9494,-11833,-6591,-8613,-1800,-5915,-11710,-9000,-11565,-4827,-8218,-5400,-4500,-10943]
        waketime = [28200,31500,28800,27000,28800,22200,18000,
                    25800,27300,26400,24600,24000,None,25200,
                    22800,28200,27600,19500,21000,20100,21300,27900,27900,27300,22500,24900,19800,19800,19800,21600,20100,20400]
        awake_duration = [702,691,2310,2208,740,1200,738,
                            1474,678,1125,2880,776,None,1620,
                            1683,743,1673,1619,1819,3127,1916,5988,0,284,977,1800,1880,1164,727,0,0,264]  

        # Stage 0
        for i in xrange(7):
            self.tick()
            if bedtime[i] is not None:
                self._make_jawbone_sleep_event(start_offset=-9+bedtime[i]/3600., end_offset=-9+waketime[i]/3600., awake_time=awake_duration[i])
            response = self._checkin(productivity=productivity[i])
        self.assertEqual(response['current_stage'],1)
        self.assertEqual(response['target'],510)

        for i in xrange(7,14):
            self.tick()
            if bedtime[i] is not None:
                s = -9+bedtime[i]/3600.
                e = -9+waketime[i]/3600.
                self._make_jawbone_sleep_event(start_offset=s, end_offset=e, awake_time=awake_duration[i])
            if productivity[i] is not None:
                response = self._checkin(productivity=productivity[i])
                print response
        self.assertEqual(response['current_stage'],2)
        self.assertEqual(response['target'],390)

        print response



