from django.db import transaction
from django.db.models import Sum, Value, OuterRef, BooleanField, Exists
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
from .serializers import (FavoriteRecipeSerializer, IngredientSerializer,
                          RecipeCreateSerializer, RecipeReadSerializer,
                          ShoppingCartSerializer, TagSerializer, 
                          RecipeAddingSerializer, FollowSerializer, CheckFollowSerializer,
                          UserSubcribedSerializer)



class FavoriteViewSet(viewsets.ModelViewSet):

    serializer_class = FavoriteRecipeSerializer

    def get_queryset(self):
        user = self.request.user
        return FavoriteRecipe.objects.filter(user=user)


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
    filter_class = RecipeFilter
    queryset = Recipe.objects.all()

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeCreateSerializer

    @transaction.atomic()
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def __post(self, model, user, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = RecipeAddingSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def __delete(self, model, user, pk):
        model.objects.filter(user=user, recipe__id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'],
            permission_classes=[IsAuthenticated],
            url_path='favorite')
    def create_favorite(self, request, pk=None):
        data = {'user': request.user.id, 'recipe': pk}
        serializer = FavoriteRecipeSerializer(
            data=data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @create_favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        user = request.user
        recipe = get_object_or_404(Recipe, id=pk)
        favorite = get_object_or_404(FavoriteRecipe, user=user, recipe=recipe)
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=('post', 'delete'),
            permission_classes=(IsAuthenticated,))
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self.__post(ShoppingCart, request.user, pk)
        elif request.method == 'DELETE':
            return self.__delete(ShoppingCart, request.user, pk)

    def create_shopping_cart(self, ingredients):
        shopping_cart = '\n'.join([
            f'{ingredient["ingredient__name"]}: {ingredient["amount"]}'
            f'{ingredient["ingredient__measurement_unit"]}'
            for ingredient in ingredients
        ])
        return shopping_cart

    @action(detail=False, permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        recipes = IngredientAmount.objects.filter(
            recipe__shopping_cart__user=request.user
        )
        ingredients = recipes.values(
            'ingredient__name',
            'ingredient__measurement_unit',
        ).annotate(amount=Sum('amount'))
        shopping_cart = self.create_shopping_cart(ingredients)
        filename = shopping_cart.pdf
        response = HttpResponse(shopping_cart, content_type='text')
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