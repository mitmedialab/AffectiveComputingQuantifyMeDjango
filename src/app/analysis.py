import simplejson, datetime, pytz
from abc import ABCMeta, abstractmethod, abstractproperty


EXPERIMENT_TYPES = {}

def experiment_type(cls):
    EXPERIMENT_TYPES[cls.get_name()] = cls
    return cls

def mean(l):
    l = [i for i in l if i is not None]
    if not l:
        return 0
    return float(sum(l)) / len(l)


class ExperimentType(object):
    __metaclass__ = ABCMeta

    def __init__(self, name):
        self.name = name

    @staticmethod
    @abstractproperty
    def get_name(): pass

    @staticmethod
    @abstractmethod
    def get_inputs(experiment, start_date, end_date, use_variability):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :param use_variability: whether to analyze the variability around the first stage's average
        :return: list of floats that are the input values, one per day
        '''
        pass

    @staticmethod
    @abstractmethod
    def get_outputs(experiment, start_date, end_date):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :return: list of floats that are the output values, one per day
        '''
        pass


    @staticmethod
    @abstractmethod
    def get_ranges():
        pass

    @staticmethod
    @abstractmethod
    def get_range_size():
        pass

    @staticmethod
    @abstractmethod
    def get_stable_range():
        pass

    @staticmethod
    def use_variability():
        return False

    @staticmethod
    def should_minimize_result():
        return False

    @staticmethod
    def calculate_input_average(initial_stage_inputs):
        return mean(initial_stage_inputs)

    @staticmethod
    def _get_checkins_value(experiment, start_date, end_date, attr):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :param attr:
        :return:
        '''
        checkins = sorted(experiment.checkins.all(), key=lambda c: c.checkin_time)
        results = []
        date = start_date
        while date < end_date:
            found = False
            for checkin in checkins:
                # we ask about yesterday's stuff, so we want the checkin for the day after we're interested in
                if experiment.localize(checkin.checkin_time).date() == date + datetime.timedelta(days=1):
                    results.append(getattr(checkin, attr))
                    found = True
                    break
            if not found:
                results.append(None)
            date += datetime.timedelta(days=1)

        return results

    @staticmethod
    def _get_jawbone_duration_event(experiment, start_date, end_date, typename, offset=datetime.timedelta(days=0)):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :param typename:
        :param offset:
        :return:
        '''
        events = experiment.get_jawbone_events(typename, (start_date + offset), (end_date - offset))
        tz = pytz.timezone(experiment.user.timezone)
        day = start_date
        durations = []
        while day < end_date:
            day_start = tz.localize(datetime.datetime.combine(day, datetime.datetime.min.time())) + offset
            day_end = day_start + datetime.timedelta(days=1)
            duration = 0
            for event in events:
                if event.end_time >= day_start and event.start_time <= day_end:
                    start = max(day_start, event.start_time)
                    end = min(day_end, event.end_time)
                    duration += round((end - start).seconds / 60.0)
            durations.append(duration)
            day += datetime.timedelta(days=1)
        return durations

    @staticmethod
    def _get_jawbone_sleep_efficiencies(experiment, start_date, end_date, typename, offset=datetime.timedelta(days=0)):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :param typename:
        :param offset:
        :return:
        '''
        events = experiment.get_jawbone_events(typename, start_date + offset, end_date - offset)
        tz = pytz.timezone(experiment.user.timezone)
        day = start_date
        durations = []
        while day < end_date:
            day_start = tz.localize(datetime.datetime.combine(day, datetime.datetime.min.time())) + offset
            day_end = day_start + datetime.timedelta(days=1)
            duration = 0.0
            awake_time = 0.0
            for event in events:
                if day_start < event.start_time <= day_end:
                    duration += round((event.end_time - event.start_time).total_seconds() / 60.0)
                    awake_time += event.awake_time
            durations.append((1.0 - (float(awake_time) / duration)) if duration else None)
            day += datetime.timedelta(days=1)
        return durations

    @staticmethod
    def _get_jawbone_activity_start(experiment, start_date, end_date, typename, offset=datetime.timedelta(days=0)):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :param typename:
        :param offset:
        :return:
        '''
        events = experiment.get_jawbone_events(typename, start_date + offset, end_date - offset)
        tz = pytz.timezone(experiment.user.timezone)
        day = start_date
        starts = []
        while day < end_date:
            day_start = tz.localize(datetime.datetime.combine(day, datetime.datetime.min.time())) + offset
            day_end = day_start + datetime.timedelta(days=1)
            start_time = None
            for event in events:
                if day_start <= event.start_time < day_end:
                    start_time = event.start_time
                    break
            starts.append(start_time)
            day += datetime.timedelta(days=1)
        return starts

    @staticmethod
    def _get_jawbone_activity_duration(experiment, start_date, end_date):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :return:
        '''
        events = experiment.get_jawbone_events("moves", start_date, end_date)
        date = start_date
        durations = []
        while date < end_date:
            duration = 0
            for event in events:
                if date == experiment.localize(event.start_time).date():
                    duration = event.duration
                    break
            durations.append(duration)
            date += datetime.timedelta(days=1)
        return durations


    @staticmethod
    def _get_jawbone_activity_steps(experiment, start_date, end_date):
        '''
        :param experiment:
        :param start_date: inclusive
        :param end_date: exclusive
        :return:
        '''
        events = experiment.get_jawbone_events("moves", start_date, end_date)
        date = start_date
        totals = []
        while date < end_date:
            total = 0
            for event in events:
                if date == experiment.localize(event.start_time).date():
                    total = event.steps
                    break
            totals.append(total)
            date += datetime.timedelta(days=1)
        return totals


@experiment_type
class StepsSleepEfficiency(ExperimentType):

    @staticmethod
    def get_name():
        return "stepssleepefficiency"

    @staticmethod
    def get_inputs(experiment, start_date, end_date, use_variability):
        return ExperimentType._get_jawbone_activity_steps(experiment, start_date, end_date)

    @staticmethod
    def get_outputs(experiment, start_date, end_date):
        return ExperimentType._get_jawbone_sleep_efficiencies(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))

    @staticmethod
    def get_ranges():
        return dict(under=6500,
                    N1=8000,
                    N2=11000,
                    N3=14000,
                    over=15500)

    @staticmethod
    def get_range_size():
        return 1500

    @staticmethod
    def get_stable_range():
        return .1  # TODO: Not a final value


@experiment_type
class SleepDurationProductivity(ExperimentType):

    @staticmethod
    def get_name():
        return "sleepdurationproductivity"

    @staticmethod
    def get_inputs(experiment, start_date, end_date, use_variability):
        # offset is because we ask about 9pm to 9pm for the given day
        return ExperimentType._get_jawbone_duration_event(experiment, start_date, end_date, "sleeps", offset=datetime.timedelta(hours=-5))

    @staticmethod
    def get_outputs(experiment, start_date, end_date):
        return ExperimentType._get_checkins_value(experiment, start_date, end_date, "productivity")

    @staticmethod
    def get_ranges():
        return dict(under=6 * 60,
                    N1=6.5 * 60,
                    N2=7.5 * 60,
                    N3=8.5 * 60,
                    over=9 * 60)

    @staticmethod
    def get_range_size():
        return 30

    @staticmethod
    def get_stable_range():
        return 3


def diff_minutes(s, e):
    return e - s

@experiment_type
class SleepVariabilityStress(ExperimentType):

    @staticmethod
    def get_name():
        return "sleepvariabilitystress"

    @staticmethod
    def get_inputs(experiment, start_date, end_date, use_variability):
        offset = datetime.timedelta(hours=-5)
        sleep_times = ExperimentType._get_jawbone_activity_start(experiment, start_date, end_date, "sleeps", offset=offset)
        sleep_start_minutes = []
        tz = pytz.timezone(experiment.user.timezone)
        daystart = tz.localize(datetime.datetime.combine(start_date + offset, datetime.datetime.min.time()))
        for sleep_time in sleep_times:
            if sleep_time is None:
                sleep_start_minutes.append(None)
            else:
                sleep_start = sleep_time - daystart
                sleep_start_minutes.append(round(sleep_start.total_seconds() / 60.0))
            daystart += datetime.timedelta(days=1)

        if not use_variability:
            return sleep_start_minutes

        average = experiment.initial_stage_average

        if average is None:
            average = mean(sleep_start_minutes) % (24 * 60)

        # we expect variances to be positive on the first day and negative on the second day. We flip even days, to make math easier later on (ie, by flipping them now, we assume we're dealing with absolute values later)
        variances = [(((sleep_start - average)) * (-1) ** i if sleep_start is not None else None) for i, sleep_start in enumerate(sleep_start_minutes)]
        return variances

    @staticmethod
    def calculate_input_average(initial_stage_inputs):
        return mean(initial_stage_inputs)

    @staticmethod
    def get_outputs(experiment, start_date, end_date):
        return ExperimentType._get_checkins_value(experiment, start_date, end_date, "stress")

    @staticmethod
    def get_ranges():
        return dict(under=15,
                    N1=30,
                    N2=60,
                    N3=90,
                    over=105)

    @staticmethod
    def get_range_size():
        return 15

    @staticmethod
    def get_stable_range():
        return 3

    @staticmethod
    def use_variability():
        return True

    @staticmethod
    def should_minimize_result():
        return True


@experiment_type
class LeisureHappiness(ExperimentType):

    @staticmethod
    def get_name():
        return "leisurehappiness"

    @staticmethod
    def get_inputs(experiment, start_date, end_date, use_variability):
        return ExperimentType._get_checkins_value(experiment, start_date, end_date, "leisure_time")

    @staticmethod
    def get_outputs(experiment, start_date, end_date):
        return ExperimentType._get_checkins_value(experiment, start_date, end_date, "happiness")

    @staticmethod
    def get_ranges():
        return dict(under=15,
                    N1=30,
                    N2=60,
                    N3=90,
                    over=105)

    @staticmethod
    def get_range_size():
        return 15

    @staticmethod
    def get_stable_range():
        return 3
