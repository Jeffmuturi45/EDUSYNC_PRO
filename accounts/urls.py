from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    # Auth
    path('login/',           views.LoginView.as_view(),              name='login'),
    path('logout/',          views.LogoutView.as_view(),             name='logout'),
    path('change-password/', views.ForceChangePasswordView.as_view(),
         name='force_change_password'),
    path('register/',        views.RegisterView.as_view(),           name='register'),

    # SuperAdmin
    path('organisations/create/', views.CreateOrganizationView.as_view(),
         name='create_organization'),

    # School Admin — User management
    path('users/',                  views.UserListView.as_view(),
         name='user_list'),
    path('users/add-teacher/',
         views.AddTeacherView.as_view(),      name='add_teacher'),
    path('users/add-student/',
         views.AddStudentView.as_view(),      name='add_student'),
    path('users/add-parent/',
         views.AddParentView.as_view(),       name='add_parent'),
    path('users/<uuid:user_id>/toggle/',
         views.ToggleUserActiveView.as_view(),  name='toggle_user'),
    path('users/<uuid:user_id>/reset-password/',
         views.ResetUserPasswordView.as_view(), name='reset_password'),
]
