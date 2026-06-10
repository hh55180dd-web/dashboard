from django.contrib import admin
from .models import Employee, Task, DailyPerformance, TaskCompletion, WarningLog

class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'points', 'daily_target', 'is_global')
    list_filter = ('is_global',)
    filter_horizontal = ('assigned_employees',) # شكل جميل لاختيار الموظفين

admin.site.register(Employee)
admin.site.register(Task, TaskAdmin)
admin.site.register(DailyPerformance)
admin.site.register(TaskCompletion)
admin.site.register(WarningLog)