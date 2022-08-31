from django.shortcuts import get_object_or_404
from djoser.serializers import UserCreateSerializer, UserSerializer
from drf_base64.fields import Base64ImageField
from recipes.models import (FavoriteRecipe, Ingredient, IngredientAmount,
                            Recipe, ShoppingCart, Tag)
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator, UniqueValidator
from users.models import Follow, User


class CustomUserCreateSerializer(UserCreateSerializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    username = serializers.CharField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    first_name = serializers.CharField()
    last_name = serializers.CharField()

    class Meta:
        model = User
        fields = '__all__'


class UserSubcribedSerializer(UserSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Follow.objects.filter(author=obj.id).exists()


class CheckFollowSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ('user', 'author')
        read_only_fields = ('user',)
        model = Follow

    def validate(self, obj):
        user = obj['user']
        author = obj['author']
        subscribed = user.follower.filter(author=author).exists()

        if self.context.get('request').method == 'POST':
            if user == author:
                raise serializers.ValidationError(
                    'Вы не можете подписаться сами на себя'
                )
            if subscribed:
                raise serializers.ValidationError(
                    'Вы уже подписаны'
                )

        if self.context.get('request').method == 'DELETE':
            if user == author:
                raise serializers.ValidationError(
                    'Вы не можете отписаться от самого себя'
                )
            if not subscribed:
                raise serializers.ValidationError(
                    'Вы уже отписались'
                )
        return obj


class FollowSerializer(UserSubcribedSerializer):
    recipes = serializers.SerializerMethodField(read_only=True)
    recipes_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes', 'recipes_count')

    def get_recipes_count(self, obj):
        return obj.author.recipes.all().count()


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = '__all__'


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = '__all__'


class IngredientAmountSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = IngredientAmount
        fields = ('id', 'name', 'measurement_unit', 'amount')
        validators = [
            UniqueTogetherValidator(
                queryset=IngredientAmount.objects.all(),
                fields=['ingredient', 'recipe']
            )
        ]


class RecipeReadSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True)
    author = UserSubcribedSerializer()
    ingredients = serializers.SerializerMethodField(read_only=True)
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = '__all__'


class RecipeCreateSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all()
    )
    ingredients = serializers.SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = '__all__'
        read_only_fields = ['author']

    def __create_ingredients(self, ingredients, recipe):
        bulk_list = list()
        for ingredient in ingredients:
            bulk_list.append(IngredientAmount(
                recipe=recipe,
                ingredient_id=ingredient.get('id'),
                amount=ingredient.get('amount'))
            )
        IngredientAmount.objects.bulk_create(bulk_list)

    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        recipe = super().create(validated_data)
        return self.__create_ingredients(
            recipe, ingredients=ingredients, tags=tags
        )

    def update(self, instance, validated_data):
        if 'ingredients' in validated_data:
            ingredients = validated_data.pop('ingredients')
            instance.ingredients.clear()
            self.__create_ingredients(ingredients, instance)
        if 'tags' in validated_data:
            instance.tags.set(
                validated_data.pop('tags')
            )
        return super().update(instance, validated_data)

    def validate(self, data):
        ingredients = data['ingredients']
        ingredient_list = []
        if not ingredients:
            raise serializers.ValidationError(
                'Кол-во ингредиентов не должно быть меньше 1'
            )
        for item in ingredients:
            ingredient = get_object_or_404(
                Ingredient, id=item['id']
            )
            if ingredient in ingredient_list:
                raise serializers.ValidationError(
                    'Ингредиенты н едолжны повторяться'
                )
            if int(item.get('amount')) < 1:
                raise serializers.ValidationError(
                    'Минимальное кол-во - 1'
                )
            ingredient_list.append(ingredient)
        tags = data['tags']
        if not tags:
            raise serializers.ValidationError(
                'У рецепта должен быть хотя бы один тег'
            )
        return data

    def validate_cooking_time(self, time):
        if int(time) < 1:
            raise serializers.ValidationError(
                'Время приготовления должно быть не меньше 1 минуты'
            )
        return time


class FavoriteRecipeSerializer(serializers.ModelSerializer):

    class Meta:
        model = FavoriteRecipe
        fields = ['favorite', 'recipe']
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=FavoriteRecipe.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже добавлен в избранное'
            )
        ]


class ShoppingCartSerializer(serializers.ModelSerializer):

    class Meta:
        model = ShoppingCart
        fields = ['shoppingcart', 'recipe']
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=ShoppingCart.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже добавлен в список покупок'
            )
        ]
