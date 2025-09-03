from django.apps import AppConfig


class FonarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fonar'

    def ready(self):
           import fonar.signals 
