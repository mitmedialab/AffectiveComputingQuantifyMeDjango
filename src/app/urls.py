from django.conf.urls import include, url
from . import views, auth_views
from django.views.generic.base import TemplateView

urlpatterns = [

    url(r'^obtain_token/$', auth_views.obtain_token, name='obtain_token'),
    url(r'^set_user_data/$', views.set_user_data, name='set_user_data'),

    url(r'^start_experiment/$', views.start_experiment, name='start_experiment'),
    url(r'^experiment_checkin/$', views.experiment_checkin, name='experiment_checkin'),

    url(r'^get_experiments/$', views.get_experiments, name='get_experiments'),

    url(r'^refresh_instructions/$', views.refresh_instructions, name='refresh_instructions'),

    url(r'^cancel_experiment/$', views.cancel_experiment, name='cancel_experiment'),

    url(r'^jawbone_webhook', views.jawbone_webhook, name='jawbone_webhook'),
    url(r'^update_jawbone', views.update_jawbone, name='update_jawbone'),

]

