from django.core.mail import EmailMessage
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from projects.models import FinancialProject, NonFinancialProject, Project, Log, FinancialContribution
####### Danial imports .Some of them may be redundant!!!

from django.contrib.auth import login, logout
from django.shortcuts import redirect
from django.views.generic import CreateView, TemplateView
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.template import loader

from accounts.forms import CharitySignUpForm
from accounts.models import *
from projects.models import CooperationRequest, search_charity, search_benefactor, convert_str_to_date
from accounts.log_util import Logger
from accounts.search_util import create_query_schedule
import random, string

possible_characters = string.ascii_letters + string.digits
ip = 'http://127.0.0.1:8000/accounts/'


def check_valid(field):
    return field is not None and len(field) > 0


def generate_recover_string(length=32):
    rng = random.SystemRandom()
    return "".join([rng.choice(possible_characters) for i in range(length)])


def get_object(obj_class, *args, **kwargs):
    try:
        obj_set = obj_class.objects.filter(*args, **kwargs)
        if obj_set.count() <= 0:
            return None
        return obj_set.all()[0]
    except:
        # TODO Raise Super Ultra Error
        return 'Error'


def error_context_generate(error_title, error_message, redirect_address):
    return {
        'error_title': error_title,
        'error_message': error_message,
        'redirect_address': redirect_address
    }


# Create your views here.

def all_user_projects(request):
    if not request.user.is_charity:
        pass
    projects = request.user.charity.project_set
    return render(request, 'url', {
        'all_user_projects': projects
    })


def add_ability_to_benefactor(request):
    benefactor_id = int(request.POST.get('add_ability_benefactor_id'))
    if request.user.id != benefactor_id:
        # TODO Return Error
        context = error_context_generate('Authentication Error', 'You Don\'t Have Permission to Change this Account!',
                                         '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))

    ability_type_name = request.POST.get('add_ability_ability_type_name')
    ability_description = request.POST.get('add_ability_description')
    ability_type = AbilityType.objects.all().filter(name__iexact=ability_type_name)[0]
    benefactor = Benefactor.objects.all().filter(user_id=benefactor_id)[0]
    ability = Ability(benefactor=benefactor, ability_type=ability_type, description=ability_description)
    ability.save()
    benefactor.ability_set.add(ability)
    Logger.add_ability_benefactor(request.user, None, None)
    # TODO Fix Path
    return HttpResponseRedirect('path')


def submit_benefactor_score(request, ability_id):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'You are not Signed In!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if request.user.is_benefactor:
        # TODO Raise Account Type Error
        context = error_context_generate('Account Type Error', 'You Can\'t Submit Score for Another Benefactor!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    ability = get_object(Ability, id=ability_id)
    if ability is None:
        # TODO Raise Not Found Error
        context = error_context_generate('Not Found', 'Requested Ability Cannot be Found', 'accounts:charity_dashboard')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    try:
        benefactor = ability.benefactor
        charity = ability.charity
        charity_projects = [nf_project for nf_project in charity.project_set if nf_project.type != 'financial']
        if len([project for project in NonFinancialProject.objects.all() if
                project.project in charity_projects and project.ability_type is ability.ability_type]) <= 0:
            context = error_context_generate('No Cooperation Error',
                                             'You Cannot Submit a Score for a Benefactor with Whom You Had no ' +
                                             'Cooperation On This Ability Type!',
                                             'accounts:charity_dashboard')
            # TODO Raise No_Cooperation Error
            template = loader.get_template('accounts/error_page.html')
            return HttpResponse(template.render(context, request))
        score = charity.benefactorscore_set.filter(benefactor=benefactor, charity=charity).all()[0]
        if score is None:
            score = BenefactorScore.objects.create(ability_type=ability, benefactor=benefactor,
                                                   charity=get_object(Charity, user=request.user))
        if float(request.POST.get('score')) > 10.0:
            score.score = 10.0
        else:
            score.score = float(request.POST.get('score'))
        score.save()
        Logger.submit_score(request.user, benefactor.user, None)
        return HttpResponseRedirect([])
    except:
        context = error_context_generate('Unexpected Error', 'Some of the Data Needed for The Page is Lost or Damaged',
                                         '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
        # TODO raise error


def submit_charity_score(request, charity_username):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', ' You are not Signed In!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if request.user.is_charity:
        context = error_context_generate('Account Type Error', 'You Can\'t Submit Score for Another Charity!', '')
        # TODO Raise Account Type Error
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    benefactor = get_object(Benefactor, user=request.user)
    if benefactor.charity_set.get(user=get_object(User, username=request.POST.get('charity_username'))).count <= 0:
        context = error_context_generate('No Cooperation Error',
                                         'You Cannot Submit Score for a Charity with Which You Had no Cooperation!', '')
        # TODO Raise No_Cooperation Error
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    try:
        charity = get_object(Charity, user=get_object(User, username=charity_username))
        score = benefactor.charityscore_set.filter(benefactor=benefactor, charity=charity).all()[0]
        if score is None:
            score = get_object(CharityScore, charity=charity, benefactor=get_object(Benefactor, user=request.user))
        if float(request.POST.get('score')) > 10.0:
            score.score = 10.0
        else:
            score.score = float(request.POST.get('score'))
        score.save()
        Logger.submit_score(request.user, charity.user, None)
        return HttpResponseRedirect([])
    except:
        # TODO raise error
        context = error_context_generate('Unexpected Error', 'Some of the Data Needed for The Page is Lost or Damaged',
                                         '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))


def submit_ability_request(request):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'You are not Signed In!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    try:
        new_request = AbilityRequest.objects.create(type=request.POST.get('type'), name=request.POST.get('name'),
                                                    description=request.POST.get('description'))
        new_request.save()

        Logger.request_new_ability_type(request.user, None, None)
        return HttpResponseRedirect([])
    except:
        # TODO Raise Error
        context = error_context_generate('Unexpected Error', 'Some of the Data Needed for The Page is Lost or Damaged',
                                         '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))


def submit_cooperation_request(request, project_id):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'You are not Signed In!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    try:
        # FIXME How should we find the project? I mean which data is given to find the project with?
        project = NonFinancialProject.objects.all().filter(project_id=project_id)
        if request.user.is_benefactor:
            benefactor = get_object(Benefactor, user=request.user)
            charity = get_object(Charity, user=get_object(User, username=request.POST.get('username')))
            new_notification = Notification.objects.create(type='new_request', user=charity.user,
                                                           datetime=datetime.datetime.now())
            new_notification.description = 'A new Cooperation Request is Received for Project ' + project.project
            new_notification.save()
            Logger.request_submit(request.user, charity.user, project.project)
            request_type = 'b2c'
        else:
            benefactor = get_object(Benefactor, user=get_object(User, username=request.POST.get('username')))
            charity = get_object(Charity, user=request.user)
            new_notification = Notification.objects.create(type='new_request', user=benefactor.user,
                                                           datetime=datetime.datetime.now())
            new_notification.description = 'A new Cooperation Request Has Been Received!'
            new_notification.save()
            Logger.request_submit(request.user, benefactor.user, project.project)
            request_type = 'c2b'
        new_request = CooperationRequest.objects.create(benefactor=benefactor, charity=charity, type=request_type,
                                                        description=request.POST.get('description'))
        new_request.nonfinancialproject = project
        new_request.save()
        return HttpResponseRedirect([])
    except:
        # TODO Raise Error
        context = {
            'error_message': 'Unexpected Error: Some of the Data Needed for The Page is Lost or Damaged'
        }
        context = error_context_generate('Unexpected Error', 'Some of the Data Needed for The Page is Lost or Damaged',
                                         '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))


#################################################################
#################################################################
#################################################################
# ignore this block


class CharitySignUpView(CreateView):
    model = User
    form_class = CharitySignUpForm
    template_name = 'registration/signup_form.html'

    def get_context_data(self, **kwargs):
        print('Azed')
        kwargs['user_type'] = 'charity'
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect('charity_signup')


#################################################################
#################################################################
#################################################################


#####Signup

class SignUpView(TemplateView):
    template_name = "accounts/register.html"


@csrf_exempt
def signup(request):
    # try:

    test1_user = User.objects.filter(username=request.POST.get("username"))
    test2_user = User.objects.filter(username=request.POST.get("email"))
    if test1_user.__len__() != 0 and test2_user.__len__() != 0:
        return render(request, 'accounts/register.html',
                      {'error_message': 'Account already exists! Try login or forget password.'})

    if test1_user.__len__() == 0 and len(test2_user) != 0:
        return render(request, 'accounts/register.html', {'error_message': 'Email is already taken!  '})

    if len(test1_user) != 0 and len(test2_user) == 0:
        return render(request, 'accounts/register.html',
                      {'error_message': 'Username is already taken! try another username.  '})

    tmp_contact_info = ContactInfo.objects.create(country="ایران",
                                                  province=request.POST.get("province"),
                                                  city=request.POST.get("city"),
                                                  address=request.POST.get("address"),
                                                  postal_code=request.POST.get("postal_code"),
                                                  phone_number=request.POST.get("phone_number")
                                                  )
    tmp_user = User.objects.create(username=request.POST.get("username"), password=request.POST.get("password"),
                                   email=request.POST.get("email"), contact_info=tmp_contact_info,
                                   description=request.POST.get("description"))
    tmp_user.is_active = False
    tmp_user.save()
    code = generate_recover_string()
    message = 'برای فعال شدن حساب خود بر روی لینک زیر کلیک کنید:' + '\n'
    message += ip + 'activate/' + str(tmp_user.id) + '/' + code
    tmp_user.activation_string = code
    email_message = EmailMessage('Activation Email', message, to=[tmp_user.email])
    email_message.send()
    Logger.create_account(tmp_user, None, None)
    if request.POST.get("account_type") == "Charity":
        tmp_user.is_charity = True
        tmp_charity = Charity.objects.create(user=tmp_user, name=request.POST.get("charity_name"))
        tmp_charity.save()
        tmp_user.save()

        login(request, tmp_user)
        Logger.login(request.user, None, None)
        return HttpResponseRedirect(reverse('accounts:user_profile'))


    else:
        tmp_user.is_benefactor = True
        age = request.POST.get('age')
        age = None if age is None else int(age)
        tmp_benefactor = Benefactor.objects.create(user=tmp_user, first_name=request.POST.get("first_name"),
                                                   last_name=request.POST.get("last_name"), age=age,
                                                   gender=request.POST.get('gender'))
        tmp_benefactor.save()
        tmp_user.save()
        login(request, tmp_user)
        Logger.login(request.user, None, None)
        template = loader.get_template('accounts/login.html')
        context = {'error_message': 'لطفاً ایمیل خود را تایید کنید.'}
        return HttpResponse(template.render(context, request))


# except:
#     context = error_context_generate('Signup Error!', 'Error While Creating New Account!', 'accounts:signup_view')
#     template = loader.get_template('accounts/error_page.html')
#     return HttpResponse(template.render(context, request))


def activate_user(request, uid, activation_string):
    # TODO any security stuff?
    users = User.objects.filter(id=uid)
    if users.count() != 1:
        # TODO shitty link
        context = error_context_generate('Activation Error', 'Something Went Wrong in Activating Your Account!', 'Home')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    user = users[0]
    if user.activation_string != activation_string:
        # TODO shitty link
        context = error_context_generate('Invalid Key Error', 'Your Provided Activation Key is not Valid', 'Home')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    user.is_active = True
    user.save(update_fields=['is_active'])
    # TODO activation success
    return HttpResponseRedirect(reverse('Home'))


####Login

class LoginView(TemplateView):
    template_name = "accounts/login.html"


def benefactor_dashboard(request):
    user = request.user
    if not user.is_authenticated:
        # TODO error
        context = error_context_generate('Authentication Error', 'لطفاً اول وارد شوید', 'accounts:login_view')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not user.is_active:
        context = error_context_generate('Authentication Error', 'لطفاً اکانت خود را تایید کنید', 'accounts:login_view')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not user.is_benefactor:
        context = error_context_generate('Access Denied', 'شما اجازه دسترسی به این بخش را ندارید', 'accounts:dashboard')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))

    requests = CooperationRequest.objects.filter(type__iexact='c2b').filter(benefactor=user.benefactor).filter(
            state__iexact='on-hold')
    notifications = Notification.objects.filter(user=user)
    user_project_ids = [project.id for project in user.benefactor.project_set.all()]
    complete_project_count = Project.objects.filter(project_state__iexact='completed').filter(
            id__in=user_project_ids).count()
    non_complete_project_count = Project.objects.filter(project_state__iexact='in-progress').filter(id__in=
                                                                                                    user_project_ids).count()
    if request.method == 'GET':
        return render(request, 'accounts/user-dashboard.html', {
            'requests': list(requests),
            'a_notification': notifications[0] if notifications.count() != 0 else None,
            'have_notification': True if notifications.count() > 0 else False,
            'notifications': list(notifications),
            'charity_results': [],
            'complete_project_count': complete_project_count,
            'non_complete_project_count': non_complete_project_count
        })
    elif request.method == 'POST':
        post = request.POST

        name = post.get('name')
        min_score = post.get('min_score')
        min_score = None if min_score is None else float(min_score)
        max_score = post.get('max_score')
        max_score = None if max_score is None else float(max_score)
        min_related_projects = post.get('min_related_projects')
        min_related_projects = None if min_related_projects is None else int(min_related_projects)
        max_related_projects = post.get('max_related_projects')
        max_related_projects = None if max_related_projects is None else int(max_related_projects)
        min_finished_projects = post.get('min_finished_projects')
        min_finished_projects = None if min_finished_projects is None else int(min_finished_projects)
        max_finished_projects = post.get('max_finished_projects')
        max_finished_projects = None if max_finished_projects is None else int(max_finished_projects)
        benefactor_name = post.get('benefactor_name')
        country = post.get('country')
        province = post.get('province')
        city = post.get('city')
        charity_result = search_charity(name=name, min_score=min_score, max_score=max_score,
                                        min_related_projects=min_related_projects,
                                        max_related_projects=max_related_projects,
                                        min_finished_projects=min_finished_projects,
                                        max_finished_projects=max_finished_projects, benefactor_name=benefactor_name,
                                        country=country, province=province, city=city)

        return render(request, 'accounts/user-dashboard.html', {
            'requests': list(requests),
            'a_notification': notifications[0] if notifications.count() != 0 else None,
            'have_notification': True if notifications.count() > 0 else False,
            'notifications': list(notifications),
            'charity_results': charity_result,
            'complete_project_count': complete_project_count,
            'non_complete_project_count': non_complete_project_count
        })


@csrf_exempt
def charity_dashboard(request):
    user = request.user
    if not user.is_authenticated:
        # TODO error
        context = error_context_generate('Authentication Error', 'لطفاً اول وارد شوید', 'accounts:login_view')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not user.is_active:
        context = error_context_generate('Authentication Error', 'لطفاً اکانت خود را تایید کنید', 'accounts:login_view')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not user.is_charity:
        context = error_context_generate('Access Denied', 'شما اجازه دسترسی به این بخش را ندارید', 'accounts:dashboard')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))

    requests = CooperationRequest.objects.filter(type__iexact='b2c').filter(charity=user.charity).filter(
            state__iexact='on-hold')
    notifications = Notification.objects.filter(user=user)
    user_project_ids = [project.id for project in list(user.charity.project_set.all())]
    complete_project_count = Project.objects.filter(project_state__iexact='completed').filter(id__in=user_project_ids).count()
    non_complete_project_count = Project.objects.filter(project_state__iexact='in-progress').filter(id__in=
                                                                                                    user_project_ids).count()
    if request.method == 'GET':
        return render(request, 'accounts/charity-dashboard.html', {
            'requests': list(requests),
            'a_notification': notifications[0] if notifications.count() != 0 else None,
            'have_notification': True if notifications.count() > 0 else False,
            'notifications': list(notifications),
            'benefactor_results': [],
            'complete_project_count': complete_project_count,
            'non_complete_project_count': non_complete_project_count,
            'ability_tags': list(AbilityTag.objects.all()),
        })
    elif request.method == 'POST':
        post = request.POST
        start_date = convert_str_to_date(post.get('start_date'))
        end_date = convert_str_to_date(post.get('end_date'))
        weekly_schedule = create_query_schedule(post.get('schedule'))
        schedule = [start_date, end_date, weekly_schedule]
        min_required_hours = post.get('min_required_hours')
        min_required_hours = None if min_required_hours is None else float(min_required_hours)
        min_date_overlap = post.get('min_date_overlap')
        min_date_overlap = None if min_date_overlap is None else float(min_date_overlap)
        min_time_overlap = post.get('min_time_overlap')
        min_time_overlap = None if min_time_overlap is None else float(min_time_overlap)
        tags = post.get('tags')
        tags = None if tags is None else tags.split(',')
        ability_name = post.get('ability_name')
        ability_min_score = post.get('ability_min_score')
        ability_min_score = None if ability_min_score is None else float(ability_min_score)
        ability_max_score = post.get('ability_max_score')
        ability_max_score = None if ability_max_score is None else float(ability_max_score)
        country = post.get('country')
        province = post.get('province')
        city = post.get('city')
        user_min_score = post.get('user_min_score')
        user_min_score = None if user_min_score is None else float(user_min_score)
        user_max_score = post.get('user_max_score')
        user_max_score = None if user_max_score is None else float(user_max_score)
        gender = post.get('gender')
        first_name = post.get('first_name')
        last_name = post.get('last_name')
        result_benefactor = search_benefactor(schedule, min_required_hours, min_date_overlap, min_time_overlap,
                                              tags, ability_name, ability_min_score, ability_max_score, country,
                                              province, city, user_min_score, user_max_score, gender, first_name,
                                              last_name)
        return render(request, 'accounts/charity-dashboard.html', {
            'requests': list(requests),
            'a_notification': notifications[0] if notifications.count() != 0 else None,
            'have_notification': True if notifications.count() > 0 else False,
            'notifications': list(notifications),
            'benefactor_results': result_benefactor,
            'complete_project_count': complete_project_count,
            'non_complete_project_count': non_complete_project_count
        })


def dashboard(request):
    user = request.user
    if not user.is_authenticated:
        return render(request, 'accounts/login.html', {'error_message': 'لطفاً اول وارد شوید'})
    if not user.is_active:
        context = error_context_generate('Inactive Account', 'Your Account is Not Activated Yet', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if user.is_benefactor:
        return HttpResponseRedirect(reverse('accounts:benefactor_dashboard'))
    elif user.is_charity:
        return HttpResponseRedirect(reverse('accounts:charity_dashboard'))
    else:
        return HttpResponseRedirect(reverse('admin'))


@csrf_exempt
def login_user(request):
    # tmp_user = get_object_or_404(User,username=request.POST.get("username"),password=request.POST.get("password"))
    # try:
    if request.user.is_authenticated:
        Logger.logout(request.user, None, None)
        logout(request)
    tmp_user = User.objects.filter(username=request.POST.get("username"))
    if len(tmp_user) == 0:
        return render(request, 'accounts/login.html', {'error_message': 'کاربر موردنظر یافت نشد!'})
    tmp_user = get_object(User, username=request.POST.get("username"))
    if tmp_user.password != request.POST.get("password"):
        return render(request, 'accounts/login.html', {'error_message': 'رمز اشتباهه -.-'})
    if not tmp_user.is_active:
        return render(request, 'accounts/login.html', {'error_message': 'لطفاً حساب خود را تایید کنید.'})
    if tmp_user.is_charity:
        login(request, user=tmp_user)
        Logger.login(request.user, None, None)
        return HttpResponseRedirect(reverse('accounts:charity_dashboard'))

    elif tmp_user.is_benefactor:

        login(request, tmp_user)
        Logger.login(request.user, None, None)
        return HttpResponseRedirect(reverse('accounts:benefactor_dashboard'))

    else:
        login(request, tmp_user)
        Logger.login(request.user, None, None)
        return HttpResponseRedirect(reverse('admin'))


# except:
#     # TODO Redirect to Login
#     context = error_context_generate('Login Error', 'رمز یا ایمیل درست وارد نشده است', 'login_view')
#     template = loader.get_template('accounts/login.html')
#
#     return HttpResponseRedirect(reverse('accounts:user_profile'))


def recover_password(request):
    if request.method == 'GET':
        return render(request, 'accounts/recover_password.html')
    elif request.method == 'POST':
        email = request.POST.get("recover_email")
        user_queryset = User.objects.all().filter(email__iexact=email)
        if user_queryset.count() == 0:
            # TODO error no such user
            pass
        elif user_queryset.count() > 1:
            # TODO something went wrong
            pass
        user = user_queryset[0]
        current_recover_string = user.email_recover_string
        user_id = user.id
        recovery_url = ip + 'accounts/' + user_id + '/' + current_recover_string
        message = 'برای وارد کردن رمز جدید خود، وارد لینک زیر شوید:' + '\n'
        message += recovery_url
        recovery_email = EmailMessage('Password recovery', message, email)
        recovery_email.send()
        # TODO return something?


def recover_pwd(request, uid, rec_str):
    if request.method == 'GET':
        # todo what to do here?
        return render(request, 'accounts/enter_new_password.html')
    if request.method == 'POST':
        password = request.POST.get('recovery_password')
        user_queryset = User.objects.all().filter(id=uid)
        if user_queryset.count() != 1:
            # TODO shitty link
            pass
        user = user_queryset[0]
        recovery_string = user.email_recover_string
        if recovery_string != rec_str:
            # TODO shitty link
            pass
        user.email_recover_string = generate_recover_string()
        user.password = password
        return HttpResponseRedirect(reverse('Home'))


def user_profile(request):
    if not request.user.is_authenticated:
        return render(request, 'accounts/login.html', {'error_message': 'please login first'})
    print(request.user.is_charity)
    print(request.user.is_benefactor)
    # try:
    print(request.user)
    context = {"type": request.user.is_charity, "username": request.user.username, "email": request.user.email,
               "country": request.user.contact_info.country, "province": request.user.contact_info.province,
               "city": request.user.contact_info.city, "address": request.user.contact_info.address,
               "phone_number": request.user.contact_info.phone_number, 'description': request.user.description}
    if request.user.is_benefactor:
        # try:
        benefactor = get_object(Benefactor, user=request.user)
        context['user'] = benefactor
        context['benefactor'] = benefactor
        projects = {project for project in Project.objects.all() if benefactor in project.benefactors}
        context['project_count'] = len(projects)
        abilities = benefactor.ability_set.all()
        score = benefactor.calculate_score()
        print(request)
        context['score'] = score
        context["first_name"] = benefactor.first_name
        context["last_name"] = benefactor.last_name
        context["gender"] = benefactor.gender
        context["age"] = benefactor.age
        context["credit"] = benefactor.credit
        print(context)
        # print(context.__str__())
        # except:
        #     print(1)

    else:
        try:
            charity = get_object(Charity, user=request.user)
            context["name"] = charity.name
            context["score"] = charity.score
        except:
            print(1)
    return render(request, 'accounts/user-profile.html', context)
    # except:
    #     context = error_context_generate('Unexpected Error', 'Error Getting Account Data!', '')
    #     # TODO Raise Error
    #     template = loader.get_template('accounts/error_page.html')
    #     return HttpResponse(template.render(context, request))


#### Customize User

@csrf_exempt
def customize_user_data(request):
    if not request.user.is_authenticated:
        return render(request, 'accounts/login.html', {'error_message': 'لطفاً اول وارد شوید'})
    try:
        notifications = Notification.objects.filter(user=request.user).all()
        context = {"type": request.user.is_charity, "username": request.user.username, "email": request.user.email,
                   "country": request.user.contact_info.country, "province": request.user.contact_info.province,
                   "city": request.user.contact_info.city, "address": request.user.contact_info.address,
                   "phone_number": request.user.contact_info.phone_number, "description": request.user.description,
                   "notifications": notifications, 'password': request.user.password}
        if request.user.is_benefactor:
            try:
                benefactor = get_object(Benefactor, user=request.user)
                projects = {project for project in Project.objects.all() if benefactor in project.benefactors}
                context['project_count'] = len(projects)
                score = benefactor.calculate_score()
                context['score'] = score
                context["first_name"] = benefactor.first_name
                context["last_name"] = benefactor.last_name
                context["gender"] = benefactor.gender
                context["age"] = benefactor.age
                context["credit"] = benefactor.credit
            except:
                print(1)


        else:
            try:
                context["name"] = request.user.charity.name
                context["score"] = request.user.charity.calculate_score()
            except:
                print(1)

        return render(request, 'accounts/user-profile.html', context)
    except:
        context = error_context_generate('Unexpected Error', 'Error Getting Account Data!', '')
        # TODO Raise Error
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))


def customize_user(request):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'لطفاً اول وارد شوید', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not request.user.is_active:
        context = error_context_generate('Deactivated Account Error',
                                         'Your Account Has Been Marked as Deactivated!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if check_valid(request.POST.get('password')):
        request.user.password = request.POST.get("password")
    if check_valid(request.POST.get('description')):
        request.user.description = request.POST.get("description")
    if check_valid(request.POST.get("province")):
        request.user.contact_info.province = request.POST.get("province")
    if check_valid(request.POST.get("city")):
        request.user.contact_info.city = request.POST.get("city")
    if check_valid(request.POST.get("address")):
        request.user.contact_info.address = request.POST.get("address")
    if check_valid(request.POST.get("phone_number")):
        request.user.contact_info.phone_number = request.POST.get("phone_number")
    request.user.save()
    request.user.contact_info.save()
    if request.user.is_charity:
        if check_valid(request.POST.get("name")):
            request.user.charity.name = request.POST.get("name")
        request.user.charity.save()
    else:
        if check_valid(request.POST.get("first_name")):
            request.user.benefactor.first_name = request.POST.get("first_name")
        if check_valid(request.POST.get("last_name")):
            request.user.benefactor.last_name = request.POST.get("last_name")
        if check_valid(request.POST.get("gender")):
            request.user.benefactor.gender = request.POST.get("gender")
        if check_valid(request.POST.get("age")):
            request.user.benefactor.age = int(request.POST.get("age"))
        request.user.benefactor.save()
    Logger.account_update(request.user, None, None)
    # TODO Fix Redirect
    return HttpResponseRedirect(reverse('accounts:user_profile'))

    # if not request.user.is_authenticated :
    # return 1 #fixme redirect to error.html with appropriate context


@csrf_exempt
def add_benefactor_credit(request):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'You are not Signed In!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not request.user.is_active:
        context = error_context_generate('Deactivated Account Error',
                                         'Your Account Has Been Marked as Deactivated!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if request.user.is_charity:
        # TODO Raise Account Type Error
        context = error_context_generate('Account Type Error',
                                         'I Don\'t Know How You Ended Here But Charities Cannot Add Credits!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    # try:
    benefactor = get_object(Benefactor, user=request.user)
    amount = float(request.POST.get('deposit_amount'))
    benefactor.credit += amount
    benefactor.save()
    # FIXME Redirect to user profile view
    Logger.account_update(request.user, None, None)
    return HttpResponseRedirect(reverse('user_profile'))
    # except:
    #     context = {
    #         'error_message': 'error in deposit!',
    #         # FIXME Redirect to user profile view
    #         'redirect_address': 'user_profile'
    #     }
    #     return HttpResponseRedirect(reverse('error'))


def submit_benefactor_comment(request, ability_id):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'You are not Signed In!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not request.user.is_active:
        context = error_context_generate('Deactivated Account Error',
                                         'Your Account Has Been Marked as Deactivated!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if request.user.is_benefactor:
        # TODO Raise Account Type Error
        context = error_context_generate('Account Type Error', 'Benefactors Cannot Comment on Other Benefactors', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    ability = get_object(Ability, id=ability_id)
    # benefactor_users = User.objects.filter(username=benefactor_username)
    if ability is None:
        # TODO Raise Not Found Error
        context = error_context_generate('Not Found', 'Requested Ability Cannot be Found', 'accounts:charity_dashboard')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    try:
        benefactor = ability.benefactor
        charity = ability.charity
        charity_projects = [nf_project for nf_project in charity.project_set if nf_project.type != 'financial']
        if len([project for project in NonFinancialProject.objects.all() if
                project.project in charity_projects and project.ability_type is ability.ability_type]) <= 0:
            context = error_context_generate('No Cooperation Error',
                                             'You Cannot Submit a Comment for a Benefactor with Whom You Had no ' +
                                             'Cooperation On This Ability Type!',
                                             'accounts:charity_dashboard')
            # TODO Raise No_Cooperation Error
            template = loader.get_template('accounts/error_page.html')
            return HttpResponse(template.render(context, request))
        comment_set = benefactor.benefactorcomment_set.filter(benefactor=benefactor, ability=ability, charity=charity).all()
        if comment_set.count() <= 0:
            comment = BenefactorComment.objects.create(commented=benefactor, commentor=request.user.charity,
                                                   ability=ability, comment_string=request.POST.get('comment_string'))
        else:
            comment = comment_set[0]
            comment.comment_string = request.POST.get('comment_string')
            comment.save()
        # TODO Redirect to Benefactor Profile Page
        Logger.submit_comment(request.user, benefactor.user, None)
        return HttpResponseRedirect([])
    except:
        # TODO Raise Unexpcted Error
        context = error_context_generate('Unexpected Error', 'Error While Submitting The Comment', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))


def submit_charity_comment(request, charity_username):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'You are not Signed In!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if not request.user.is_active:
        context = error_context_generate('Deactivated Account Error',
                                         'Your Account Has Been Marked as Deactivated!', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if request.user.is_charity:
        # TODO Raise Account Type Error
        context = error_context_generate('Account Type Error', 'Charities Cannot Comment on Other Charities', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    if request.user.benefactor.charity_set.get(user=get_object(User, username=charity_username)).count <= 0:
        context = error_context_generate('No Cooperation Error',
                                         'You Cannot Submit a Comment for a Charity with Which You Had no Cooperation!', '')
        # TODO Raise No_Cooperation Error
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    charity_users = User.objects.filter(username=charity_username)
    if charity_users.count() <= 0:
        # TODO Raise Not Found Error
        context = error_context_generate('Not Found', 'Requested User Cannot be Found', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    charity_user = charity_users.all()[0]
    try:
        charity = charity_user.charity
        comment_set = charity.charitycomment_set.filter(benefactor=request.user.benefactor, charity=charity).all()
        if comment_set.count() <= 0:
            comment = CharityComment.objects.create(commented=charity, commentor=request.user.benefactor,
                                                   comment_string=request.POST.get('comment_string'))
        else:
            comment = comment_set[0]
            comment.comment_string = request.POST.get('comment_string')
            comment.save()
        comment = CharityComment.objects.create(commented=charity_user.charity, commentor=request.user.benefactor,
                                                comment_string=request.POST.get('comment_string'))
        # TODO Redirect to Charity Profile Page
        Logger.account_update(request.user, charity_user, None)
        return HttpResponseRedirect([])
    except:
        # TODO Raise Unexpected Error
        context = error_context_generate('Unexpected Error', 'Error While Submitting The comment', '')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))


def error_redirect(request, redirect_address):
    return HttpResponseRedirect(reverse(redirect_address))


class ErrorView(TemplateView):
    template_name = 'accounts/error_page.html'


def logout_user(request):
    if not request.user.is_authenticated:
        # TODO Raise Authentication Error
        context = error_context_generate('Authentication Error', 'You are not Signed In!', 'accounts:login_view')
        template = loader.get_template('accounts/error_page.html')
        return HttpResponse(template.render(context, request))
    Logger.logout(request.user, None, None)
    logout(request)
    template = loader.get_template('accounts/login.html')
    return HttpResponse(template.render({}, request))
