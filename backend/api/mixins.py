from rest_framework import viewsets, mixins


class ListRetrieveViewSet(viewsets.GenericViewSet, 
                          mixins.ListModelMixin,
                          mixins.RetrieveModelMixin):
    pass
