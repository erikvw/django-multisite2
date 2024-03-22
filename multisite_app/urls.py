from django.urls import re_path

from multisite_app.views import domain_view

urlpatterns = [re_path(r"^domain/$", domain_view)]
