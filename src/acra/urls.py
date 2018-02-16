from django.conf.urls import url

import views

urlpatterns = [

    url(r'report/', views.report, name='report'),
    
]
