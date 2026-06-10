from django import forms
from .models import Task

class PerformanceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # نستقبل الموظف لمعرفة المهام المخصصة له
        employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        
        if employee:
            # جلب المهام العامة
            global_tasks = Task.objects.filter(is_global=True)
            # جلب المهام المخصصة لهذا الموظف تحديداً
            custom_tasks = employee.custom_tasks.all()
            # دمج المهام معاً
            all_tasks = (global_tasks | custom_tasks).distinct()
            
           # إنشاء حقول الاستمارة ديناميكياً بناءً على المهام
            for task in all_tasks:
                field = forms.IntegerField(
                    label=task.name,
                    min_value=0,
                    initial=0,
                    required=True,
                    widget=forms.NumberInput(attrs={
                        'class': 'w-full p-4 border border-gray-200 rounded-xl focus:outline-none focus:border-brand-gold focus:ring-2 focus:ring-brand-gold/20 font-bold text-brand-dark transition-all text-center text-xl bg-gray-50',
                    })
                )
                # إرفاق كائن المهمة بالحقل لكي نستخدمه في الـ HTML
                field.task_obj = task 
                self.fields[f'task_{task.id}'] = field