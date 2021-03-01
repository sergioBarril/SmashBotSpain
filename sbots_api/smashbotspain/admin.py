from django.contrib import admin
from smashbotspain import models

# Register your models here.

admin.site.register(models.Player)
admin.site.register(models.Region)
admin.site.register(models.Tier)
admin.site.register(models.Character)
admin.site.register(models.Arena)
admin.site.register(models.ArenaPlayer)
admin.site.register(models.Message)
admin.site.register(models.Guild)