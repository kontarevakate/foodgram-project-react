#from django.db import transaction
from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import HttpResponse, get_object_or_404
from djoser.views import UserViewSet

from recipes.models import (FavoriteRecipe, Ingredient, IngredientAmount,
                            Recipe, ShoppingCart, Tag)
from users.models import User, Follow

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated, AllowAny
from rest_framework.response import Response

from .pagination import LimitPageNumberPagination
from .filters import IngredientSearchFilter, RecipeFilter
from .mixins import ListRetrieveViewSet
from .permissions import IsAdminOrReadOnly, OwnerOrReadOnly
from .serializers import (IngredientSerializer,
                          RecipeCreateSerializer, RecipeReadSerializer,
                          TagSerializer, 
                          FollowSerializer, UserSubcribedSerializer, 
                          ShortRecipeSerializer)


class TagViewSet(ListRetrieveViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    permission_classes = (AllowAny,)


class IngredientViewSet(ListRetrieveViewSet):
    queryset = Ingredient.objects.all()
    permission_classes = (IsAdminOrReadOnly,)
    serializer_class = IngredientSerializer
    pagination_class = None
    filter_backends = [IngredientSearchFilter]
    search_fields = ('^name',)


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = (OwnerOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filter_class = RecipeFilter
    queryset = Recipe.objects.all()
    pagination_class = LimitPageNumberPagination

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeCreateSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def __post(self, model, user, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = ShortRecipeSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def __delete(self, model, user, pk):
        model.objects.filter(user=user, recipe__id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # def add_obj(self, model, user, pk):
    #     if model.objects.filter(user=user, recipe__id=pk).exists():
    #         return Response({
    #             'errors': 'Рецепт уже добавлен в список.'
    #         }, status=status.HTTP_400_BAD_REQUEST)
    #     recipe = get_object_or_404(Recipe, id=pk)
    #     model.objects.create(user=user, recipe=recipe)
    #     serializer = ShortRecipeSerializer(recipe)
    #     return Response(serializer.data, status=status.HTTP_201_CREATED)

    # def delete_obj(self, model, user, pk):
    #     obj = model.objects.filter(user=user, recipe__id=pk)
    #     obj.delete()
    #     return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=('post', 'delete'),
            permission_classes=(IsAuthenticated,))
    def favorite(self, request, pk=None):
        if request.method == 'POST':
            return self.__post(FavoriteRecipe, request.user, pk)
        elif request.method == 'DELETE':
            return self.__delete(FavoriteRecipe, request.user, pk)
    
    @action(detail=True, methods=('post', 'delete'),
            permission_classes=(IsAuthenticated,))
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self.__post(ShoppingCart, request.user, pk)
        elif request.method == 'DELETE':
            return self.__delete(ShoppingCart, request.user, pk)

    def create_shopping_cart(self, user):
        ingredients = (
            IngredientAmount.objects.filter(recipe__list__user=user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(amount=Sum('amount'))
        )
        shopping_list = f'Список покупок {user.first_name}\n\n'
        for ingredient in ingredients:
            shopping_list += (
                f'{ingredient["ingredient__name"]}: {ingredient["amount"]} '
                f'{ingredient["ingredient__measurement_unit"]}\n'
            )
        return shopping_list

    @action(detail=False, permission_classes=[IsAuthenticated], methods=['get'],)
    def download_shopping_cart(self, request):
        user = request.user
        if not user.list.exists():
            return Response({
                'errors': 'Ваш список покупок пуст.'
            }, status=status.HTTP_400_BAD_REQUEST
            )
        filename = f'{user.username}_shopping_list.txt'
        shopping_list = self.create_shopping_cart(user)
        response = HttpResponse(
            shopping_list, content_type='text.txt; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response


class FollowViewSet(UserViewSet):
    serializer_class = UserSubcribedSerializer
    pagination_class = LimitPageNumberPagination

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        user = request.user
        queryset = Follow.objects.filter(user=user)
        paginator = self.paginate_queryset(queryset)
        serializer = FollowSerializer(
            paginator,
            context={'request': request},
            many=True
        )
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post', ],
            permission_classes=[IsAuthenticated])
    def subscribe(self, request, id=None):
        user = request.user
        author = get_object_or_404(User, id=id)

        if user == author:
            return Response(
                {'errors': ('Нельзя подписаться на самого себя')},
                status=status.HTTP_400_BAD_REQUEST
            )
        if Follow.objects.filter(user=user, author=author).exists():
            return Response(
                {'errors': ('Подписка уже существует')},
                status=status.HTTP_400_BAD_REQUEST
            )

        follow = Follow.objects.create(user=user, author=author)
        serializer = FollowSerializer(
            follow, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def unsubscribe(self, request, id=None):
        user = request.user
        author = get_object_or_404(User, id=id)
        follow = Follow.objects.filter(user=user, author=author)
        if follow.exists():
            follow.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            {'errors': ('Нет подписки на этого автора')},
            status=status.HTTP_400_BAD_REQUEST
        )