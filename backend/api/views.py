from django.db import transaction
from django.db.models import Sum
from django.shortcuts import HttpResponse, get_object_or_404
from recipes.models import (FavoriteRecipe, Ingredient, IngredientAmount,
                            Recipe, ShoppingCart, Tag)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from .filters import IngredientSearchFilter, RecipeFilter
from .mixins import ListRetrieveViewSet
from .permissions import IsAdminOrReadOnly
from .serializers import (FavoriteRecipeSerializer, IngredientSerializer,
                          RecipeCreateSerializer, RecipeReadSerializer,
                          ShoppingCartSerializer, TagSerializer)


class TagViewSet(ListRetrieveViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None


class IngredientViewSet(ListRetrieveViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    filter_class = IngredientSearchFilter


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminOrReadOnly,)
    filter_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeCreateSerializer

    @transaction.atomic()
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def __post(self, request, pk, serializers):
        data = {'user': request.user.id, 'recipe': pk}
        serializer = serializers(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def __delete(self, request, pk, model):
        user = request.user
        recipe = get_object_or_404(Recipe, id=pk)
        model_obj = get_object_or_404(model, user=user, recipe=recipe)
        model_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True, methods=['POST'],
        permission_classes=[IsAuthenticated],
    )
    def post_favorite(self, request, pk):
        return self.__post(
            request=request, pk=pk, serializers=FavoriteRecipeSerializer
        )

    @post_favorite.mapping.delete
    def delete_favorite(self, request, pk):
        return self.__delete(
            request=request, pk=pk, model=FavoriteRecipe
        )

    @action(
        detail=True, methods=['POST'],
        permission_classes=[IsAuthenticated],
    )
    def post_shopping_cart(self, request, pk):
        return self.__post(
            request=request, pk=pk, serializers=ShoppingCartSerializer
        )

    @post_shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk):
        return self.__delete(
            request=request, pk=pk, model=ShoppingCart
        )

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
