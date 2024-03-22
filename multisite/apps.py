from django.apps import AppConfig as DjangoApponfig


class AppConfig(DjangoApponfig):
    name = "multisite"
    verbose_name = "Multisite"
    default_auto_field = "django.db.models.BigAutoField"
