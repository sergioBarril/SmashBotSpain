from django.contrib import admin
from smashbotspain import models

# Register your models here.

class GameSetAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at',)


admin.site.register(models.Player)
admin.site.register(models.Region)
admin.site.register(models.Tier)
admin.site.register(models.Character)
admin.site.register(models.Main)
admin.site.register(models.Arena)
admin.site.register(models.ArenaPlayer)
admin.site.register(models.Message)
admin.site.register(models.Guild)
admin.site.register(models.GameSet, GameSetAdmin)
admin.site.register(models.Game)
admin.site.register(models.GamePlayer)
admin.site.register(models.Stage)
admin.site.register(models.Rating)