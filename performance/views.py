from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q, Count
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from .models import Employee, DailyPerformance, WarningLog
from .forms import PerformanceForm
import os
from groq import Groq
from django.http import JsonResponse
import json
from .models import Employee, DailyPerformance, WarningLog, Task, TaskCompletion # تأكد من استيراد Task و TaskCompletion في الأعلى
from .models import Task # تأكد من استيراد Task في أعلى الملف إذا لم تكن موجودة

@login_required(login_url='login')
def dashboard(request):
    if not request.user.is_staff:
        return redirect('add_performance')
        
    today = timezone.now().date()

    # 🎛️ 1. استقبال الفلاتر
    period = request.GET.get('period', 'all')
    employee_id = request.GET.get('employee', '')

    perf_q_annotate = Q()
    warn_q_annotate = Q()
    perf_q_general = Q()
    warn_q_general = Q()

    if period == 'today':
        perf_q_annotate &= Q(performances__date=today)
        warn_q_annotate &= Q(warnings__date=today)
        perf_q_general &= Q(date=today)
        warn_q_general &= Q(date=today)
    elif period == 'week':
        perf_q_annotate &= Q(performances__date__gte=today - timedelta(days=7))
        warn_q_annotate &= Q(warnings__date__gte=today - timedelta(days=7))
        perf_q_general &= Q(date__gte=today - timedelta(days=7))
        warn_q_general &= Q(date__gte=today - timedelta(days=7))
    elif period == 'month':
        perf_q_annotate &= Q(performances__date__gte=today - timedelta(days=30))
        warn_q_annotate &= Q(warnings__date__gte=today - timedelta(days=30))
        perf_q_general &= Q(date__gte=today - timedelta(days=30))
        warn_q_general &= Q(date__gte=today - timedelta(days=30))

    if employee_id:
        perf_q_general &= Q(employee_id=employee_id)
        warn_q_general &= Q(employee_id=employee_id)

    employees_qs = Employee.objects.all()
    if employee_id:
        employees_qs = employees_qs.filter(id=employee_id)

    employees_ranking = employees_qs.annotate(
        avg_performance=Avg('performances__overall_percentage', filter=perf_q_annotate),
        num_warnings=Count('warnings', filter=warn_q_annotate, distinct=True)
    ).order_by('-avg_performance')

    top_performers = employees_ranking.filter(avg_performance__isnull=False)[:5]
    low_performers = employees_ranking.filter(num_warnings__gte=1).distinct()

    # ==========================================
    # 📊 2. حساب الـ KPIs
    # ==========================================
    base_perf_qs = DailyPerformance.objects.filter(perf_q_general)
    avg_performance_kpi = base_perf_qs.aggregate(Avg('overall_percentage'))['overall_percentage__avg'] or 0

    total_emps = employees_qs.count()
    warned_emps = WarningLog.objects.filter(warn_q_general).values('employee').distinct().count()
    warning_rate = (warned_emps / total_emps * 100) if total_emps > 0 else 0

    productivity_score = (avg_performance_kpi * 0.8) + ((100 - warning_rate) * 0.2)

    submitted_today = DailyPerformance.objects.filter(date=today).values('employee').distinct().count()
    submission_rate = (submitted_today / total_emps * 100) if total_emps > 0 else 0

    # ==========================================
    # 🧠 3. الذكاء الإداري (Smart Insights)
    # ==========================================
    seven_days_ago = today - timedelta(days=7)
    fourteen_days_ago = today - timedelta(days=14)

    current_week_avg = DailyPerformance.objects.filter(date__gte=seven_days_ago).aggregate(Avg('overall_percentage'))['overall_percentage__avg'] or 0
    prev_week_avg = DailyPerformance.objects.filter(date__gte=fourteen_days_ago, date__lt=seven_days_ago).aggregate(Avg('overall_percentage'))['overall_percentage__avg'] or 0

    if prev_week_avg > 0:
        trend_percentage = ((current_week_avg - prev_week_avg) / prev_week_avg) * 100
    else:
        trend_percentage = 100 if current_week_avg > 0 else 0

    trend_direction = "up" if trend_percentage >= 0 else "down"
    recent_warnings_count = WarningLog.objects.filter(date__gte=seven_days_ago).values('employee').distinct().count()

# ==========================================
    # 📈 4. تجهيز بيانات الرسوم البيانية (Trend Analysis)
    # ==========================================
    chart_names = [emp.name for emp in employees_ranking[:10] if emp.avg_performance is not None]
    chart_perfs = [float(emp.avg_performance or 0) for emp in employees_ranking[:10] if emp.avg_performance is not None]
    
    good_employees_count = employees_ranking.filter(num_warnings=0).count()
    bad_employees_count = low_performers.count()

    # 🎛️ ربط الرسم البياني الزمني بالفلتر
    if period == 'week':
        trend_days = 7
        chart_title_context = "آخر 7 أيام"
    elif period == 'month':
        trend_days = 30
        chart_title_context = "آخر 30 يوماً"
    elif period == 'today':
        trend_days = 7 # نعرض 7 أيام حتى لو اختار اليوم لكي يظهر الخط البياني بشكل منطقي
        chart_title_context = "آخر 7 أيام (للمقارنة)"
    else:
        trend_days = 15 # الافتراضي
        chart_title_context = "آخر 15 يوماً"

    start_trend_date = today - timedelta(days=trend_days-1)
    date_list = [start_trend_date + timedelta(days=x) for x in range(trend_days)]
    trend_dates_labels = [d.strftime("%m-%d") for d in date_list]

    # مسار الأداء الزمني
    perf_trend_qs = DailyPerformance.objects.filter(date__gte=start_trend_date)
    if employee_id:
        perf_trend_qs = perf_trend_qs.filter(employee_id=employee_id)
    perf_dict = {p['date']: p['avg_perf'] for p in perf_trend_qs.values('date').annotate(avg_perf=Avg('overall_percentage'))}
    trend_perfs_data = [round(perf_dict.get(d, 0), 1) for d in date_list]

    # مسار الإنذارات الزمني
    warn_trend_qs = WarningLog.objects.filter(date__gte=start_trend_date)
    if employee_id:
        warn_trend_qs = warn_trend_qs.filter(employee_id=employee_id)
    warn_dict = {w['date']: w['count'] for w in warn_trend_qs.values('date').annotate(count=Count('id'))}
    trend_warns_data = [warn_dict.get(d, 0) for d in date_list]

    # ==========================================
    # 🤖 5. محرك التوصيات الذكي (AI Recommendations)
    # ==========================================
    ai_promotions = []
    ai_training = []
    ai_burnout = []

    for emp in employees_ranking:
        if emp.avg_performance is None:
            continue
            
        # 1. من يجب ترقيته أو مكافأته؟ (أداء عالي + التزام تام)
        if emp.avg_performance >= 90 and emp.num_warnings == 0:
            ai_promotions.append(emp)
            
        # 2. من يحتاج إلى تدريب؟ (أداء ضعيف أو إنذارات كثيرة)
        if emp.avg_performance < 60 or emp.num_warnings >= 3:
            ai_training.append(emp)
            
        # 3. من المعرض للاستقالة أو الاحتراق الوظيفي؟ (انخفاض مفاجئ وحاد في الأداء)
        emp_recent = DailyPerformance.objects.filter(employee=emp, date__gte=seven_days_ago).aggregate(Avg('overall_percentage'))['overall_percentage__avg'] or 0
        emp_prev = DailyPerformance.objects.filter(employee=emp, date__gte=fourteen_days_ago, date__lt=seven_days_ago).aggregate(Avg('overall_percentage'))['overall_percentage__avg'] or 0
        
        # إذا كان أداؤه جيداً جداً الأسبوع الماضي، وانهار هذا الأسبوع
        if emp_prev >= 70 and emp_recent < 50:
            ai_burnout.append({
                'employee': emp,
                'drop': round(emp_prev - emp_recent, 1) # حساب مقدار السقوط
            })

    # نأخذ أهم 3 موظفين لكل فئة لعرضهم في اللوحة
    ai_promotions = ai_promotions[:3]
    ai_training = ai_training[:3]
    ai_burnout = ai_burnout[:3]

    context = {
        'top_performers': top_performers,
        'low_performers': low_performers,
        'employees_ranking': employees_ranking,
        'good_count': good_employees_count,
        'bad_count': bad_employees_count,
        'trend_percentage': abs(trend_percentage),
        'trend_direction': trend_direction,
        'recent_warnings_count': recent_warnings_count,
        'all_employees': Employee.objects.all(),
        'selected_period': period,
        'selected_employee': employee_id,
        'avg_performance_kpi': avg_performance_kpi,
        'warning_rate': warning_rate,
        'productivity_score': productivity_score,
        'submission_rate': submission_rate,
        'ai_promotions': ai_promotions,
        'ai_training': ai_training,
        'ai_burnout': ai_burnout,   
        # بيانات الرسوم البيانية (JSON)
        'chart_names': json.dumps(chart_names),
        'chart_perfs': json.dumps(chart_perfs),
        'trend_dates_labels': json.dumps(trend_dates_labels),
        'trend_perfs_data': json.dumps(trend_perfs_data),
        'trend_warns_data': json.dumps(trend_warns_data),
        'chart_title_context': chart_title_context, # أضفنا هذا المتغير للنصوص
    }
    return render(request, 'dashboard.html', context)
@login_required(login_url='login')
def add_performance(request):
    try:
        employee = request.user.employee
    except:
        messages.error(request, 'حسابك الحالي غير مرتبط بملف موظف. الرجاء مراجعة مدير النظام.')
        return redirect('login')

    if request.method == 'POST':
        # نمرر الموظف للاستمارة لكي تجلب مهامه
        form = PerformanceForm(request.POST, employee=employee)
        if form.is_valid():
            # 1. إنشاء سجل الأداء اليومي
            performance = DailyPerformance.objects.create(
                employee=employee,
                date=timezone.now().date()
            )
            
            # 2. حفظ إنجازات المهام (Task Completions)
            for field_name, quantity in form.cleaned_data.items():
                if field_name.startswith('task_'):
                    task_id = int(field_name.split('_')[1])
                    task = Task.objects.get(id=task_id)
                    
                    TaskCompletion.objects.create(
                        daily_performance=performance,
                        task=task,
                        quantity=quantity
                    )
            
            # 3. حساب النسبة والتقييم تلقائياً
            performance.calculate_performance()
            
            messages.success(request, 'تم تسجيل إنجازك اليومي بنجاح! شكراً لك.')
            if request.user.is_staff:
                return redirect('dashboard')
            else:
                return redirect('add_performance')
    else:
        form = PerformanceForm(employee=employee)

    return render(request, 'add_performance.html', {'form': form, 'employee': employee})

@login_required(login_url='login')
def branch_report(request):
    if not request.user.is_staff:
        return redirect('add_performance')

    employees = Employee.objects.all()
    report_data = []

    for emp in employees:
        performances = emp.performances.all()
        total_warnings = emp.warnings.count()
        
        avg_overall = performances.aggregate(Avg('overall_percentage'))['overall_percentage__avg'] or 0
        
        # تحديث حساب أيام النجاح والإخفاق بناءً على الحالات الجديدة
        normal_days = performances.filter(Q(status='ممتاز') | Q(status='جيد')).count()
        low_days = performances.filter(Q(status='Warning') | Q(status='Critical')).count()

        # نظام التوصيات الجديد المبني على النسبة العامة للموظف
        if avg_overall >= 90:
            recommendation = "ممتاز (أداء استثنائي)"
        elif avg_overall >= 70:
            recommendation = "جيد (أداء مستقر)"
        elif avg_overall >= 50:
            recommendation = "Warning (يحتاج متابعة وتوجيه)"
        else:
            recommendation = "Critical (تدخل إداري عاجل)"

        report_data.append({
            'id': emp.id,
            'name': emp.name,
            'warnings': total_warnings,
            'avg_performance': round(avg_overall, 2),
            'normal_days': normal_days,
            'low_days': low_days,
            'recommendation': recommendation
        })

    return render(request, 'report.html', {'report_data': report_data})

@login_required(login_url='login')
def employee_profile(request, employee_id):
    if not request.user.is_staff:
        return redirect('add_performance')

    employee = get_object_or_404(Employee, id=employee_id)
    
    performances = employee.performances.all().order_by('-date')
    warnings = employee.warnings.all().order_by('-date')

    avg_overall = performances.aggregate(Avg('overall_percentage'))['overall_percentage__avg'] or 0
    total_warnings = warnings.count()
    total_days = performances.count()

    chart_performances = employee.performances.all().order_by('date')[:30]
    chart_dates = [p.date.strftime("%Y-%m-%d") for p in chart_performances]
    chart_scores = [float(p.overall_percentage or 0) for p in chart_performances]

    # ==========================================
    # ⚙️ تجهيز المهام الديناميكية للجدول
    # ==========================================
    global_tasks = Task.objects.filter(is_global=True)
    custom_tasks = employee.custom_tasks.all()
    employee_tasks = (global_tasks | custom_tasks).distinct()

    # تجهيز قائمة الإنجازات لتتناسب مع الأعمدة الديناميكية
    perf_data_list = []
    for perf in performances:
        # تحويل إنجازات هذا اليوم إلى قاموس {رقم_المهمة: الكمية} لسهولة البحث
        completions_dict = {comp.task_id: comp.quantity for comp in perf.completions.all()}
        
        task_quantities = []
        for task in employee_tasks:
            qty = completions_dict.get(task.id, 0) # إذا لم ينجزها، نضع 0
            task_quantities.append({
                'qty': qty,
                'target': task.daily_target,
                'is_low': qty < task.daily_target # لمعرفة هل نلون الرقم بالأحمر أم الأخضر
            })
        
        perf_data_list.append({
            'date': perf.date,
            'overall_percentage': perf.overall_percentage,
            'status': perf.status,
            'task_quantities': task_quantities
        })

    context = {
        'employee': employee,
        'warnings': warnings,
        'avg_overall': round(avg_overall, 1),
        'total_warnings': total_warnings,
        'total_days': total_days,
        'chart_dates': json.dumps(chart_dates),
        'chart_scores': json.dumps(chart_scores),
        'employee_tasks': employee_tasks, # إرسال عناوين الأعمدة
        'perf_data_list': perf_data_list, # إرسال البيانات المرتبة
    }
    return render(request, 'employee_profile.html', context)

# 1. دالة عرض صفحة الشات
@login_required(login_url='login')
def ai_chat_page(request):
    if not request.user.is_staff:
        return redirect('add_performance')
    return render(request, 'ai_chat.html')

# 2. دالة الـ API التي تتحدث مع Groq
@login_required(login_url='login')
def ai_chat_api(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'غير مصرح لك'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message')

            # ==========================================
            # 🧠 1. تجميع بيانات الموظفين الحقيقية (Context)
            # ==========================================
            employees = Employee.objects.annotate(
                avg_perf=Avg('performances__overall_percentage'),
                warns=Count('warnings')
            )
            
            context_data = "إليك بيانات أداء موظفي القسم الحالية:\n"
            for emp in employees:
                perf = round(emp.avg_perf, 1) if emp.avg_perf else 0
                context_data += f"- الموظف: {emp.name} | متوسط الأداء: {perf}% | عدد الإنذارات: {emp.warns}\n"

            # ==========================================
            # 🤖 2. إعداد رسالة النظام (System Prompt)
            # ==========================================
            system_prompt = f"""
            أنت مستشار موارد بشرية (HR) ومدير ذكي خبير. مهمتك مساعدة مدير القسم في تحليل أداء الموظفين.
            {context_data}
            
            تعليمات هامة:
            1. أجب باللغة العربية بأسلوب احترافي، إداري، ومشجع.
            2. اعتمد فقط على البيانات المرفقة أعلاه للإجابة على أسئلة المدير.
            3. إذا طلب منك مقارنة، اذكر الأرقام.
            4. إذا طلب منك نصيحة (ماذا أقول للمقصر)، أعطه خطوات عملية أو نص رسالة لبقة ومحفزة.
            """

            # ==========================================
            # 🚀 3. الاتصال بـ Groq API
            # ==========================================
            # جلب المفتاح بأمان من ملف .env
            groq_api_key = os.getenv("GROQ_API_KEY")
            
            if not groq_api_key:
                return JsonResponse({'error': 'مفتاح API غير موجود في إعدادات النظام.'}, status=500)

            client = Groq(api_key=groq_api_key) 

            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                model="llama3-70b-8192", 
                temperature=0.7,
            )

            ai_response = chat_completion.choices[0].message.content
            return JsonResponse({'response': ai_response})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)