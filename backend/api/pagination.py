from rest_framework.pagination import PageNumberPagination

from foodgram.settings import RECIPES_ON_PAGE


class LimitPageNumberPagination(PageNumberPagination):
    page_size = RECIPES_ON_PAGE
