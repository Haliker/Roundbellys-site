from django.urls import path

from . import fundraise, views

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
    # Fundraisers
    path("s/<str:code>/", fundraise.order_page, name="order_page"),
    path("s/<str:code>/thanks/", fundraise.order_thanks, name="order_thanks"),
    path("join/<str:code>/", fundraise.join, name="join"),
    path("me/<str:token>/", fundraise.seller_home, name="seller_home"),
    path("me/<str:token>/order/", fundraise.seller_log, name="seller_log"),
    path("me/<str:token>/flyer.pdf", fundraise.seller_flyer, name="seller_flyer"),
    path("group/<str:token>/", fundraise.coordinator, name="coordinator"),
    path("group/<str:token>/packing/", fundraise.packing, name="packing"),
    path("group/<str:token>/flyers.pdf", fundraise.all_flyers, name="all_flyers"),
]
