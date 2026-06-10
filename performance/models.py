from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

# ==========================================
# 1. جدول المهام (القاموس الإداري)
# ==========================================
class Task(models.Model):
    name = models.CharField(max_length=200, verbose_name="اسم المهمة")
    points = models.IntegerField(default=1, verbose_name="النقاط لكل إنجاز")
    daily_target = models.IntegerField(default=1, verbose_name="الهدف اليومي (الكمية المطلوبة)")
    
    # هل هي للجميع أم لموظفين محددين؟
    is_global = models.BooleanField(default=True, verbose_name="مهمة مشتركة للجميع؟")
    assigned_employees = models.ManyToManyField(Employee, blank=True, related_name='custom_tasks', verbose_name="تخصيص لموظفين محددين")

    def __str__(self):
        type_str = "عامة" if self.is_global else "مخصصة"
        return f"{self.name} ({self.points} نقاط) - {type_str}"

# ==========================================
# 2. السجل اليومي العام للموظف
# ==========================================
class DailyPerformance(models.Model):
    STATUS_CHOICES = [
        ('ممتاز', 'ممتاز (90-100)'),
        ('جيد', 'جيد (70-89)'),
        ('تحذير', 'تحذير (50-69)'),
        ('حرج', 'حرج (<50)'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performances')
    date = models.DateField(default=timezone.now)
    
    # حقول محسوبة تلقائياً
    total_earned_points = models.IntegerField(default=0)
    total_target_points = models.IntegerField(default=0)
    overall_percentage = models.FloatField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, blank=True)

    # دالة تقوم بحساب النقاط والنسبة بعد إدخال المهام
    def calculate_performance(self):
        completions = self.completions.all()
        earned = 0
        target = 0

        # جلب المهام المطلوبة من هذا الموظف (العامة + المخصصة له)
        global_tasks = Task.objects.filter(is_global=True)
        custom_tasks = self.employee.custom_tasks.all()
        all_tasks = (global_tasks | custom_tasks).distinct()

        # حساب إجمالي النقاط المستهدفة لليوم
        for task in all_tasks:
            target += (task.points * task.daily_target)

        # حساب إجمالي النقاط التي حققها فعلياً
        for comp in completions:
            earned += (comp.task.points * comp.quantity)

        self.total_earned_points = earned
        self.total_target_points = target

        # حساب النسبة المئوية
        if target > 0:
            pct = (earned / target) * 100
        else:
            pct = 100 if earned > 0 else 0

        self.overall_percentage = round(pct, 2)

        # التقييم
        if self.overall_percentage >= 90:
            self.status = 'ممتاز'
        elif self.overall_percentage >= 70:
            self.status = 'جيد'
        elif self.overall_percentage >= 50:
            self.status = 'تحذير'
        else:
            self.status = 'حرج'

        self.save()

        # نظام الإنذارات
        if self.status in ['تحذير', 'حرج']:
            WarningLog.objects.get_or_create(employee=self.employee, date=self.date, defaults={'performance_record': self})
        else:
            # مسح الإنذار إذا قام الموظف بتعديل إنجازه وتحسن أداؤه في نفس اليوم
            WarningLog.objects.filter(performance_record=self).delete()

# ==========================================
# 3. تفاصيل إنجاز المهام (كم أنجز من كل مهمة؟)
# ==========================================
class TaskCompletion(models.Model):
    daily_performance = models.ForeignKey(DailyPerformance, on_delete=models.CASCADE, related_name='completions')
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0, verbose_name="الكمية المنجزة")

    def __str__(self):
        return f"{self.task.name}: {self.quantity}"

# ==========================================
# 4. سجل الإنذارات
# ==========================================
class WarningLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='warnings')
    performance_record = models.ForeignKey(DailyPerformance, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    
    def __str__(self):
        return f"إنذار لـ {self.employee.name} في {self.date}"
    

# account superuser: admin
# username : hamid
# email : hh55180dd@gmail.com
# password : rax123rax