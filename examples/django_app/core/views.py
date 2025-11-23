import logging

from django.http import HttpResponse

logger = logging.getLogger("logcost.examples.django")
logger.setLevel(logging.INFO)


def home(request):
    logger.info("Django home page accessed")
    return HttpResponse("Hello from Django + LogCost")


def user_profile(request, user_id: str):
    logger.info("User %s profile viewed", user_id)
    return HttpResponse(f"User {user_id}")
