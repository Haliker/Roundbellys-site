from django.urls import path

from . import views

app_name = "web"
urlpatterns = [
    path("", views.home, name="home"),
    path("catering/", views.catering, name="catering"),
    path("catering/date-check/", views.date_check, name="date_check"),
    path("events/", views.events, name="events"),
    path("our-pizza/", views.menu, name="menu"),
    path("fundraising/", views.fundraising, name="fundraising"),
    path("wholesale/", views.wholesale, name="wholesale"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("thanks/<slug:kind>/", views.thanks, name="thanks"),
    path("robots.txt", views.robots),
]
