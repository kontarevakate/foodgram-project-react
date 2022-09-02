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
    id = serializers.ReadOnlyField(source='author.id')
    email = serializers.ReadOnlyField(source='author.email')
    username = serializers.ReadOnlyField(source='author.username')
    first_name = serializers.ReadOnlyField(source='author.first_name')
    last_name = serializers.ReadOnlyField(source='author.last_name')
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes', 'recipes_count')
    
    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        queryset = obj.author.recipes.all()
        if limit:
            queryset = queryset[:int(limit)]
        return RecipeAddingSerializer(queryset, many=True).data

    def get_recipes_count(self, obj):
        return obj.author.recipes.all().count()


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')

class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


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
    image = Base64ImageField(max_length=None, use_url=True)
    tags = TagSerializer(read_only=True, many=True)
    author = UserSubcribedSerializer()
    ingredients = IngredientAmountSerializer(
        source='recipe_ingredient',
        many=True,
        read_only=True,
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')
        read_only_fields = ('is_favorite', 'is_shopping_cart',)

    def get_is_favorited(self, obj):
        user = self.context.get("request").user.id
        return FavoriteRecipe.objects.filter(user=user, recipe=obj.id).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get("request").user.id
        return ShoppingCart.objects.filter(user=user, recipe=obj.id).exists()


class CreateIngredientRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField()

    class Meta:
        model = IngredientAmount
        fields = ('id', 'amount')


class RecipeCreateSerializer(serializers.ModelSerializer):
    author = UserSubcribedSerializer(read_only=True)
    ingredients = CreateIngredientRecipeSerializer(many=True)
    image = Base64ImageField(max_length=None, use_url=True)

    class Meta:
        model = Recipe
        fields = ('author', 'tags', 'ingredients', 'name',
                  'image', 'text', 'cooking_time')

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
                    'Ингредиенты не должны повторяться'
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

    def __create_ingredients(self, ingredients, recipe):
        for ingredient in ingredients:
            IngredientAmount.objects.create(
                recipe=recipe,
                ingredient_id=ingredient['id'],
                amount=ingredient['amount'],
            )

    def create(self, validated_data):
        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredients')
        image = validated_data.pop('image')
        recipe = Recipe.objects.create(image=image, **validated_data)
        self.__create_ingredients(ingredients_data, recipe)
        recipe.tags.set(tags_data)
        return recipe

    def update(self, instance, validated_data):
        prev_ingredients = IngredientAmount.objects.filter(recipe=instance.id)
        prev_ingredients.delete()
        ingredients = validated_data.pop("ingredients")
        self.__create_ingredients(instance, ingredients)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        context = self.context
        return RecipeReadSerializer(instance, context=context).data

class FavoriteRecipeSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())
    
    class Meta:
        model = FavoriteRecipe
        fields = ('id', 'user', 'recipe')

    def validate(self, data):
        request = self.context.get('request')
        recipe = data['recipe']
        if FavoriteRecipe.objects.filter(user=request.user, recipe=recipe).exists():
            raise serializers.ValidationError(
                {'errors': ('Рецепт уже в избранном!')}
            )
        return data

    def to_representation(self, instance):
        context = {"request": self.context.get("request")}
        return RecipeReadSerializer(instance.recipe, context=context).data


class RecipeAddingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


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
