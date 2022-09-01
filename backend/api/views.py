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
                          RecipeAddingSerializer, FollowSerializer, CheckFollowSerialize,
                          UserSubcribedSerializer)


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

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeCreateSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Recipe.objects.annotate(
                is_favorited=Exists(FavoriteRecipe.objects.filter(
                    user=self.request.user, recipe__pk=OuterRef('pk'))
                ),
                is_in_shopping_cart=Exists(ShoppingCart.objects.filter(
                    user=self.request.user, recipe__pk=OuterRef('pk'))
                )
            )
        else:
            return Recipe.objects.annotate(
                is_favorited=Value(False, output_field=BooleanField()),
                is_in_shopping_cart=Value(False, output_field=BooleanField())
            )

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
    queryset = User.objects.all()
    serializer_class = UserSubcribedSerializer
    pagination_class = LimitPageNumberPagination

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, **kwargs):
        user = request.user
        author_id = self.kwargs.get('id')
        author = get_object_or_404(User, id=author_id)

        if request.method == 'POST':
            serializer = FollowSerializer(author,
                                          data=request.data,
                                          context={"request": request})
            serializer.is_valid(raise_exception=True)
            Follow.objects.create(user=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            subscription = get_object_or_404(Follow,
                                             user=user,
                                             author=author)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(subscribing__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = FollowSerializer(pages,
                                         many=True,
                                         context={'request': request})
        return self.get_paginated_response(serializer.data)
